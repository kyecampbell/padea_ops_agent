#!/usr/bin/env python3
"""
Test: get_sessions_needing_orders idempotency guard.

Two assertions:
  1. Positive control   — when no order exists for (slot, date), the function
                          returns that pair (windowing logic works).
  2. Idempotency guard  — after inserting an order on the *correct* weekday,
                          the function excludes that pair.

Uses slot 1 (MBBC, day_of_week=2 Tuesday, start_time=16:00) and
test date 2026-05-26 (Tuesday), which has no seeded order.

Cleans up the inserted order in a finally block.
"""
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from src.ingest.db import get_conn
from src.tools.sessions import get_sessions_needing_orders

BRISBANE = ZoneInfo("Australia/Brisbane")

TEST_SLOT_ID = 1
TEST_SESSION_DATE = date(2026, 5, 26)   # Tuesday — matches slot 1 day_of_week=2
TEST_CATERER_ID = 1                      # Lakehouse — slot 1's caterer in seeded data


def _insert_test_order() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (
                    session_slot_id, caterer_id, session_date,
                    total_items, total_cost_cents, gst_rate_percent
                ) VALUES (%s, %s, %s, 1, 100, 10.00)
                RETURNING id
                """,
                (TEST_SLOT_ID, TEST_CATERER_ID, TEST_SESSION_DATE),
            )
            order_id = cur.fetchone()[0]
        conn.commit()
    return order_id


def _delete_test_order(order_id: int) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))
        conn.commit()


def main() -> None:
    # --- Preconditions ---
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT day_of_week, start_time FROM session_slots WHERE id = %s AND active = true",
                (TEST_SLOT_ID,),
            )
            row = cur.fetchone()

    assert row is not None, f"Slot {TEST_SLOT_ID} not found or inactive"
    dow, start_time = row
    assert dow == 2, f"Expected slot {TEST_SLOT_ID} day_of_week=2 (Tuesday), got {dow}"
    assert TEST_SESSION_DATE.isoweekday() == dow, (
        f"{TEST_SESSION_DATE} is not isoweekday={dow} — pick a different test date"
    )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM orders WHERE session_slot_id = %s AND session_date = %s",
                (TEST_SLOT_ID, TEST_SESSION_DATE),
            )
            assert cur.fetchone() is None, (
                f"Order already exists for slot {TEST_SLOT_ID} / {TEST_SESSION_DATE}; "
                f"choose a different test date"
            )

    # as_of is exactly at the T-72h mark: session_dt - 72h
    session_dt = datetime.combine(TEST_SESSION_DATE, start_time, tzinfo=BRISBANE)
    as_of = session_dt - timedelta(hours=72)

    # --- Positive control: no order → session MUST be returned ---
    results = get_sessions_needing_orders(as_of=as_of, window_hours=1.0)
    hits = {(r["session_slot_id"], r["session_date"]) for r in results}
    assert (TEST_SLOT_ID, TEST_SESSION_DATE) in hits, (
        f"FAIL positive control: (slot={TEST_SLOT_ID}, {TEST_SESSION_DATE}) missing from results. "
        f"hits={hits}"
    )
    print(f"  [ok] positive control: (slot={TEST_SLOT_ID}, {TEST_SESSION_DATE}) returned — no order exists")

    # --- Idempotency guard: insert order → session must NOT be returned ---
    order_id = _insert_test_order()
    try:
        results = get_sessions_needing_orders(as_of=as_of, window_hours=1.0)
        hits = {(r["session_slot_id"], r["session_date"]) for r in results}
        assert (TEST_SLOT_ID, TEST_SESSION_DATE) not in hits, (
            f"FAIL idempotency guard: (slot={TEST_SLOT_ID}, {TEST_SESSION_DATE}) still returned "
            f"after order inserted. hits={hits}"
        )
        print(f"  [ok] idempotency guard: (slot={TEST_SLOT_ID}, {TEST_SESSION_DATE}) excluded after order inserted")
    finally:
        _delete_test_order(order_id)
        print(f"  [cleanup] test order deleted")

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
