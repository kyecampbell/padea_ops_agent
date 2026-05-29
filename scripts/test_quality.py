#!/usr/bin/env python3
"""
scripts/test_quality.py
Tests for src/tools/quality.py — all functions are read-only, no DB cleanup needed.

Seed facts relied on (from seed_feedback_history.py):
  - 55 orders, 55 manager-level feedback rows, 0 order_lines, 0 tutor feedback rows
  - Slot 2 = JPC Tue (day_of_week=2, caterer_id=2 Terrific)
  - Week 5 (2026-05-18..): slot 2 session_date=2026-05-19, rating=1
      food_on_time=False, correct_dietary_delivered=False, visibly_wrong=True
  - Week 4 (2026-05-11..): last Thu session submitted at 2026-05-14 20:00 UTC
  - Terrific (caterer_id=2) 4w rolling mean from as_of=2026-05-29 00:00 AEST:
      since = 2026-05-01 00:00 AEST = 2026-04-30 14:00 UTC
      Included ratings: Apr 30 (5), May 5/6/7 (3,3,3), May 12/13/14 (2,2,2),
                        May 19/20/21 (1,1,1) = 10 ratings, sum=23, mean=2.3
"""
import sys
import datetime
from zoneinfo import ZoneInfo

from src.tools.quality import (
    compute_rolling_mean,
    get_feedback_for_session,
    get_feedback_since,
)

TZ = ZoneInfo("Australia/Brisbane")

# Pinned as_of: 2026-05-29 00:00:00 AEST = 2026-05-28 14:00:00 UTC
# 4 weeks back  = 2026-05-01 00:00:00 AEST = 2026-04-30 14:00:00 UTC
# Apr 30 Terrific session was submitted at 20:00 UTC → included; Apr 28/29 are not.
PINNED_AS_OF = datetime.datetime(2026, 5, 29, 0, 0, 0, tzinfo=TZ)
PINNED_TERRIFIC_MEAN = 2.3   # 23 / 10


def test_get_feedback_for_session_positive() -> None:
    """
    Slot 2 (JPC Tue, Terrific), week-5 date 2026-05-19: worst session (rating=1).
    Verifies manager rating, comment presence, two escalation-critical checklist
    fields, and that tutor fields are empty (no order_lines seeded).
    """
    result = get_feedback_for_session(2, datetime.date(2026, 5, 19))

    assert result["manager_rating"] == 1, (
        f"expected manager_rating=1 (Terrific worst week), got {result['manager_rating']!r}"
    )
    assert result["manager_comments"] is not None, (
        "expected a manager comment on worst Terrific session (week 5)"
    )

    # Escalation-critical checklist fields — seeded from rating=1 formula
    assert result["food_on_time"] is False, (
        f"expected food_on_time=False (rating=1 < 3), got {result['food_on_time']!r}"
    )
    assert result["correct_dietary_delivered"] is False, (
        f"expected correct_dietary_delivered=False (rating=1 < 4), got {result['correct_dietary_delivered']!r}"
    )
    assert result["visibly_wrong"] is True, (
        f"expected visibly_wrong=True (rating=1 <= 2), got {result['visibly_wrong']!r}"
    )

    # No tutor data (no order_lines seeded — conscious scope cut)
    assert result["tutor_ratings"] == [], (
        f"expected tutor_ratings=[] (no order_lines seeded), got {result['tutor_ratings']!r}"
    )
    assert result["student_avg"] is None, (
        f"expected student_avg=None (no tutor data), got {result['student_avg']!r}"
    )

    print(
        f"  ✓ get_feedback_for_session positive: "
        f"manager_rating={result['manager_rating']}, "
        f"food_on_time={result['food_on_time']}, "
        f"correct_dietary_delivered={result['correct_dietary_delivered']}, "
        f"visibly_wrong={result['visibly_wrong']}"
    )


def test_get_feedback_for_session_no_order() -> None:
    """Future date with no order — all fields must be None/empty, not an exception."""
    result = get_feedback_for_session(1, datetime.date(2026, 6, 3))

    for field in ("manager_rating", "manager_comments", "food_on_time",
                  "correct_count_received", "correct_dietary_delivered",
                  "food_temperature_ok", "visibly_wrong", "meals_left",
                  "kids_who_didnt_eat", "student_avg"):
        assert result[field] is None, (
            f"expected None for {field!r} (no order), got {result[field]!r}"
        )
    assert result["tutor_ratings"] == [], (
        f"expected [] for tutor_ratings (no order), got {result['tutor_ratings']!r}"
    )

    print("  ✓ get_feedback_for_session no-order: all None/[] as expected")


def test_compute_rolling_mean_live_terrific() -> None:
    """Live (no as_of) Terrific 4w mean must be non-None and below quality floor (3.0)."""
    mean = compute_rolling_mean(2, weeks=4)

    assert mean is not None, (
        "expected non-None for Terrific caterer (>=3 seeded ratings in last 4 weeks)"
    )
    assert mean < 3.0, (
        f"expected Terrific 4w mean < 3.0 (engineered decline), got {mean:.4f}"
    )

    print(f"  ✓ compute_rolling_mean live Terrific 4w: {mean:.4f} (< 3.0 quality floor)")


def test_compute_rolling_mean_pinned_terrific() -> None:
    """
    Pinned as_of=2026-05-29 00:00 AEST (= 2026-04-30 14:00 UTC cutoff).
    Terrific included ratings: [5, 3,3,3, 2,2,2, 1,1,1] = 10 values, mean=2.3.
    This assertion is deterministic regardless of when the test runs.
    """
    mean = compute_rolling_mean(2, weeks=4, as_of=PINNED_AS_OF)

    assert mean is not None, (
        f"expected non-None for pinned Terrific 4w (10 ratings), got None"
    )
    assert abs(mean - PINNED_TERRIFIC_MEAN) < 1e-9, (
        f"expected pinned mean={PINNED_TERRIFIC_MEAN}, got {mean:.10f}"
    )

    print(
        f"  ✓ compute_rolling_mean pinned Terrific 4w: {mean:.4f} "
        f"(as_of={PINNED_AS_OF.date()}, deterministic)"
    )


def test_compute_rolling_mean_insufficient_data() -> None:
    """Unknown caterer_id has 0 ratings — must return None, not 0.0."""
    mean = compute_rolling_mean(999, weeks=4)

    assert mean is None, (
        f"expected None for caterer 999 (insufficient data), got {mean!r}"
    )

    print("  ✓ compute_rolling_mean unknown caterer: None (< 3 ratings)")


def test_get_feedback_since() -> None:
    """
    Cutoff 2026-05-14 21:00 UTC — after last week-4 session (submitted 20:00 UTC same day).
    Expect exactly 11 rows: week-5 sessions only (3 Mon + 4 Tue + 2 Wed + 2 Thu).
    Spot-check: slot 2 on 2026-05-19 has caterer_id=2, rating=1, source='manager'.
    """
    cutoff = datetime.datetime(2026, 5, 14, 21, 0, 0, tzinfo=datetime.timezone.utc)
    rows = get_feedback_since(cutoff)

    assert len(rows) == 11, (
        f"expected 11 week-5 feedback rows, got {len(rows)}"
    )

    slot2_row = next(
        (r for r in rows
         if r["session_slot_id"] == 2 and r["session_date"] == datetime.date(2026, 5, 19)),
        None,
    )
    assert slot2_row is not None, (
        "expected a feedback row for slot 2 on 2026-05-19 (JPC Tue week 5)"
    )
    assert slot2_row["caterer_id"] == 2, (
        f"expected caterer_id=2 (Terrific) on slot 2, got {slot2_row['caterer_id']!r}"
    )
    assert slot2_row["rating"] == 1, (
        f"expected rating=1 (Terrific week-5 worst), got {slot2_row['rating']!r}"
    )
    assert slot2_row["source"] == "manager", (
        f"expected source='manager' (no order_lines), got {slot2_row['source']!r}"
    )

    print(
        f"  ✓ get_feedback_since: {len(rows)} rows returned\n"
        f"  ✓ slot 2 row: session_date={slot2_row['session_date']}, "
        f"caterer_id={slot2_row['caterer_id']}, "
        f"rating={slot2_row['rating']}, source={slot2_row['source']!r}"
    )


if __name__ == "__main__":
    print("\n=== test_quality.py ===\n")
    try:
        test_get_feedback_for_session_positive()
        test_get_feedback_for_session_no_order()
        test_compute_rolling_mean_live_terrific()
        test_compute_rolling_mean_pinned_terrific()
        test_compute_rolling_mean_insufficient_data()
        test_get_feedback_since()
        print("\nAll quality.py tests passed.\n")
    except AssertionError as exc:
        print(f"\nFAIL: {exc}\n", file=sys.stderr)
        sys.exit(1)
