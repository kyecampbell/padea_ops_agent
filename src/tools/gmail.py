"""
src/tools/gmail.py
Email-sending tools for the Padea operations agent.

gmail_send now performs a REAL Gmail API send and stamps the returned
gmail_message_id onto the outbound_emails row. The row-write contract is
unchanged from the stub — same columns, same statuses — Block C's renderer reads
these rows, so only gmail_message_id (was always NULL) is newly populated.

Two paths:
  gmail_send              — routine emails (session_order, weekly_consolidated_summary).
                            Actually sends, writes status='sent', sent_at=now(),
                            gmail_message_id=<real id>. A commercial email_type is
                            rejected here — it must go through queue_email_for_approval.
  queue_email_for_approval — commercial-relationship emails (warning, rfp,
                            cancellation, rfp_loser_courtesy). Writes
                            status='queued_for_approval'. NEVER sends — unchanged.

Demo vs production (settings.email_mode):
  demo (default)  — the email is REALLY sent, but to demo_email_address
                    (kyec898@gmail.com). intended_to_address keeps the real
                    production recipient; the body is prefixed
                    "[DEMO — Intended for: {real}]". Real cc recipients are NOT
                    emailed in demo mode (preserved only in intended_cc_addresses).
  production      — sent to the real recipient with real cc. Never set in dev.

Send failure: the outbound_emails row is written with status='failed' and
failure_reason captured, then the exception is re-raised so the agent loop logs
it as an urgent error observation. The tool never pretends a failed send sent.
"""
from __future__ import annotations

import base64
from email.message import EmailMessage

from psycopg.types.json import Jsonb

from config.settings import settings
from src.ingest.db import get_conn
from src.tools import gmail_client

# Commercial-relationship types may NEVER be sent by gmail_send — they require
# operator approval via queue_email_for_approval. This is the in-code guarantee
# that the real-send path cannot be reached by these types.
_COMMERCIAL_TYPES = frozenset(
    {"warning", "rfp", "cancellation", "rfp_loser_courtesy"}
)


_DEMO_PREFIX_MARKER = "[DEMO — Intended for:"


def _demo_body(to: str, body: str) -> str:
    # Idempotent: the compose_* helpers already prepend this prefix in demo mode,
    # so re-prefixing here would double it (and it now shows in the real inbox).
    if settings.email_mode == "demo" and not body.lstrip().startswith(_DEMO_PREFIX_MARKER):
        return f"[DEMO — Intended for: {to}]\n\n{body}"
    return body


def _actual_recipient(intended_to: str) -> str:
    """Where the email is REALLY sent: the demo sink in demo mode, else the real to."""
    if settings.email_mode == "demo":
        return settings.demo_email_address
    return intended_to


def _build_raw(
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    cc: list[str] | None,
) -> str:
    """Build a base64url-encoded RFC-2822 message for the Gmail API."""
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def gmail_send(
    to: str,
    subject: str,
    body: str,
    email_type: str,
    cc: list[str] | None = None,
    related_order_id: int | None = None,
    related_caterer_id: int | None = None,
    related_run_id: int | None = None,
    related_step_id: int | None = None,
) -> int:
    """
    Send a routine email via the Gmail API and write an outbound_emails row.

    email_type must be a routine public.email_type ('session_order' or
    'weekly_consolidated_summary'). Commercial-relationship types are rejected —
    they must go through queue_email_for_approval.

    Demo mode: the email is really sent to demo_email_address; intended_to_address
    stays the real recipient; the stored+sent body carries the demo prefix; real
    cc recipients are not emailed.

    On send success: status='sent', sent_at=now(), gmail_message_id=<real id>.
    On send failure: a status='failed' row is written with failure_reason, then
    the exception is re-raised for the loop to surface as an urgent error.

    Returns the outbound_email_id.
    """
    if email_type in _COMMERCIAL_TYPES:
        raise ValueError(
            f"gmail_send refused: {email_type!r} is a commercial-relationship type "
            "and must go through queue_email_for_approval (operator approval), "
            "never an auto-send."
        )

    stored_body = _demo_body(to, body)
    actual_to = _actual_recipient(to)
    # In demo mode we never email the real cc recipients.
    send_cc = cc if settings.email_mode != "demo" else None

    try:
        raw = _build_raw(settings.gmail_address, actual_to, subject, stored_body, send_cc)
        gmail_message_id = gmail_client.send_message(raw)
    except Exception as e:
        failure_reason = f"{type(e).__name__}: {e}"
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO outbound_emails (
                        email_type, status, intended_to_address, intended_cc_addresses,
                        subject, rendered_body, failed_at, failure_reason,
                        related_order_id, related_caterer_id,
                        related_run_id, related_step_id
                    ) VALUES (
                        %s, 'failed', %s, %s, %s, %s, now(), %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        email_type,
                        to,
                        Jsonb(cc) if cc is not None else None,
                        subject,
                        stored_body,
                        failure_reason,
                        related_order_id,
                        related_caterer_id,
                        related_run_id,
                        related_step_id,
                    ),
                )
            conn.commit()
        raise RuntimeError(f"Gmail send failed for {email_type} to {actual_to}: {failure_reason}") from e

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO outbound_emails (
                    email_type, status, intended_to_address, intended_cc_addresses,
                    subject, rendered_body, sent_at, gmail_message_id,
                    related_order_id, related_caterer_id,
                    related_run_id, related_step_id
                ) VALUES (
                    %s, 'sent', %s, %s, %s, %s, now(), %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    email_type,
                    to,
                    Jsonb(cc) if cc is not None else None,
                    subject,
                    stored_body,
                    gmail_message_id,
                    related_order_id,
                    related_caterer_id,
                    related_run_id,
                    related_step_id,
                ),
            )
            outbound_email_id = cur.fetchone()[0]
        conn.commit()
    return outbound_email_id


def queue_email_for_approval(
    email_type: str,
    to: str,
    subject: str,
    body: str,
    related_run_id: int,
    related_step_id: int | None = None,
    related_order_id: int | None = None,
    related_caterer_id: int | None = None,
) -> int:
    """
    Queue a commercial-relationship email for manager approval by writing an
    outbound_emails row with status='queued_for_approval'. Never auto-sends and
    never auto-advances the status — a human approves it downstream.

    email_type is a public.email_type enum value: 'warning', 'rfp',
    'cancellation', or 'rfp_loser_courtesy'.

    Demo mode: intended_to_address stays the real recipient; the stored body is
    prefixed with the demo marker.

    Returns the outbound_email_id.
    """
    stored_body = _demo_body(to, body)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO outbound_emails (
                    email_type, status, intended_to_address,
                    subject, rendered_body, queued_for_approval_at,
                    related_order_id, related_caterer_id,
                    related_run_id, related_step_id
                ) VALUES (
                    %s, 'queued_for_approval', %s, %s, %s, now(), %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    email_type,
                    to,
                    subject,
                    stored_body,
                    related_order_id,
                    related_caterer_id,
                    related_run_id,
                    related_step_id,
                ),
            )
            outbound_email_id = cur.fetchone()[0]
        conn.commit()
    return outbound_email_id
