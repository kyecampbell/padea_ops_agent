"""
src/tools/gmail_client.py
Thin Gmail API client for the Padea operations agent.

Low-level only — no DB writes, no demo-mode logic, no agent wiring. The higher
layers (gmail_send / gmail_poll in src/tools/gmail.py) own the outbound_emails /
inbound_email_records row contract and the demo-mode recipient rewrite. This
module just talks to Google:

  send_message(raw)        — send a base64url-encoded RFC-2822 message, return id
  list_messages(query)     — list message ids matching a Gmail search query
  get_message(msg_id)      — fetch a full message resource
  mark_read(msg_id)        — remove the UNREAD label (optional; dedup is table-based)

Credentials: the token is minted once by scripts/gmail_auth.py (human browser
consent) and stored at settings.gmail_token_path. This module loads it, refreshes
it transparently when expired, and persists the refreshed token back to disk.
"""
from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config.settings import settings

# Single source of truth for scopes — imported by scripts/gmail_auth.py so the
# consent grant and the runtime load can never drift. gmail.modify covers reading
# and marking-read; gmail.send covers outbound. Changing this list requires
# re-running gmail_auth.py to re-consent.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _token_path() -> Path:
    return Path(settings.gmail_token_path)


def _credentials_path() -> Path:
    return Path(settings.gmail_credentials_path)


def load_credentials() -> Credentials:
    """
    Load the stored OAuth token, refreshing (and re-persisting) it if expired.

    Raises FileNotFoundError if the token has not been minted yet — run
    scripts/gmail_auth.py once to create it.
    """
    token_path = _token_path()
    if not token_path.exists():
        raise FileNotFoundError(
            f"Gmail token not found at {token_path}. "
            "Run `python scripts/gmail_auth.py` once to mint it (browser consent)."
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())

    if not creds or not creds.valid:
        raise RuntimeError(
            f"Gmail credentials at {token_path} are invalid and could not be "
            "refreshed. Re-run `python scripts/gmail_auth.py`."
        )

    return creds


def get_service():
    """Build an authenticated Gmail API service (v1)."""
    return build("gmail", "v1", credentials=load_credentials(), cache_discovery=False)


def send_message(raw: str) -> str:
    """
    Send a base64url-encoded RFC-2822 message. Returns the Gmail message id.

    `raw` is what email.message.EmailMessage produces via
    base64.urlsafe_b64encode(msg.as_bytes()).decode(). The caller owns headers.
    """
    service = get_service()
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return sent["id"]


def list_messages(query: str, max_results: int = 50) -> list[dict]:
    """
    List messages matching a Gmail search query (e.g. 'is:unread').

    Returns the raw list-entry dicts ({'id', 'threadId'}); empty list if none.
    """
    service = get_service()
    resp = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    return resp.get("messages", [])


def get_message(msg_id: str, fmt: str = "full") -> dict:
    """Fetch a single full message resource by id."""
    service = get_service()
    return (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format=fmt)
        .execute()
    )


def mark_read(msg_id: str) -> None:
    """Remove the UNREAD label from a message. Optional — dedup is table-based."""
    service = get_service()
    service.users().messages().modify(
        userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()
