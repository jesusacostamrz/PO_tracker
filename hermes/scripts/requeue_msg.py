"""Requeue a Gmail message for Hermes intake: mark it UNREAD (and drop the
NeedsReview label if present). Usage: python scripts/requeue_msg.py <gmail_msg_id> [...]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import load_config
from connectors.gmail_client import GmailClient

cfg = load_config()
svc = GmailClient.from_config(cfg).service
for mid in sys.argv[1:]:
    msg = svc.users().messages().get(userId="me", id=mid, format="metadata").execute()
    # remove whichever NeedsReview id is actually on the message (the account has a dup label)
    names = {l["id"]: l["name"] for l in svc.users().labels().list(userId="me").execute()["labels"]}
    drop = [l for l in msg.get("labelIds", []) if names.get(l, "").endswith("NeedsReview")]
    svc.users().messages().modify(userId="me", id=mid,
                                  body={"addLabelIds": ["UNREAD"], "removeLabelIds": drop}).execute()
    print(f"requeued {mid}: +UNREAD -{drop}")
