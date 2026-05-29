#!/usr/bin/env python
"""
scripts/step5_live_run.py

STEP 5 — Prove gmail_send writes a real outbound_emails row end-to-end.

Re-runs Scenario 1 and Scenario 2 through the FULL agent loop on FRESH future
dates (existing orders 132/133/136 are on earlier dates; window_hours=0.25
isolates exactly one session per run so each scenario is deterministic).

  Scenario 1 — GYG / CHAC Wednesday, slot 11, caterer 4
    as_of=2026-06-07T15:30:00+10:00, window=0.25 -> session 2026-06-10 (CHAC Wed)
  Scenario 2 — Terrific / JPC Tuesday, slot 2, caterer 2
    as_of=2026-06-06T16:30:00+10:00, window=0.25 -> session 2026-06-09 (JPC Tue)

Run ONCE. Reports agent_steps, orders, and outbound_emails per run, plus a
⚑ VEGETARIAN OPTION render check on Scenario 2's email body.
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


def max_ids():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(id), 0) FROM agent_runs")
            r = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(MAX(id), 0) FROM outbound_emails")
            e = cur.fetchone()[0]
    return r, e


def report_run(run_id: int, label: str, vo_check: bool):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT notes, started_at, completed_at FROM agent_runs WHERE id=%s",
                (run_id,),
            )
            notes, started, completed = cur.fetchone()
            print(f"\n{'='*72}\n{label} — run_id={run_id}\n{'='*72}")
            print(f"started:   {started}")
            print(f"completed: {completed}")
            print(f"notes: {notes!r}")

            cur.execute(
                """
                SELECT step_index, tool_name, urgency, reasoning
                FROM agent_steps WHERE run_id=%s ORDER BY step_index
                """,
                (run_id,),
            )
            steps = cur.fetchall()
            print(f"\n--- agent_steps ({len(steps)} rows) ---")
            for idx, tool, urg, reasoning in steps:
                rsn = (reasoning or "").strip().replace("\n", " ")
                print(f"  [{idx:02d}] {tool:32s} {urg or '-':14s} {rsn[:160]}")

            cur.execute(
                """
                SELECT id, session_slot_id, session_date, caterer_id,
                       total_items, total_cost_cents,
                       (SELECT count(*) FROM order_lines ol WHERE ol.order_id=o.id)
                FROM orders o
                WHERE o.composed_at >= %s ORDER BY id
                """,
                (started,),
            )
            orders = cur.fetchall()
            print(f"\n--- orders composed during this run ({len(orders)}) ---")
            for o in orders:
                print(
                    f"  order_id={o[0]} slot={o[1]} date={o[2]} caterer={o[3]} "
                    f"items={o[4]} cost_cents={o[5]} lines={o[6]}"
                )

            cur.execute(
                """
                SELECT id, email_type, status, intended_to_address,
                       sent_at, gmail_message_id, related_order_id, rendered_body
                FROM outbound_emails WHERE related_run_id=%s ORDER BY id
                """,
                (run_id,),
            )
            emails = cur.fetchall()
            print(f"\n--- outbound_emails (related_run_id={run_id}): {len(emails)} ---")
            for em in emails:
                eid, etype, status, to, sent_at, gmid, oid, body = em
                demo_prefix = body.splitlines()[0] if body else ""
                print(f"  email_id={eid} type={etype} status={status}")
                print(f"    intended_to_address={to!r}")
                print(f"    sent_at={sent_at}  gmail_message_id={gmid!r}  related_order_id={oid}")
                print(f"    body[0]={demo_prefix!r}")
                if vo_check:
                    n_vo = body.count("VEGETARIAN OPTION")
                    print(f"    ⚑ VEGETARIAN OPTION occurrences in body: {n_vo}")
    return steps, orders, emails


SCENARIOS = [
    (
        "SCENARIO 1 (GYG / CHAC Wed, slot 11)",
        "T-72h order trigger. When calling get_sessions_needing_orders, use these "
        "exact values: as_of=2026-06-07T15:30:00+10:00 and window_hours=0.25.",
        False,
    ),
    (
        "SCENARIO 2 (Terrific / JPC Tue, slot 2 — VO students)",
        "T-72h order trigger. When calling get_sessions_needing_orders, use these "
        "exact values: as_of=2026-06-06T16:30:00+10:00 and window_hours=0.25.",
        True,
    ),
]

for label, trigger, vo_check in SCENARIOS:
    run_before, _ = max_ids()
    print(f"\n\n########## {label} ##########")
    print(f"Trigger: {trigger!r}")
    print("--- AGENT RUN START ---\n", flush=True)
    try:
        run(trigger)
    except Exception as exc:
        import traceback

        print(f"\n[EXCEPTION: {type(exc).__name__}: {exc}]")
        traceback.print_exc()
    print("\n--- AGENT RUN END ---", flush=True)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM agent_runs WHERE id > %s ORDER BY id DESC LIMIT 1",
                (run_before,),
            )
            row = cur.fetchone()
    if row is None:
        print(f"[{label}] No new agent_run created — run failed before create_agent_run.")
        continue
    report_run(row[0], label, vo_check)

print("\n\nDone.")
