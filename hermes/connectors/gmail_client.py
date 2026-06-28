"""Gmail connector for Hermes.

Reads unread PO emails + their PDF attachments, and applies Hermes labels
(Hermes/Processed, Hermes/NeedsReview) so the intake batch can triage the inbox.

Scope is gmail.modify: read + label/mark-read only. It deliberately still has NO
method to delete, trash, or send mail.

NOTE: the scope was upgraded from gmail.readonly to gmail.modify. The existing
read-only token is no longer sufficient — re-run scripts/gmail_auth.py once (via the
SSH tunnel on the VPS) to re-consent and mint a modify-scoped token.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailError(RuntimeError):
    pass


@dataclass
class GmailClient:
    service: object
    account: str
    _label_ids: dict[str, str] = field(default_factory=dict)  # label name -> id cache

    @classmethod
    def from_config(cls, cfg: dict) -> "GmailClient":
        gm = cfg["gmail"]
        token_path = Path(gm["token_path"])
        if not token_path.exists():
            raise GmailError(
                f"No Gmail token at {token_path}. Run scripts/gmail_auth.py once to grant read access."
            )
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                token_path.write_text(creds.to_json(), encoding="utf-8")
            else:
                raise GmailError("Gmail token is invalid/expired. Re-run scripts/gmail_auth.py.")
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
        return cls(service=service, account=profile.get("emailAddress", gm.get("account", "?")))

    # ---- read helpers ----
    def search(self, query: str, max_results: int = 20) -> list[dict]:
        resp = (
            self.service.users().messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        return resp.get("messages", [])

    def get_message(self, msg_id: str) -> dict:
        return self.service.users().messages().get(userId="me", id=msg_id, format="full").execute()

    @staticmethod
    def headers(msg: dict) -> dict:
        return {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

    def pdf_attachments(self, msg: dict) -> list[tuple[str, bytes]]:
        """Return [(filename, pdf_bytes)] for every PDF attached to the message."""
        out: list[tuple[str, bytes]] = []

        def walk(part: dict) -> None:
            filename = part.get("filename") or ""
            body = part.get("body", {})
            if filename.lower().endswith(".pdf") and body.get("attachmentId"):
                data = (
                    self.service.users().messages().attachments()
                    .get(userId="me", messageId=msg["id"], id=body["attachmentId"])
                    .execute()
                )
                out.append((filename, base64.urlsafe_b64decode(data["data"])))
            for sub in part.get("parts") or []:
                walk(sub)

        walk(msg.get("payload", {}))
        return out

    # ---- label helpers (gmail.modify) ----
    def ensure_label(self, name: str) -> str:
        """Return the labelId for ``name``, creating the (possibly nested) label if missing.

        Results are cached on the instance so a batch resolves each label at most once.
        """
        if name in self._label_ids:
            return self._label_ids[name]
        labels = self.service.users().labels().list(userId="me").execute().get("labels", [])
        for lbl in labels:
            self._label_ids[lbl["name"]] = lbl["id"]
        if name not in self._label_ids:
            created = (
                self.service.users().labels()
                .create(userId="me", body={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                })
                .execute()
            )
            self._label_ids[name] = created["id"]
        return self._label_ids[name]

    def apply_label(self, msg_id: str, label_name: str, mark_read: bool = False) -> None:
        """Add ``label_name`` to a message (creating it if needed). Optionally clear UNREAD."""
        body: dict = {"addLabelIds": [self.ensure_label(label_name)]}
        if mark_read:
            body["removeLabelIds"] = ["UNREAD"]
        self.service.users().messages().modify(userId="me", id=msg_id, body=body).execute()
