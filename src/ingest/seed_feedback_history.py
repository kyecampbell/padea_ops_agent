#!/usr/bin/env python3
"""
seed_feedback_history.py — DUMMY DATA
Creates 5 weeks of historical orders + manager feedback to support quality monitoring.

Term 2 2026 started Mon Apr 21.  This script seeds weeks 1–5:
  Week 1: Apr 21–24   Week 2: Apr 28–May 1
  Week 3: May 5–8     Week 4: May 12–15     Week 5: May 19–22

CATERER TREND (engineered to trigger sustained-decline escalation for Terrific):
  Caterer 1 — Lakehouse  : steady 4–5 across all weeks
  Caterer 2 — Terrific    : excellent weeks 1–2, sharp decline weeks 3–5
  Caterer 3 — Kenko       : steady 4 across all weeks
  Caterer 4 — GyG         : variable 3–4 across all weeks

Ratings are designed so that:
  compute_rolling_mean(Terrific, weeks=4) ≈ 2.2  (<  quality_floor 3.0)
  compute_rolling_mean(Terrific, weeks=12) ≈ 3.3 (>> 4w mean, decline > 0.5)
→ sustained-decline escalation fires in the demo run.

NOTE: The feedback CHECK constraint requires:
  source='manager' → order_id IS NOT NULL, order_line_id IS NULL
  source='tutor'   → order_line_id IS NOT NULL, order_id IS NULL
Only manager-level (session) feedback is seeded here — no order_lines created.
For a richer demo the tutor path could be seeded with order_lines, but manager
ratings alone are sufficient for compute_rolling_mean.

FAKE DATA: No real feedback source exists.  These rows simulate manager
feedback submitted on the evening of each historical session.
"""
import datetime

from src.ingest.db import get_conn

# Week start dates (all Mondays — 2026-04-21 is Tuesday, correct start is 2026-04-20)
WEEK_STARTS = [
    datetime.date(2026, 4, 20),   # Week 1
    datetime.date(2026, 4, 27),   # Week 2
    datetime.date(2026, 5,  4),   # Week 3
    datetime.date(2026, 5, 11),   # Week 4
    datetime.date(2026, 5, 18),   # Week 5
]

# session_slot_id → (school_id, caterer_id, day_of_week, approx_students, tutor_id)
# Built from DB but hardcoded here for clarity (matches seeded data exactly)
# day_of_week: 1=Mon, 2=Tue, 3=Wed, 4=Thu
SLOT_INFO = {
    1:  {"caterer_id": 1, "day_of_week": 2, "students": 16, "tutor_id": 1},  # MBBC Tue  — Lakehouse
    2:  {"caterer_id": 2, "day_of_week": 2, "students": 26, "tutor_id": 2},  # JPC Tue   — Terrific
    3:  {"caterer_id": 2, "day_of_week": 3, "students": 34, "tutor_id": 3},  # JPC Wed   — Terrific
    4:  {"caterer_id": 2, "day_of_week": 4, "students": 7,  "tutor_id": 2},  # MSHS Thu  — Terrific
    5:  {"caterer_id": 3, "day_of_week": 1, "students": 34, "tutor_id": 4},  # ISHS Mon  — Kenko
    6:  {"caterer_id": 3, "day_of_week": 2, "students": 43, "tutor_id": 4},  # ISHS Tue  — Kenko
    7:  {"caterer_id": 3, "day_of_week": 4, "students": 37, "tutor_id": 5},  # ISHS Thu  — Kenko
    8:  {"caterer_id": 4, "day_of_week": 1, "students": 33, "tutor_id": 6},  # LC Mon    — GyG
    9:  {"caterer_id": 4, "day_of_week": 2, "students": 19, "tutor_id": 6},  # LC Tue    — GyG
    10: {"caterer_id": 4, "day_of_week": 1, "students": 15, "tutor_id": 5},  # CHAC Mon  — GyG
    11: {"caterer_id": 4, "day_of_week": 3, "students": 37, "tutor_id": 7},  # CHAC Wed  — GyG
}

# Approximate price per item (cents, pre-GST for excl-GST caterers)
CATERER_PRICE = {1: 3500, 2: 2050, 3: 550, 4: 1500}
CATERER_DELIVERY = {1: 0, 2: 3000, 3: 1000, 4: 0}  # per-session delivery (Terrific: 3000/school/trip)

# Manager feedback ratings by (caterer_id, week_index 0–4): one rating per session.
# Terrific (caterer 2) engineered to trigger sustained-decline alert.
RATINGS: dict[int, list[int]] = {
    # caterer 1 — Lakehouse — steady good
    1: [5, 4, 5, 4, 5],
    # caterer 2 — Terrific — sharp decline after week 2
    2: [5, 5, 3, 2, 1],
    # caterer 3 — Kenko — reliable
    3: [4, 4, 4, 4, 4],
    # caterer 4 — GyG — variable
    4: [4, 3, 4, 3, 3],
}

# Manager comments for notable sessions, keyed by (caterer_id, week_index)
COMMENTS: dict[tuple[int, int], dict[str, str]] = {
    (2, 2): {"manager": "Food was lukewarm on arrival, a few items missing."},
    (2, 3): {"manager": "Multiple items wrong — two halal students received non-halal meals. Delivery 20 min late."},
    (2, 4): {"manager": "Worst week yet. Three wrong orders, two students couldn't eat. Packaging damaged."},
}


def _session_date(week_start: datetime.date, day_of_week: int) -> datetime.date:
    """Return the calendar date for this day_of_week in the given week. 1=Mon…4=Thu."""
    return week_start + datetime.timedelta(days=day_of_week - 1)


def _feedback_time(session_date: datetime.date) -> datetime.datetime:
    """Feedback submitted at 8pm on session night."""
    return datetime.datetime(
        session_date.year, session_date.month, session_date.day,
        20, 0, 0, tzinfo=datetime.timezone.utc
    )


def run() -> None:
    order_count = 0
    feedback_count = 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            for week_idx, week_start in enumerate(WEEK_STARTS):
                for slot_id, info in SLOT_INFO.items():
                    caterer_id  = info["caterer_id"]
                    day_of_week = info["day_of_week"]
                    students    = info["students"]
                    tutor_id    = info["tutor_id"]

                    session_date  = _session_date(week_start, day_of_week)
                    composed_at   = datetime.datetime(
                        session_date.year, session_date.month, session_date.day,
                        9, 0, 0, tzinfo=datetime.timezone.utc
                    )

                    total_cost = students * CATERER_PRICE[caterer_id] + CATERER_DELIVERY[caterer_id]

                    # Guard: skip if order already exists (idempotent re-run)
                    cur.execute(
                        "SELECT id FROM orders WHERE session_slot_id = %s AND session_date = %s",
                        (slot_id, session_date),
                    )
                    if cur.fetchone():
                        continue

                    cur.execute(
                        """
                        INSERT INTO orders (
                            session_slot_id, caterer_id, session_date,
                            total_items, total_cost_cents, gst_rate_percent,
                            moq_floor_applied, moq_variance_cents,
                            composed_at, sent_at, is_preview_week, rotation_status
                        ) VALUES (
                            %s, %s, %s,
                            %s, %s, 10.00,
                            false, 0,
                            %s, %s, false, 'normal'
                        )
                        RETURNING id
                        """,
                        (
                            slot_id, caterer_id, session_date,
                            students, total_cost,
                            composed_at,
                            composed_at + datetime.timedelta(minutes=2),
                        ),
                    )
                    order_id = cur.fetchone()[0]
                    order_count += 1

                    # Manager feedback (source='manager' requires order_id, no order_line_id)
                    rating = RATINGS[caterer_id][week_idx]
                    comment = COMMENTS.get((caterer_id, week_idx), {}).get("manager")
                    cur.execute(
                        """
                        INSERT INTO feedback (
                            source, order_id, tutor_id, caterer_id, rating, comment,
                            food_on_time, correct_count_received, correct_dietary_delivered,
                            food_temperature_ok, visibly_wrong, submitted_at
                        ) VALUES (
                            'manager', %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            order_id, tutor_id, caterer_id, rating, comment,
                            rating >= 3,   # food_on_time
                            rating >= 3,   # correct_count_received
                            rating >= 4,   # correct_dietary_delivered
                            rating >= 3,   # food_temperature_ok
                            rating <= 2,   # visibly_wrong
                            _feedback_time(session_date),
                        ),
                    )
                    feedback_count += 1

            conn.commit()

    print(f"orders (historical):  {order_count} rows  (5 weeks × 11 slots)")
    print(f"feedback:             {feedback_count} rows  (1 manager rating per session)")
    print()
    print("Terrific Noodles manager rating trajectory:")
    for i, wk in enumerate(WEEK_STARTS):
        r = RATINGS[2][i]
        print(f"  Week {i+1} ({wk}): {r}")


if __name__ == "__main__":
    run()
