"""
scripts/reset_demo.py

Reset the database to the clean SEED baseline between demo practice takes.

Wipes the entire agent-generated transactional layer so the next live run
starts from nothing and escalations pop up fresh on camera:
    - agent_runs + agent_steps        (all — 100% agent-generated)
    - outbound_emails                 (all)
    - inbound_email_records           (all — so a re-sent absence email isn't deduped)
    - orders + order_lines with id > MAX_SEED_ORDER_ID (agent-composed only)

PRESERVES the seed substrate the charts are computed from:
    - the 54 historical seed orders (id 60-114) + their order_lines
    - all feedback rows (manager + tutor ratings)
    - enrolments, schools, caterers, menu, dietary tags, session slots,
      exclusions, seeded absences, term meal preferences

The order-id sequence only increases (seed tops out at 114; the next live
order will be >= 143), so `id > MAX_SEED_ORDER_ID` is a safe, durable boundary
between seed and agent-composed orders.

Safety: runs inside one transaction; verifies the seed order count is unchanged
before committing and rolls back if it isn't. Rebuilds renderer/index.html at
the end (it will be blank until the next live run repopulates it).

Usage:
    python scripts/reset_demo.py            # reset + rebuild renderer
    python scripts/reset_demo.py --dry-run  # show what WOULD be deleted, change nothing
    python scripts/reset_demo.py --no-rebuild
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ingest.db import get_conn

MAX_SEED_ORDER_ID = 114  # seed historical orders are ids 60-114; anything above is agent-composed


def _count(cur, sql: str) -> int:
    cur.execute(sql)
    return cur.fetchone()[0]


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    rebuild = "--no-rebuild" not in sys.argv

    with get_conn() as conn:
        with conn.cursor() as cur:
            seed_before = _count(cur, f"SELECT count(*) FROM orders WHERE id <= {MAX_SEED_ORDER_ID}")
            if seed_before == 0:
                print("ABORT — no seed orders found (id <= "
                      f"{MAX_SEED_ORDER_ID}). DB does not look seeded; refusing to run.")
                sys.exit(1)

            targets = {
                "outbound_emails":       "SELECT count(*) FROM outbound_emails",
                "agent_steps":           "SELECT count(*) FROM agent_steps",
                "agent_runs":            "SELECT count(*) FROM agent_runs",
                "inbound_email_records": "SELECT count(*) FROM inbound_email_records",
                "order_lines (agent)":   f"SELECT count(*) FROM order_lines WHERE order_id > {MAX_SEED_ORDER_ID}",
                "orders (agent)":        f"SELECT count(*) FROM orders WHERE id > {MAX_SEED_ORDER_ID}",
            }
            print(f"Seed orders protected (id <= {MAX_SEED_ORDER_ID}): {seed_before}")
            print("Rows targeted for deletion:")
            for label, sql in targets.items():
                print(f"  {label}: {_count(cur, sql)}")

            if dry_run:
                print("\n--dry-run: no changes made.")
                return

            # FK-safe order: emails reference steps/runs/orders -> steps -> runs
            #                -> inbound -> order_lines -> orders
            cur.execute("DELETE FROM outbound_emails")
            cur.execute("DELETE FROM agent_steps")
            cur.execute("DELETE FROM agent_runs")
            cur.execute("DELETE FROM inbound_email_records")
            cur.execute(f"DELETE FROM order_lines WHERE order_id > {MAX_SEED_ORDER_ID}")
            cur.execute(f"DELETE FROM orders WHERE id > {MAX_SEED_ORDER_ID}")

            seed_after = _count(cur, f"SELECT count(*) FROM orders WHERE id <= {MAX_SEED_ORDER_ID}")
            if seed_after != seed_before:
                conn.rollback()
                print(f"\nABORT — seed order count changed ({seed_before} -> {seed_after}). "
                      "Rolled back, nothing deleted.")
                sys.exit(1)

        conn.commit()
        print("\n--- RESET COMMITTED ---")
        with conn.cursor() as cur:
            print(f"orders remaining (seed): {_count(cur, 'SELECT count(*) FROM orders')}")
            print(f"feedback remaining:      {_count(cur, 'SELECT count(*) FROM feedback')}")
            print(f"agent_runs remaining:    {_count(cur, 'SELECT count(*) FROM agent_runs')}")

    if rebuild:
        print("\nRebuilding renderer/index.html (will be blank until the next live run)...")
        script = Path(__file__).with_name("build_renderer.py")
        subprocess.run([sys.executable, str(script)], check=True)


if __name__ == "__main__":
    main()
