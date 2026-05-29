#!/usr/bin/env python
"""
scripts/step6_monday_run.py

STEP 6 — THE REVIEW GATE: live Monday consolidated-summary run.

  monday_summary caterer_id=2 week_of=2026-06-01 as_of=2026-06-01T15:30:00+10:00

Fresh script on the step4_live_run.py pattern (step6_live_run_slot2.py's
o.created_at post-run query is broken — not reused). Reports the full
agent_steps log and every outbound_emails row the run wrote, with the
auto-send / queued-for-approval split made explicit.

Run ONCE.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"),
    override=True,
)

from src.ingest.db import get_conn
from src.agent.loop import run

TRIGGER = (
    "monday_summary caterer_id=2 week_of=2026-06-01 as_of=2026-06-01T15:30:00+10:00"
)

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM agent_runs")
        run_before = cur.fetchone()[0]

print(f"Max agent_run id before: {run_before}")
print(f"Trigger: {TRIGGER!r}")
print("\n--- AGENT RUN START ---\n", flush=True)

try:
    run(TRIGGER)
except Exception as exc:
    import traceback

    print(f"\n[EXCEPTION: {type(exc).__name__}: {exc}]")
    traceback.print_exc()

print("\n--- AGENT RUN END ---\n", flush=True)

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, notes, started_at, completed_at FROM agent_runs "
            "WHERE id > %s ORDER BY id",
            (run_before,),
        )
        runs = cur.fetchall()
        if not runs:
            print("No new agent_run created — failed before create_agent_run.")
            sys.exit(1)
        run_id = runs[-1][0]
        notes, started, completed = runs[-1][1], runs[-1][2], runs[-1][3]

        print(f"=== agent_run id={run_id} ===")
        print(f"started:   {started}")
        print(f"completed: {completed}")
        print(f"notes:\n{notes}\n")

        cur.execute(
            """
            SELECT step_index, tool_name, urgency, reasoning, tool_input
            FROM agent_steps WHERE run_id=%s ORDER BY step_index
            """,
            (run_id,),
        )
        steps = cur.fetchall()
        print(f"=== agent_steps ({len(steps)} rows) ===")
        blank_decision_steps = []
        for idx, tool, urg, reasoning, tinput in steps:
            rsn = (reasoning or "").strip().replace("\n", " ")
            print(f"\n  [{idx:02d}] {tool}  urgency={urg}")
            print(f"       reasoning: {rsn[:280]}" + (" [...]" if len(rsn) > 280 else ""))
            print(f"       tool_input: {str(tinput)[:200]}")
            if not rsn and tool not in ("session_order_sent",):
                blank_decision_steps.append((idx, tool))

        print(f"\n=== call count: {len(steps)} (cap 20) ===")
        if blank_decision_steps:
            print(f"  blank-reasoning steps: {blank_decision_steps}")

        cur.execute(
            """
            SELECT id, email_type, status, intended_to_address, sent_at,
                   queued_for_approval_at, gmail_message_id, related_run_id,
                   related_caterer_id, rendered_body
            FROM outbound_emails WHERE related_run_id=%s ORDER BY id
            """,
            (run_id,),
        )
        emails = cur.fetchall()
        print(f"\n=== outbound_emails written by run {run_id}: {len(emails)} ===")
        for em in emails:
            eid, etype, status, to, sent, queued, gmid, rid, cid, body = em
            print(f"\n  email_id={eid}  type={etype}  status={status}")
            print(f"    intended_to_address={to!r}")
            print(f"    sent_at={sent}  queued_for_approval_at={queued}")
            print(f"    related_run_id={rid}  related_caterer_id={cid}  gmail_message_id={gmid!r}")
            for line in (body or "").splitlines():
                if "TOTAL DUE" in line:
                    print(f"    >> {line.strip()}")

        # Mutation guard: confirm swap analysis did NOT change incumbent assignments
        cur.execute("SELECT id, current_caterer_id FROM schools ORDER BY id")
        print(f"\n=== schools.current_caterer_id (mutation guard) ===")
        for r in cur.fetchall():
            print(f"  school {r[0]}: caterer {r[1]}")

print("\nDone.")
