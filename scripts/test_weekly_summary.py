#!/usr/bin/env python3
"""
scripts/test_weekly_summary.py

Integration tests for generate_weekly_summary and compose_weekly_summary_email
(src/tools/weekly_summary.py) against the live Supabase DB.

Seed facts (verified from live DB — STEP 0 ground truth, session 021):
  Caterer 2: Terrific Catering Co, price_includes_gst=False, gst_rate=10%
             delivery_fee_cents=3000, moq_4=10, moq_5=20, moq_6=30
  Week 2026-06-01 (Mon) to 2026-06-07 (Sun):
    Slot 2 (JPC Tue), 2026-06-02: 28 items, cost_cents=57400
    Slot 3 (JPC Wed), 2026-06-03: 33 items, cost_cents=67650
    total_items=61, total_cost_cents=125050
    total_delivery_cents=6000  (3000 × 2 sessions, ex-GST)
    ex_subtotal=131050         (125050 + 6000)
    grand_total_cents=144155   (round(131050 × 1.1) — delivery folded in)
    gst_amount_cents=13105     (144155 − 131050)
    variety_count=7 → moq_applicable=None → moq_floor_applied=False

Tests:
  1. test_generate_weekly_summary_terrific  — core aggregation and GST path
  2. test_idempotency                       — already_completed guard
  3. test_moq_set_not_increment             — variety=7 → no MOQ floor, orders untouched
  4. test_zero_orders                       — far-future week with no orders
"""
import sys
import datetime
from zoneinfo import ZoneInfo

from src.ingest.db import get_conn
from src.tools.weekly_summary import generate_weekly_summary, compose_weekly_summary_email

TZ = ZoneInfo("Australia/Brisbane")

CATERER_ID    = 2
WEEK_OF       = datetime.date(2026, 6, 1)   # any date in the target ISO week
AS_OF         = datetime.datetime(2026, 6, 1, 15, 30, 0, tzinfo=TZ)

EXPECTED_TOTAL_ITEMS       = 61
EXPECTED_TOTAL_COST_CENTS  = 125050
EXPECTED_TOTAL_DELIVERY_CENTS = 6000      # 3000 × 2 sessions, ex-GST
EXPECTED_GRAND_TOTAL_CENTS = 144155       # round((125050 + 6000) × 1.1)
EXPECTED_GST_AMOUNT_CENTS  = 13105        # 144155 − 131050

EXPECTED_SESSION_0 = {
    "session_date": datetime.date(2026, 6, 2),
    "session_slot_id": 2,
    "school_id": 2,
    "school_name": "John Paul College",
    "items": 28,
    "cost_cents": 57400,
}
EXPECTED_SESSION_1 = {
    "session_date": datetime.date(2026, 6, 3),
    "session_slot_id": 3,
    "school_id": 2,
    "school_name": "John Paul College",
    "items": 33,
    "cost_cents": 67650,
}


def test_generate_weekly_summary_terrific() -> None:
    """
    Core aggregation: correct totals, GST normalisation, session breakdown shape.
    """
    summary = generate_weekly_summary(CATERER_ID, WEEK_OF, AS_OF)

    assert summary["already_completed"] is False, (
        "already_completed should be False — no outbound_emails row for this week yet"
    )
    assert summary["total_items"] == EXPECTED_TOTAL_ITEMS, (
        f"total_items: expected {EXPECTED_TOTAL_ITEMS}, got {summary['total_items']}"
    )
    assert summary["total_cost_cents"] == EXPECTED_TOTAL_COST_CENTS, (
        f"total_cost_cents: expected {EXPECTED_TOTAL_COST_CENTS}, got {summary['total_cost_cents']}"
    )
    assert summary["grand_total_cents"] == EXPECTED_GRAND_TOTAL_CENTS, (
        f"grand_total_cents: expected {EXPECTED_GRAND_TOTAL_CENTS}, got {summary['grand_total_cents']}"
    )
    assert summary["gst_amount_cents"] == EXPECTED_GST_AMOUNT_CENTS, (
        f"gst_amount_cents: expected {EXPECTED_GST_AMOUNT_CENTS}, got {summary['gst_amount_cents']}"
    )
    assert summary["total_delivery_cents"] == EXPECTED_TOTAL_DELIVERY_CENTS, (
        f"total_delivery_cents: expected {EXPECTED_TOTAL_DELIVERY_CENTS}, got {summary['total_delivery_cents']}"
    )
    assert summary["moq_floor_applied"] is False, (
        f"moq_floor_applied: expected False (variety=7, no tier), got {summary['moq_floor_applied']}"
    )
    assert summary["moq_variance_cents"] == 0, (
        f"moq_variance_cents: expected 0, got {summary['moq_variance_cents']}"
    )

    breakdown = summary["session_breakdown"]
    assert len(breakdown) == 2, (
        f"session_breakdown length: expected 2, got {len(breakdown)}"
    )

    s0 = breakdown[0]
    for key, val in EXPECTED_SESSION_0.items():
        assert s0[key] == val, (
            f"session_breakdown[0][{key!r}]: expected {val!r}, got {s0[key]!r}"
        )

    s1 = breakdown[1]
    for key, val in EXPECTED_SESSION_1.items():
        assert s1[key] == val, (
            f"session_breakdown[1][{key!r}]: expected {val!r}, got {s1[key]!r}"
        )

    # Week boundaries
    assert summary["week_start"] == datetime.date(2026, 6, 1), (
        f"week_start: expected 2026-06-01, got {summary['week_start']}"
    )
    assert summary["week_end"] == datetime.date(2026, 6, 7), (
        f"week_end: expected 2026-06-07, got {summary['week_end']}"
    )

    print(
        f"  ✓ generate_weekly_summary: {summary['caterer_name']} week {summary['week_start']} "
        f"total_items={summary['total_items']} grand_total={summary['grand_total_cents']} "
        f"gst={summary['gst_amount_cents']} sessions={len(breakdown)}"
    )

    # Smoke-check compose renders without error and includes key content
    body = compose_weekly_summary_email(CATERER_ID, summary)
    assert "WEEKLY SUMMARY" in body, "email body must contain 'WEEKLY SUMMARY'"
    assert "John Paul College" in body, "email body must mention school name"
    assert "$1,250.50" in body or "1,250.50" in body, (
        "email body must show ex-GST cost $1,250.50"
    )
    assert "$1,441.55" in body or "1,441.55" in body, (
        "email body must show TOTAL DUE $1,441.55 (meals + delivery + GST)"
    )
    assert "DEMO" in body, "demo mode must prefix the body"
    print(f"  ✓ compose_weekly_summary_email: body rendered, DEMO prefix present")


def test_idempotency() -> None:
    """
    already_completed guard: if an outbound_emails row already exists for this
    caterer in this ISO week, generate_weekly_summary returns early with
    {"already_completed": True} and makes no DB mutations.
    """
    email_id: int | None = None
    week_start = WEEK_OF - datetime.timedelta(days=WEEK_OF.weekday())

    try:
        # Insert a sentinel weekly_consolidated_summary row for this week
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO outbound_emails (
                        email_type, status, intended_to_address,
                        subject, rendered_body, related_caterer_id, composed_at
                    ) VALUES (
                        'weekly_consolidated_summary', 'sent',
                        'idempotency-test@example.com',
                        'TEST IDEMPOTENCY', 'TEST BODY',
                        %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        CATERER_ID,
                        datetime.datetime(
                            week_start.year, week_start.month, week_start.day,
                            12, 0, 0, tzinfo=TZ,
                        ),
                    ),
                )
                email_id = cur.fetchone()[0]
            conn.commit()

        result = generate_weekly_summary(CATERER_ID, WEEK_OF, AS_OF)

        assert result == {"already_completed": True}, (
            f"Expected {{'already_completed': True}}, got {result}"
        )
        print(
            f"  ✓ idempotency: sentinel email_id={email_id} present → "
            f"already_completed=True returned, no mutations"
        )

    finally:
        if email_id is not None:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM outbound_emails WHERE id = %s", (email_id,)
                    )
                conn.commit()
            print(f"  ✓ cleanup: deleted outbound_emails id={email_id}")


def test_moq_set_not_increment() -> None:
    """
    variety_count=7 falls outside MOQ tiers {4,5,6} → moq_applicable=None →
    shortfall=0 → moq_floor_applied=False → orders are NOT mutated.

    Also verifies that both live orders (slot 2 / slot 3) still have
    moq_floor_applied=False and moq_variance_cents=0 in the DB after the call,
    confirming no spurious UPDATE ran.
    """
    summary = generate_weekly_summary(CATERER_ID, WEEK_OF, AS_OF)

    assert summary["moq_applicable"] is None, (
        f"moq_applicable: expected None (variety=7 outside tiers), got {summary['moq_applicable']}"
    )
    assert summary["moq_floor_applied"] is False, (
        f"moq_floor_applied: expected False, got {summary['moq_floor_applied']}"
    )
    assert summary["moq_variance_cents"] == 0, (
        f"moq_variance_cents: expected 0, got {summary['moq_variance_cents']}"
    )

    # Confirm orders in the week are untouched
    week_start = WEEK_OF - datetime.timedelta(days=WEEK_OF.weekday())
    week_end   = week_start + datetime.timedelta(days=6)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, moq_floor_applied, moq_variance_cents
                FROM orders
                WHERE caterer_id = %s
                  AND session_date >= %s
                  AND session_date <= %s
                ORDER BY session_date ASC
                """,
                (CATERER_ID, week_start, week_end),
            )
            rows = cur.fetchall()

    assert len(rows) == 2, f"expected 2 orders in week, got {len(rows)}"
    for oid, floor_applied, variance in rows:
        assert floor_applied is False, (
            f"order {oid}: moq_floor_applied should be False (no MOQ floor), got {floor_applied}"
        )
        assert variance == 0, (
            f"order {oid}: moq_variance_cents should be 0, got {variance}"
        )

    print(
        f"  ✓ moq_set_not_increment: variety=7 → moq_applicable=None → "
        f"no UPDATE ran; both orders have moq_floor_applied=False"
    )


def test_zero_orders() -> None:
    """
    Far-future week with no orders: all cost/count fields are zero.
    """
    future_week = datetime.date(2027, 6, 7)
    summary = generate_weekly_summary(CATERER_ID, future_week)

    assert summary["already_completed"] is False, (
        "already_completed should be False for a future week with no emails"
    )
    assert summary["total_items"] == 0, (
        f"total_items: expected 0, got {summary['total_items']}"
    )
    assert summary["total_cost_cents"] == 0, (
        f"total_cost_cents: expected 0, got {summary['total_cost_cents']}"
    )
    assert summary["grand_total_cents"] == 0, (
        f"grand_total_cents: expected 0, got {summary['grand_total_cents']}"
    )
    assert summary["gst_amount_cents"] == 0, (
        f"gst_amount_cents: expected 0, got {summary['gst_amount_cents']}"
    )
    assert summary["moq_floor_applied"] is False, (
        f"moq_floor_applied: expected False, got {summary['moq_floor_applied']}"
    )
    assert summary["moq_variance_cents"] == 0, (
        f"moq_variance_cents: expected 0, got {summary['moq_variance_cents']}"
    )
    assert len(summary["session_breakdown"]) == 0, (
        f"session_breakdown: expected empty list, got {len(summary['session_breakdown'])} items"
    )
    assert summary["sessions_count"] == 0, (
        f"sessions_count: expected 0, got {summary['sessions_count']}"
    )

    print(
        f"  ✓ zero_orders: week {future_week} → "
        f"total_items=0 grand_total=0 sessions=0 moq_floor=False"
    )


if __name__ == "__main__":
    print("\n=== test_weekly_summary.py ===\n")
    passed = 0
    failed = 0

    tests = [
        test_generate_weekly_summary_terrific,
        test_idempotency,
        test_moq_set_not_increment,
        test_zero_orders,
    ]

    for test_fn in tests:
        print(f"--- {test_fn.__name__} ---")
        try:
            test_fn()
            passed += 1
            print()
        except AssertionError as exc:
            print(f"  FAIL: {exc}\n", file=sys.stderr)
            failed += 1
        except Exception as exc:
            print(f"  ERROR: {type(exc).__name__}: {exc}\n", file=sys.stderr)
            failed += 1

    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
    print()
