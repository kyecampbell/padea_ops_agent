"""
src/tools/gmail.py
Email-sending tools for the Padea operations agent.

These are STUBS: they write rows to outbound_emails but do NOT call the real
Gmail API (credentials not yet obtained). When real Gmail lands, gmail_send
performs the network send and stamps gmail_message_id; the row-write contract
stays the same.

Two paths:
  gmail_send              — routine emails (session_order, weekly_consolidated_summary).
                            Writes status='sent', sent_at=now(). Auto-sends.
  queue_email_for_approval — commercial-relationship emails (warning, rfp,
                            cancellation, rfp_loser_courtesy). Writes
                            status='queued_for_approval'. Never auto-sends.

Demo mode (settings.email_mode == 'demo', the default): intended_to_address is
kept as the real production recipient (per the schema comment — demo rewrites
the actual send target, not the intended field); the stored body is prefixed
with "[DEMO — Intended for: {to}]" so the audit trail shows the routing.
"""
from __future__ import annotations

from psycopg.types.json import Jsonb

from config.settings import settings
from src.ingest.db import get_conn


def _demo_body(to: str, body: str) -> str:
    if settings.email_mode == "demo":
        return f"[DEMO — Intended for: {to}]\n\n{body}"
    return body


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
    Send a routine email by writing an outbound_emails row with status='sent'.

    email_type is a public.email_type enum value — for this stub the callers are
    'session_order' and 'weekly_consolidated_summary'. Commercial-relationship
    types must go through queue_email_for_approval instead, never here.

    Demo mode: intended_to_address stays the real recipient; the stored body is
    prefixed with the demo marker. gmail_message_id is left NULL (no real send).

    Returns the outbound_email_id.
    """
    stored_body = _demo_body(to, body)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO outbound_emails (
                    email_type, status, intended_to_address, intended_cc_addresses,
                    subject, rendered_body, sent_at,
                    related_order_id, related_caterer_id,
                    related_run_id, related_step_id
                ) VALUES (
                    %s, 'sent', %s, %s, %s, %s, now(), %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    email_type,
                    to,
                    Jsonb(cc) if cc is not None else None,
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
