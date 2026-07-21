"""Offline check of GmailClient.body_text (fake payloads, no network)."""
import base64, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.gmail_client import GmailClient

def b64(s): return base64.urlsafe_b64encode(s.encode()).decode()

plain = {"payload": {"mimeType": "text/plain", "body": {"data": b64("hola\n2x bearing 6204")}}}
nested_html = {"payload": {"mimeType": "multipart/alternative", "body": {}, "parts": [
    {"mimeType": "text/html", "body": {"data": b64("<table><tr><td>ABC-1</td><td>5</td></tr></table>")}},
]}}

assert "bearing 6204" in GmailClient.body_text(plain)
html_out = GmailClient.body_text(nested_html)
assert "ABC-1" in html_out and "<" not in html_out  # tags stripped
print("OK test_rfq_gmail")
