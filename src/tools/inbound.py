"""
src/tools/inbound.py
Inbound email tools for the Padea operations agent: poll + classify.

gmail_poll_inbox  — read UNREAD messages from the REAL padea.catering inbox and
                    drop any already recorded in inbound_email_records (dedup).
classify_inbound_email — route ONE message into an inbound_classification enum
                    value using Haiku (the ONLY sanctioned Haiku use in the whole
                    architecture), and write the dedup row.

POLL ISOLATION FROM DEMO MODE
-----------------------------
The demo-mode recipient rewrite lives entirely in src/tools/gmail.py
(_actual_recipient / settings.demo_email_address) and is referenced ONLY by
gmail_send. This module imports NEITHER of those. The poll talks to the Gmail API
with userId="me", which is fixed by the OAuth token identity
(padea.catering@gmail.com). There is no parameter, setting, or code path here by
which the poll could be pointed at the demo sink (kyec898). Demo mode affects
SENDING only; it cannot touch what gets read.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

import anthropic

from config.settings import settings
from src.ingest.db import get_conn
from src.tools import gmail_client

# The five inbound_classification enum values (public.inbound_classification).
_VALID_CLASSIFICATIONS = frozenset(
    {
        "absence",
        "caterer_order_confirmation",
        "caterer_price_change_notification",
        "parent_enrolment_response",
        "unclassified",
    }
)

_CLASSIFIER_SYSTEM_PROMPT = """\
You are an email router for a school catering operations system. Classify the \
inbound email into EXACTLY ONE of these five labels and reply with the label only \
— no punctuation, no explanation:

- absence: a parent notifying that their child will be absent / away / not \
attending a session.
- caterer_order_confirmation: a caterer confirming/acknowledging they received \
or will fulfil a meal order.
- caterer_price_change_notification: a caterer notifying that their prices have \
changed or will change.
- parent_enrolment_response: a parent submitting dietary preferences and/or \
selecting meals for their child (a structured term-start enrolment response).
- unclassified: anything else — complaints, unusual correspondence, delivery \
problems/cancellations, or anything you cannot confidently place in the above.

Reply with one label from that list and nothing else."""


def _extract_body(payload: dict) -> str:
    """Best-effort plain-text body from a Gmail message payload (walks parts)."""
    def decode(data: str) -> str:
        return base64.urlsafe_b64decode(data.encode()).decode(errors="replace")

    # Simple, non-multipart message.
    body = payload.get("body", {})
    if body.get("data") and payload.get("mimeType", "").startswith("text/plain"):
        return decode(body["data"])

    # Multipart: prefer text/plain, fall back to the first decodable part.
    fallback = ""
    for part in payload.get("parts", []) or []:
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if mime == "text/plain" and data:
            return decode(data)
        if data and not fallback:
            fallback = decode(data)
        # Nested multipart.
        if part.get("parts"):
            nested = _extract_body(part)
            if nested:
                return nested
    return fallback


def gmail_poll_inbox(
    since_last_run_timestamp: str | None = None,
    max_results: int = 50,
) -> list[dict]:
    """
    Read UNREAD messages from the real padea.catering inbox, dropping any already
    recorded in inbound_email_records (dedup by gmail_message_id).

    since_last_run_timestamp: optional ISO datetime. When given, only messages
    received after it are returned (Gmail `after:` filter). Dedup via
    inbound_email_records is the authoritative double-process guard regardless.

    Returns list of dicts:
        {gmail_message_id, from_address, subject, received_at (ISO), body}
    Empty list if nothing new.
    """
    query = "in:inbox is:unread"
    if since_last_run_timestamp:
        dt = datetime.fromisoformat(since_last_run_timestamp)
        query += f" after:{int(dt.timestamp())}"

    entries = gmail_client.list_messages(query, max_results=max_results)
    if not entries:
        return []

    candidate_ids = [e["id"] for e in entries]

    # Dedup: which of these have we already processed?
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT gmail_message_id FROM inbound_email_records "
                "WHERE gmail_message_id = ANY(%s)",
                (candidate_ids,),
            )
            already = {r[0] for r in cur.fetchall()}

    results: list[dict] = []
    for mid in candidate_ids:
        if mid in already:
            continue
        msg = gmail_client.get_message(mid)
        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        received_at = datetime.fromtimestamp(
            int(msg["internalDate"]) / 1000, tz=timezone.utc
        ).isoformat()
        results.append(
            {
                "gmail_message_id": mid,
                "from_address": headers.get("from", ""),
                "subject": headers.get("subject", ""),
                "received_at": received_at,
                "body": _extract_body(msg["payload"]),
            }
        )
    return results


def classify_inbound_email(
    gmail_message_id: str,
    from_address: str,
    subject: str,
    body: str,
    received_at: datetime,
) -> dict:
    """
    Classify one inbound message into an inbound_classification enum value using
    Haiku (settings.classifier_model — the ONLY Haiku use in the architecture),
    and write the inbound_email_records dedup row.

    Haiku ONLY routes; Sonnet (the agent loop) does all downstream reasoning,
    handler dispatch, and escalation. An unrecognised model reply falls back to
    'unclassified' — the safe default that surfaces to the operator.

    Idempotent: the inbound_email_records insert is ON CONFLICT DO NOTHING, so a
    re-classify of the same gmail_message_id will not duplicate the dedup row.

    Returns {gmail_message_id, classification}.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.classifier_model,
        max_tokens=16,
        system=_CLASSIFIER_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"From: {from_address}\nSubject: {subject}\n\n{body}"
                ),
            }
        ],
    )
    raw = next((b.text for b in response.content if b.type == "text"), "").strip().lower()
    classification = raw if raw in _VALID_CLASSIFICATIONS else "unclassified"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inbound_email_records (
                    gmail_message_id, received_at, from_address, subject, classified_as
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (gmail_message_id) DO NOTHING
                """,
                (gmail_message_id, received_at, from_address, subject, classification),
            )
        conn.commit()

    return {"gmail_message_id": gmail_message_id, "classification": classification}
