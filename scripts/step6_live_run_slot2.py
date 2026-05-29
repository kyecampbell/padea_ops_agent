#!/usr/bin/env python
"""
scripts/step6_live_run_slot2.py

Option C STEP 6 — Live JPC Tuesday (slot 2) run.
Run ONCE. Do not retry.

Target:
  session_slot_id = 2  (JPC Tuesday, Terrific Noodles, dinner 18:00)
  session_date    = 2026-06-02  (next clean Tuesday — no existing order)
  as_of           = 2026-05-30T16:30:00+10:00  (exactly T-72h before session start)
  window_hours    = 0.25  (±15 min — isolates slot 2 only; MBBC 16:00 and ISHS/LC 15:30 fall outside)

Expected outcome:
  - Aanya Desai (enr 63, vegetarian): VO variant, safe=True
  - Pooja Mehta  (enr 36, vegetarian): VO variant, safe=True
  - Rashid Khalil (enr 23, halal+veg):  halal VO variant, safe=True
  - vo_variant_requested informational steps for all three
  - order_lines.variant = 'vegetarian_option' for those three rows
  - No urgent no_safe_meal escalations for those students
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

# ── confirm no existing order for slot 2 / 2026-06-02 before running ──────────
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM orders WHERE session_slot_id = 2 AND session_date = '2026-06-02'"
        )
        existing = cur.fetchone()
        if existing:
            print(f"ABORT: order already exists for slot 2 / 2026-06-02 (id={existing[0]})")
            sys.exit(1)

        cur.execute("SELECT COALESCE(MAX(id), 0) FROM agent_runs")
        max_run_id_before = cur.fetchone()[0]

print(f"Max agent_run id before this run: {max_run_id_before}")
print("No existing order for slot 2 / 2026-06-02 — safe to proceed\n")

trigger = (
    "T-72h order trigger. "
    "as_of: 2026-05-30T16:30:00+10:00 — use this exact datetime "
    "when calling get_sessions_needing_orders, "
    "with window_hours=0.25 to target only JPC Tuesday (slot 2) on 2026-06-02."
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

# ── full agent_steps report ────────────────────────────────────────────────────
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
            reasoning = s[3] or ""
            print(f"       reasoning: {reasoning!r}")
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

        # ── VO confirmation for Aanya / Pooja / Rashid ────────────────────────
        if orders:
            order_id = orders[0][0]
            print(f"\n=== variant confirmation for order_id={order_id} ===")
            cur.execute(
                """
                SELECT ol.id, e.id AS enrolment_id, e.student_name,
                       mi.id AS item_id, mi.name AS meal,
                       ol.variant, ol.source
                FROM order_lines ol
                JOIN enrolments e  ON e.id  = ol.enrolment_id
                JOIN menu_items mi ON mi.id = ol.menu_item_id
                WHERE ol.order_id = %s
                  AND e.id IN (23, 36, 63)
                ORDER BY e.student_name
                """,
                (order_id,),
            )
            vo_rows = cur.fetchall()
            if vo_rows:
                for r in vo_rows:
                    print(
                        f"  enr={r[1]}  {r[2]:<20}  item_id={r[3]}  {r[4]:<45}  "
                        f"variant={r[5]!r}  source={r[6]!r}"
                    )
            else:
                print("  (none of enr 23/36/63 appear in this order — check cohort)")

            # also confirm no no_safe_meal steps for those enrolments
            print(f"\n=== no_safe_meal steps for run_id={run_id} ===")
            cur.execute(
                """
                SELECT step_index, tool_name, urgency, tool_input
                FROM agent_steps
                WHERE run_id = %s AND tool_name = 'no_safe_meal'
                ORDER BY step_index
                """,
                (run_id,),
            )
            escalations = cur.fetchall()
            if escalations:
                for e in escalations:
                    print(f"  [{e[0]:02d}] {e[1]}  urgency={e[2]}  input={e[3]}")
            else:
                print("  (none — all students fed)")

            # vo_variant_requested steps
            print(f"\n=== vo_variant_requested steps for run_id={run_id} ===")
            cur.execute(
                """
                SELECT step_index, tool_name, urgency, tool_input, reasoning
                FROM agent_steps
                WHERE run_id = %s AND tool_name = 'vo_variant_requested'
                ORDER BY step_index
                """,
                (run_id,),
            )
            vo_steps = cur.fetchall()
            if vo_steps:
                for v in vo_steps:
                    print(f"  [{v[0]:02d}] {v[1]}  urgency={v[2]}")
                    print(f"       input: {v[3]}")
                    print(f"       reasoning: {v[4]!r}")
            else:
                print("  (none found — STEP 4 VO logging may not have fired)")

print(f"\nDone. Total agent_steps: {len(steps)}, orders: {len(orders)}")
