#!/usr/bin/env python
"""
scripts/step2_real_send.py  — Block B STOP 2 live test.

Runs ONE order scenario through the full agent loop on a FRESH future date and
proves gmail_send now performs a REAL Gmail API send:

  Scenario — GYG / CHAC Wed, slot 11, caterer 4
    as_of=2026-06-21T15:30:00+10:00, window=0.25 -> session 2026-06-24 (fresh)

Reports the agent_steps log, the order, and the outbound_emails row (status,
email_type, intended_to_address, gmail_message_id). Then reads the sent message
BACK from the Gmail API to confirm it was really addressed to the demo sink with
the [DEMO — Intended for: ...] prefix. Run ONCE.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from src.ingest.db import get_conn
from src.agent.loop import run
from src.tools import gmail_client

TRIGGER = (
    "T-72h order trigger. When calling get_sessions_needing_orders, use these "
    "exact values: as_of=2026-06-21T15:30:00+10:00 and window_hours=0.25."
)


def latest_run_id_after(prev: int) -> int | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM agent_runs WHERE id > %s ORDER BY id DESC LIMIT 1", (prev,))
        row = cur.fetchone()
    return row[0] if row else None


with get_conn() as conn, conn.cursor() as cur:
    cur.execute("SELECT COALESCE(MAX(id),0) FROM agent_runs")
    run_before = cur.fetchone()[0]

print("########## STOP 2 — GYG / CHAC Wed slot 11, session 2026-06-17 ##########")
print(f"Trigger: {TRIGGER!r}\n--- AGENT RUN START ---\n", flush=True)
try:
    run(TRIGGER)
except Exception as exc:
    import traceback
    print(f"\n[EXCEPTION: {type(exc).__name__}: {exc}]")
    traceback.print_exc()
print("\n--- AGENT RUN END ---\n", flush=True)

run_id = latest_run_id_after(run_before)
if run_id is None:
    print("No new agent_run created — run failed before create_agent_run.")
    sys.exit(1)

with get_conn() as conn, conn.cursor() as cur:
    cur.execute("SELECT notes, started_at, completed_at FROM agent_runs WHERE id=%s", (run_id,))
    notes, started, completed = cur.fetchone()
    print(f"==== run_id={run_id} ====\nstarted={started}\ncompleted={completed}\nnotes={notes!r}")

    cur.execute(
        "SELECT step_index, tool_name, urgency, reasoning FROM agent_steps WHERE run_id=%s ORDER BY step_index",
        (run_id,),
    )
    steps = cur.fetchall()
    print(f"\n--- agent_steps ({len(steps)}) ---")
    for idx, tool, urg, reasoning in steps:
        rsn = (reasoning or "").strip().replace("\n", " ")
        print(f"  [{idx:02d}] {tool:32s} {urg or '-':14s} {rsn[:140]}")

    cur.execute(
        "SELECT id, session_slot_id, session_date, caterer_id, total_items, total_cost_cents "
        "FROM orders WHERE composed_at >= %s ORDER BY id",
        (started,),
    )
    print("\n--- orders this run ---")
    for o in cur.fetchall():
        print(f"  order_id={o[0]} slot={o[1]} date={o[2]} caterer={o[3]} items={o[4]} cost_cents={o[5]}")

    cur.execute(
        "SELECT id, email_type, status, intended_to_address, sent_at, gmail_message_id, "
        "failure_reason, rendered_body FROM outbound_emails WHERE related_run_id=%s ORDER BY id",
        (run_id,),
    )
    emails = cur.fetchall()
    print(f"\n--- outbound_emails (related_run_id={run_id}): {len(emails)} ---")
    sent_ids = []
    for eid, etype, status, to, sent_at, gmid, fail, body in emails:
        first_line = body.splitlines()[0] if body else ""
        print(f"  email_id={eid} type={etype} status={status}")
        print(f"    intended_to_address={to!r}")
        print(f"    sent_at={sent_at} gmail_message_id={gmid!r} failure_reason={fail!r}")
        print(f"    body[0]={first_line!r}")
        if gmid:
            sent_ids.append(gmid)

# Read the sent message BACK from Gmail to confirm real delivery to the demo sink.
print("\n--- Gmail API read-back (proves real send) ---")
for gmid in sent_ids:
    msg = gmail_client.get_message(gmid)
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    print(f"  message {gmid}:")
    print(f"    To:      {headers.get('To')}")
    print(f"    From:    {headers.get('From')}")
    print(f"    Subject: {headers.get('Subject')}")
    print(f"    Labels:  {msg.get('labelIds')}")
    print(f"    Snippet: {msg.get('snippet')[:120]!r}")

print("\nDone.")
