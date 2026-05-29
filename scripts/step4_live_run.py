#!/usr/bin/env python
"""
scripts/step4_live_run.py

STEP 4 — First live T-72h end-to-end agent run.
Run ONCE. Do not retry.

Target: as_of=2026-05-31T16:00:00+10:00
  -> slot 3 (JPC Wednesday 2026-06-03, caterer=Terrific Noodles id=2)
  -> slot 11 (CHAC Wednesday 2026-06-03, caterer=GYG id=4)
No exclusions on either school for 2026-06-03.
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

# ── snapshot max run_id before run ────────────────────────────────────────────
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM agent_runs")
        max_run_id_before = cur.fetchone()[0]
print(f"Max agent_run id before this run: {max_run_id_before}")

trigger = (
    "T-72h order trigger. "
    "as_of: 2026-05-31T16:00:00+10:00 — use this exact datetime "
    "when calling get_sessions_needing_orders."
)
print(f"Trigger: {trigger!r}")
print("\n--- AGENT RUN START ---\n", flush=True)

try:
    run(trigger)
except Exception as exc:
    import traceback
    print(f"\n[EXCEPTION: {type(exc).__name__}: {exc}]")
    traceback.print_exc()

print("\n--- AGENT RUN END ---", flush=True)

# ── query and report everything created ──────────────────────────────────────
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, notes, started_at, completed_at "
            "FROM agent_runs WHERE id > %s ORDER BY id",
            (max_run_id_before,),
        )
        runs = cur.fetchall()
        print(f"\n=== Agent runs created (id > {max_run_id_before}): {len(runs)} ===")
        for r in runs:
            print(f"  id={r[0]}")
            print(f"  notes: {r[1]!r}")
            print(f"  started:   {r[2]}")
            print(f"  completed: {r[3]}")

        if not runs:
            print("  (none — run may have failed before create_agent_run)")
            sys.exit(1)

        run_id = runs[-1][0]

        cur.execute(
            """
            SELECT step_index, tool_name, urgency, reasoning, tool_input
            FROM agent_steps WHERE run_id = %s ORDER BY step_index
            """,
            (run_id,),
        )
        steps = cur.fetchall()
        print(f"\n=== agent_steps for run_id={run_id}: {len(steps)} rows ===")
        for s in steps:
            print(f"\n  [{s[0]:02d}] tool={s[1]}  urgency={s[2]}")
            # Truncate long reasoning to 300 chars to keep output readable
            reasoning = s[3] or ""
            print(f"       reasoning: {reasoning[:300]!r}" + (" [...]" if len(reasoning) > 300 else ""))
            print(f"       tool_input: {s[4]}")

        cur.execute(
            """
            SELECT o.id, o.session_slot_id, o.session_date, o.caterer_id,
                   o.total_items, o.total_cost_cents,
                   (SELECT COUNT(*) FROM order_lines ol WHERE ol.order_id = o.id) AS line_count
            FROM orders o
            JOIN agent_runs ar ON ar.id = %s
            WHERE o.created_at >= ar.started_at
            ORDER BY o.id
            """,
            (run_id,),
        )
        orders = cur.fetchall()
        print(f"\n=== Orders written to DB this run: {len(orders)} ===")
        for o in orders:
            print(
                f"  order_id={o[0]}  slot={o[1]}  date={o[2]}  caterer={o[3]}  "
                f"students={o[4]}  cost_cents={o[5]}  order_lines={o[6]}"
            )

print(f"\nDone. Total agent_steps: {len(steps)}, orders: {len(orders)}")
