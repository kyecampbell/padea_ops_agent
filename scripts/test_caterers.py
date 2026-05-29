#!/usr/bin/env python3
"""
scripts/test_caterers.py
Tests for src/tools/caterers.py

All three functions are read-only projections except check_weekly_moq which
inserts temporary test orders + order_lines then deletes them in finally.

Seed facts used (verified from DB at test-design time):
  ISHS:     school_id=4,  postcode=4068
  JPC:      school_id=2,  postcode=4127,  session_slots=2 (slots 2+3)
  Terrific: caterer_id=2, moq_4=10, moq_5=20, moq_6=30,
            all active menu items price_cents=2050,  menu_item_ids 11–18
  Kenko:    caterer_id=3, postcode=4068 (same as ISHS)
  JPC enrolments active+opted-in: ids 18–32 (15 rows)
"""
import sys
import datetime

from src.ingest.db import get_conn
from src.tools.caterers import (
    caterers_within_range,
    check_weekly_moq,
    project_weekly_cost,
)

# ── known seed constants ─────────────────────────────────────────────────────
ISHS_SCHOOL_ID      = 4
JPC_SCHOOL_ID       = 2
TERRIFIC_CATERER_ID = 2
KENKO_CATERER_ID    = 3

TERRIFIC_ITEM_IDS        = [11, 12, 13, 14, 15]   # 5 distinct — all 2050 cents
TERRIFIC_ITEM_PRICE      = 2050                    # all Terrific items same price (GST-excl)
TERRIFIC_PRICE_INCL_GST  = False
TERRIFIC_GST_RATE        = 10.0
TERRIFIC_MOQ_5           = 20

JPC_ENROLMENT_IDS   = list(range(18, 33))     # 15 active opted-in enrolments at JPC

# Test week: 2026-06-22 Mon – 2026-06-28 Sun (no existing orders)
TEST_WEEK_OF    = datetime.date(2026, 6, 23)   # Tue — used as week_of argument
TEST_SESSION_A  = datetime.date(2026, 6, 23)   # Slot 2 JPC Tue → caterer=Terrific
TEST_SESSION_B  = datetime.date(2026, 6, 24)   # Slot 3 JPC Wed → caterer=Terrific
TEST_SLOT_ID_A  = 2
TEST_SLOT_ID_B  = 3


# ── helpers ──────────────────────────────────────────────────────────────────

def _insert_order_and_lines(conn, slot_id, session_date, enrolment_ids, item_ids):
    """Insert one order + N order_lines (cycling item_ids). Returns order_id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO orders
                (session_slot_id, caterer_id, session_date,
                 total_items, total_cost_cents, gst_rate_percent)
            VALUES (%s, %s, %s, %s, 0, 10.0)
            RETURNING id
            """,
            (slot_id, TERRIFIC_CATERER_ID, session_date, len(enrolment_ids)),
        )
        order_id = cur.fetchone()[0]
        for i, enrolment_id in enumerate(enrolment_ids):
            cur.execute(
                """
                INSERT INTO order_lines
                    (order_id, enrolment_id, menu_item_id, source)
                VALUES (%s, %s, %s, 'rotation'::order_line_source)
                """,
                (order_id, enrolment_id, item_ids[i % len(item_ids)]),
            )
    conn.commit()
    return order_id


# ── test functions ────────────────────────────────────────────────────────────

def test_caterers_within_range_exclude() -> None:
    """ISHS (postcode 4068) + exclude Kenko (also 4068) → 3 caterers returned."""
    results = caterers_within_range(ISHS_SCHOOL_ID, exclude_caterer_id=KENKO_CATERER_ID)
    ids_returned = {r["caterer_id"] for r in results}

    assert KENKO_CATERER_ID not in ids_returned, (
        f"Kenko should be excluded, got ids={ids_returned}"
    )
    assert len(results) == 3, (
        f"Expected 3 caterers in range (Lakehouse, Terrific, GyG), got {len(results)}: {ids_returned}"
    )
    # All returned caterers must have distance_km <= their max_delivery_km
    for r in results:
        assert r["distance_km"] <= r["max_delivery_km"], (
            f"caterer {r['caterer_id']} returned but {r['distance_km']:.2f}km > {r['max_delivery_km']}km"
        )
    # All distances must be positive (postcodes differ from ISHS 4068)
    for r in results:
        assert r["distance_km"] > 0, (
            f"Expected positive distance for caterer {r['caterer_id']}, got {r['distance_km']}"
        )

    print(f"  ✓ caterers_within_range exclude: {len(results)} caterers, Kenko absent")
    for r in results:
        print(f"    caterer_id={r['caterer_id']} {r['name']!r} distance={r['distance_km']}km")


def test_caterers_within_range_no_exclude() -> None:
    """ISHS with no exclusion → all 4 caterers returned (all within 50km of 4068)."""
    results = caterers_within_range(ISHS_SCHOOL_ID, exclude_caterer_id=None)
    ids_returned = {r["caterer_id"] for r in results}

    assert len(results) == 4, (
        f"Expected all 4 caterers within 50km of ISHS, got {len(results)}: {ids_returned}"
    )
    assert KENKO_CATERER_ID in ids_returned, (
        f"Kenko (same postcode as ISHS) must be included when not excluded"
    )
    # Kenko is at same postcode — distance should be ~0
    kenko = next(r for r in results if r["caterer_id"] == KENKO_CATERER_ID)
    assert kenko["distance_km"] < 1.0, (
        f"Kenko at same postcode 4068 — expected < 1km, got {kenko['distance_km']}"
    )

    print(f"  ✓ caterers_within_range no-exclude: all {len(results)} caterers in range")
    print(f"    Kenko distance={kenko['distance_km']}km (same postcode → ~0)")


def test_project_weekly_cost_terrific_jpc() -> None:
    """
    project_weekly_cost(Terrific, JPC) — assert exact GST-inclusive projected total
    computed independently.

    Terrific is price_includes_gst=False, gst_rate=10% → normalise raw prices × 1.1.
    Delivery fee is per-delivery (one delivery per session); 2 sessions = 2 fees.
    Expected formula (all values GST-inclusive):
      gst_incl_price    = round(raw_avg_price × 1.1)     e.g. round(2050 × 1.1) = 2255
      gst_incl_delivery = round(raw_delivery × 1.1)      e.g. round(3000 × 1.1) = 3300
      projected_items   = cohort_size × sessions_per_week
      projected_natural = projected_items × gst_incl_price + gst_incl_delivery × sessions_per_week
      moq_floor if projected_items < moq_5 (=20):
          moq_floor_cents = (20 - projected_items) × gst_incl_price
      projected_total = projected_natural + (moq_floor or 0)
    """
    # Independent DB queries
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*)
                FROM enrolments
                WHERE school_id = %s
                  AND opted_out_of_catering = false
                  AND (current_period_end_date IS NULL
                       OR current_period_end_date > CURRENT_DATE)
                """,
                (JPC_SCHOOL_ID,),
            )
            expected_cohort: int = cur.fetchone()[0]

            cur.execute(
                "SELECT round(avg(price_cents))::int FROM menu_items WHERE caterer_id = %s AND active = true",
                (TERRIFIC_CATERER_ID,),
            )
            raw_price: int = cur.fetchone()[0]

            cur.execute(
                "SELECT count(*) FROM session_slots WHERE school_id = %s AND active = true",
                (JPC_SCHOOL_ID,),
            )
            sessions_per_week: int = cur.fetchone()[0]

    assert raw_price == TERRIFIC_ITEM_PRICE, (
        f"expected avg item price={TERRIFIC_ITEM_PRICE}, got {raw_price}"
    )
    assert sessions_per_week == 2, (
        f"expected 2 JPC sessions/week (slots 2+3), got {sessions_per_week}"
    )

    # Terrific is GST-exclusive → normalise to GST-inclusive (independent of function)
    raw_delivery = 3000  # Terrific seed value
    gst_mult = 1 + TERRIFIC_GST_RATE / 100   # 1.1
    gst_incl_price    = round(raw_price    * gst_mult)   # round(2050 × 1.1) = 2255
    gst_incl_delivery = round(raw_delivery * gst_mult)   # round(3000 × 1.1) = 3300

    projected_items = expected_cohort * sessions_per_week
    projected_natural = projected_items * gst_incl_price + gst_incl_delivery * sessions_per_week
    moq_floor = None
    if projected_items < TERRIFIC_MOQ_5:
        moq_floor = (TERRIFIC_MOQ_5 - projected_items) * gst_incl_price
    expected_total = projected_natural + (moq_floor or 0)

    result = project_weekly_cost(TERRIFIC_CATERER_ID, JPC_SCHOOL_ID)

    assert result["cohort_size"] == expected_cohort, (
        f"cohort_size: expected {expected_cohort}, got {result['cohort_size']}"
    )
    assert result["per_meal_price_cents"] == gst_incl_price, (
        f"per_meal_price_cents: expected GST-incl {gst_incl_price} (raw {raw_price} × 1.1), "
        f"got {result['per_meal_price_cents']}"
    )
    assert result["delivery_fee_cents"] == gst_incl_delivery, (
        f"delivery_fee_cents: expected GST-incl {gst_incl_delivery} (raw {raw_delivery} × 1.1), "
        f"got {result['delivery_fee_cents']}"
    )
    assert result["moq_floor_cents"] == moq_floor, (
        f"moq_floor_cents: expected {moq_floor!r}, got {result['moq_floor_cents']!r}"
    )
    assert result["projected_total_cents"] == expected_total, (
        f"projected_total_cents: expected {expected_total}, got {result['projected_total_cents']}"
    )

    print(
        f"  ✓ project_weekly_cost Terrific/JPC: cohort={expected_cohort}, "
        f"price={gst_incl_price}c (GST-incl), delivery={gst_incl_delivery}c, "
        f"sessions={sessions_per_week}, moq_floor={moq_floor!r}c, total={expected_total}c"
    )


def test_check_weekly_moq_shortfall_then_met() -> None:
    """
    Insert test order_lines into an empty test week, exercise both cases.

    Shortfall case (order A only):
      10 lines × 5 varieties → total=10 < moq_5=20 → shortfall=10, cents=10×2050=20500

    Met-minimum case (order A + order B):
      25 lines × 5 varieties → total=25 >= moq_5=20 → shortfall=0, cents=0

    Cleanup: DELETE FROM orders CASCADE removes order_lines.
    """
    order_a_id = None
    order_b_id = None

    try:
        with get_conn() as conn:
            # ── order A: 10 lines, 5 varieties ──────────────────────────────
            order_a_id = _insert_order_and_lines(
                conn,
                slot_id=TEST_SLOT_ID_A,
                session_date=TEST_SESSION_A,
                enrolment_ids=JPC_ENROLMENT_IDS[:10],
                item_ids=TERRIFIC_ITEM_IDS,
            )

        # ── assert shortfall ──────────────────────────────────────────────
        result_a = check_weekly_moq(TERRIFIC_CATERER_ID, week_of=TEST_WEEK_OF)

        assert result_a["total_items"] == 10, (
            f"shortfall case: expected total_items=10, got {result_a['total_items']}"
        )
        assert result_a["moq_applicable"] == TERRIFIC_MOQ_5, (
            f"shortfall case: expected moq_applicable={TERRIFIC_MOQ_5} (moq_5), "
            f"got {result_a['moq_applicable']}"
        )
        assert result_a["shortfall"] == 10, (
            f"shortfall case: expected shortfall=10, got {result_a['shortfall']}"
        )
        # Terrific is GST-exclusive → shortfall_cents uses GST-inclusive price
        terrific_gst_incl_price = round(TERRIFIC_ITEM_PRICE * (1 + TERRIFIC_GST_RATE / 100))  # 2255
        expected_shortfall_cents_a = 10 * terrific_gst_incl_price   # 10 × 2255 = 22550
        assert result_a["shortfall_cents"] == expected_shortfall_cents_a, (
            f"shortfall case: expected shortfall_cents={expected_shortfall_cents_a} "
            f"(10 × {terrific_gst_incl_price} GST-incl), got {result_a['shortfall_cents']}"
        )

        print(
            f"  ✓ check_weekly_moq shortfall: total={result_a['total_items']}, "
            f"moq={result_a['moq_applicable']}, shortfall={result_a['shortfall']}, "
            f"shortfall_cents={result_a['shortfall_cents']}"
        )

        with get_conn() as conn:
            # ── order B: 15 more lines, same 5 varieties ─────────────────
            order_b_id = _insert_order_and_lines(
                conn,
                slot_id=TEST_SLOT_ID_B,
                session_date=TEST_SESSION_B,
                enrolment_ids=JPC_ENROLMENT_IDS,   # all 15
                item_ids=TERRIFIC_ITEM_IDS,
            )

        # ── assert met minimum ────────────────────────────────────────────
        result_b = check_weekly_moq(TERRIFIC_CATERER_ID, week_of=TEST_WEEK_OF)

        assert result_b["total_items"] == 25, (
            f"met-min case: expected total_items=25 (10+15), got {result_b['total_items']}"
        )
        assert result_b["moq_applicable"] == TERRIFIC_MOQ_5, (
            f"met-min case: expected moq_applicable={TERRIFIC_MOQ_5}, got {result_b['moq_applicable']}"
        )
        assert result_b["shortfall"] == 0, (
            f"met-min case: expected shortfall=0 (25 >= 20), got {result_b['shortfall']}"
        )
        assert result_b["shortfall_cents"] == 0, (
            f"met-min case: expected shortfall_cents=0, got {result_b['shortfall_cents']}"
        )

        print(
            f"  ✓ check_weekly_moq met-minimum: total={result_b['total_items']}, "
            f"shortfall={result_b['shortfall']}, shortfall_cents={result_b['shortfall_cents']}"
        )

    finally:
        # Clean up test orders — CASCADE removes order_lines
        if order_a_id is not None or order_b_id is not None:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    ids = [i for i in (order_a_id, order_b_id) if i is not None]
                    cur.execute(
                        "DELETE FROM orders WHERE id = ANY(%s)", (ids,)
                    )
                conn.commit()
            print(f"  ✓ cleanup: deleted test orders {ids}")


if __name__ == "__main__":
    print("\n=== test_caterers.py ===\n")
    try:
        test_caterers_within_range_exclude()
        test_caterers_within_range_no_exclude()
        test_project_weekly_cost_terrific_jpc()
        test_check_weekly_moq_shortfall_then_met()
        print("\nAll caterers.py tests passed.\n")
    except AssertionError as exc:
        print(f"\nFAIL: {exc}\n", file=sys.stderr)
        sys.exit(1)
