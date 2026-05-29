#!/usr/bin/env python
"""
scripts/dryrun_runner.py — DRY-RUN rehearsal helper (temporary).

Runs the agent loop ONCE with a trigger passed on argv, then prints a focused
report: the new run id, every agent_step, any orders written, and any
outbound_emails the run produced. Read-only reporting (no extra writes).

Usage:  python scripts/dryrun_runner.py "<trigger string>"
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from src.ingest.db import get_conn
from src.agent.loop import run

trigger = sys.argv[1]

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM agent_runs")
        before = cur.fetchone()[0]

print(f"Max agent_run id before: {before}")
print(f"Trigger: {trigger!r}")
print("\n--- AGENT RUN START ---\n", flush=True)

try:
    run(trigger)
except Exception as exc:
    import traceback
    print(f"\n[EXCEPTION: {type(exc).__name__}: {exc}]")
    traceback.print_exc()

print("\n--- AGENT RUN END ---\n", flush=True)

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, trigger_reason, started_at, completed_at, notes "
            "FROM agent_runs WHERE id > %s ORDER BY id",
            (before,),
        )
        runs = cur.fetchall()
        if not runs:
            print("No new agent_run created.")
            sys.exit(1)
        run_id = runs[-1][0]
        print(f"=== NEW RUN id={run_id} ===")
        print(f"started:   {runs[-1][2]}")
        print(f"completed: {runs[-1][3]}")
        print(f"notes:\n{runs[-1][4]}\n")

        cur.execute(
            "SELECT step_index, tool_name, urgency, reasoning "
            "FROM agent_steps WHERE run_id=%s ORDER BY step_index",
            (run_id,),
        )
        steps = cur.fetchall()
        print(f"=== agent_steps ({len(steps)} rows; cap 20) ===")
        for idx, tool, urg, reasoning in steps:
            rsn = (reasoning or "").strip().replace("\n", " ")
            print(f"  [{idx:02d}] {tool:32s} urgency={urg}")
            if rsn:
                print(f"        {rsn[:200]}" + (" [...]" if len(rsn) > 200 else ""))

        cur.execute(
            "SELECT id, session_slot_id, session_date, caterer_id, total_items, total_cost_cents "
            "FROM orders WHERE id > (SELECT COALESCE(MAX(id),0) FROM orders WHERE id IN "
            "(SELECT id FROM orders)) - 0 AND session_slot_id IS NOT NULL "
            "ORDER BY id DESC LIMIT 5"
        )
        # simpler: orders linked via this run's agent_steps tool_output is messy;
        # just show the most recent orders for eyeballing.
        cur.execute(
            "SELECT id, session_slot_id, session_date, caterer_id, total_items, total_cost_cents "
            "FROM orders ORDER BY id DESC LIMIT 3"
        )
        print("\n=== most recent 3 orders (newest first) ===")
        for o in cur.fetchall():
            print(f"  order_id={o[0]} slot={o[1]} date={o[2]} caterer={o[3]} items={o[4]} cost_cents={o[5]}")

        cur.execute(
            "SELECT id, email_type, status, intended_to_address, gmail_message_id, "
            "queued_for_approval_at, sent_at FROM outbound_emails "
            "WHERE related_run_id=%s ORDER BY id",
            (run_id,),
        )
        emails = cur.fetchall()
        print(f"\n=== outbound_emails for run {run_id}: {len(emails)} ===")
        for e in emails:
            print(f"  email_id={e[0]} type={e[1]} status={e[2]} to={e[3]!r}")
            print(f"        gmail_message_id={e[4]!r} queued_at={e[5]} sent_at={e[6]}")

print(f"\nNEW_RUN_ID={run_id}")
