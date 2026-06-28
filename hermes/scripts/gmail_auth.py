"""One-time Gmail consent — mints .secrets/gmail_token.json (gmail.modify scope).

Scope (read + label/mark-read) comes from connectors.gmail_client.SCOPES. Re-run
this whenever that scope changes — the old token won't carry the new permissions.

Headless/VPS-friendly: it does NOT try to open a browser. It prints a URL and
waits on a fixed loopback port (8765) so the consent redirect can return over an
SSH tunnel. See README for the exact tunnel command.

Run (inside an SSH session opened with  -L 8765:localhost:8765 ):
    cd /opt/hermes-po && . .venv/bin/activate && python scripts/gmail_auth.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from core.config import load_config  # noqa: E402
from connectors.gmail_client import SCOPES  # noqa: E402

PORT = 8765


def main() -> int:
    cfg = load_config()
    gm = cfg["gmail"]
    client_path = Path(gm["oauth_client_path"])
    token_path = Path(gm["token_path"])
    if not client_path.exists():
        print(f"FAILED: missing OAuth client JSON at {client_path}")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
    creds = flow.run_local_server(
        host="localhost",
        port=PORT,
        open_browser=False,
        authorization_prompt_message=(
            "\n>>> Open this URL in your browser and approve Gmail access "
            "(read + apply labels):\n\n{url}\n"
        ),
        success_message="Done — you can close this tab and return to the terminal.",
    )
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    token_path.chmod(0o600)
    print(f"\nOK — token saved to {token_path}. Now run: python scripts/test_gmail.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
