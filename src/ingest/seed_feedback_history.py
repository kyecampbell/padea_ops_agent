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

PER-SCHOOL DIVERGENCE (Terrific serves two schools — see SLOT_RATING_OVERRIDE):
  JPC (slots 2,3)      : 5,5,3,2,1  — collapse (drives the caterer-level alert)
  MacGregor (slot 4)   : 5,4,4,4,3  — healthy, only grazes the floor
  → per-school monitoring shows JPC in crisis while MacGregor stays fine.

Ratings are designed so the caterer-level (both schools combined) rolling mean
still trips the trigger as_of the demo week (2026-06-01 15:30 AEST):
  compute_rolling_mean(Terrific, weeks=4)  ≈ 2.56  (<  quality_floor 3.0)
  compute_rolling_mean(Terrific, weeks=12) ≈ 3.47  (12w − 4w ≈ 0.91 ≥ 0.5)
→ sustained-decline escalation still fires in the demo run.

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

# Per-slot rating override (takes precedence over the per-caterer RATINGS above).
# Terrific serves two schools — JPC (slots 2,3) and MacGregor (slot 4). To make
# per-school quality monitoring visibly matter, the two schools tell different
# stories on the SAME caterer: JPC collapses (5,5,3,2,1) while MacGregor stays
# healthy and only grazes the floor (5,4,4,4,3). The caterer-level rolling mean
# still trips the sustained-decline trigger (4w≈2.56<3.0, 12w−4w≈0.91≥0.5).
SLOT_RATING_OVERRIDE: dict[int, list[int]] = {
    4: [5, 4, 4, 4, 3],   # MacGregor (school 3) — healthy, ends just at the floor
}

# Per-session STUDENT (tutor) ratings for the Terrific demo schools, one list of
# n=6 student scores per week (week_index 0–4). These hang off order_lines as
# source='tutor' feedback so the per-school satisfaction chart shows real decimal
# student averages, not just the single manager integer. JPC's list is applied to
# BOTH its slots (2 and 3) so the JPC school mean equals the list mean.
#   JPC weekly means : 4.83, 4.83, 3.17, 2.00, 1.17  — collapse below the 3.0 floor
#   MacGregor means  : 4.67, 4.33, 3.67, 3.83, 3.17  — healthier, never below floor
# The caterer-level pooled (manager + tutor) rolling mean still trips the
# sustained-decline trigger as_of 2026-06-01 15:30 AEST:
#   4-week  = 163/63 = 2.59 (< 3.0)   12-week = 362/105 = 3.45   drop = 0.86 (≥ 0.5)
_JPC_STUDENT = [
    [5, 5, 5, 4, 5, 5],   # W1 mean 4.83
    [5, 5, 5, 5, 4, 5],   # W2 mean 4.83
    [3, 4, 3, 3, 2, 4],   # W3 mean 3.17
    [1, 2, 2, 3, 2, 2],   # W4 mean 2.00
    [1, 1, 2, 1, 1, 1],   # W5 mean 1.17
]
_MACG_STUDENT = [
    [5, 5, 4, 5, 5, 4],   # W1 mean 4.67
    [4, 4, 5, 4, 4, 5],   # W2 mean 4.33
    [4, 3, 4, 4, 4, 3],   # W3 mean 3.67
    [4, 4, 3, 4, 4, 4],   # W4 mean 3.83
    [3, 4, 3, 3, 3, 3],   # W5 mean 3.17
]
SLOT_STUDENT_RATINGS: dict[int, list[list[int]]] = {
    2: _JPC_STUDENT,   # JPC Tue
    3: _JPC_STUDENT,   # JPC Wed (same list → JPC school mean = list mean)
    4: _MACG_STUDENT,  # MacGregor Thu
}
STUDENT_LINES_PER_SESSION = 6  # n students rated per session

# Manager comments for notable sessions, keyed by (caterer_id, week_index).
# These describe the Terrific decline and apply only to the collapsing JPC slots;
# slots in SLOT_RATING_OVERRIDE (the healthy MacGregor session) get no comment so
# the text never contradicts a healthy rating.
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


def _slot_enrolment_ids(cur, slot_id: int, limit: int) -> list[int]:
    """First `limit` enrolment ids attached to this session slot (stable order)."""
    cur.execute(
        """
        SELECT e.id
        FROM enrolment_session_slots ess
        JOIN enrolments e ON e.id = ess.enrolment_id
        WHERE ess.session_slot_id = %s
        ORDER BY e.id
        LIMIT %s
        """,
        (slot_id, limit),
    )
    return [r[0] for r in cur.fetchall()]


def _terrific_menu_ids(cur) -> list[int]:
    cur.execute("SELECT id FROM menu_items WHERE caterer_id = 2 ORDER BY id")
    return [r[0] for r in cur.fetchall()]


def run() -> None:
    order_count = 0
    feedback_count = 0
    order_line_count = 0
    tutor_feedback_count = 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            terrific_menu = _terrific_menu_ids(cur)

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

                    # Order: reuse if it already exists (idempotent re-run), else insert.
                    cur.execute(
                        "SELECT id FROM orders WHERE session_slot_id = %s AND session_date = %s",
                        (slot_id, session_date),
                    )
                    existing = cur.fetchone()
                    if existing:
                        order_id = existing[0]
                    else:
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

                    submitted_at = _feedback_time(session_date)

                    # Manager feedback (source='manager' requires order_id, no order_line_id)
                    # Per-slot override (e.g. MacGregor) wins over the per-caterer trend.
                    # Guard: skip if a manager row already exists for this order.
                    cur.execute(
                        "SELECT 1 FROM feedback WHERE order_id = %s AND source = 'manager'",
                        (order_id,),
                    )
                    if not cur.fetchone():
                        if slot_id in SLOT_RATING_OVERRIDE:
                            rating = SLOT_RATING_OVERRIDE[slot_id][week_idx]
                            comment = None  # healthy session — no decline-narrative comment
                        else:
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
                                submitted_at,
                            ),
                        )
                        feedback_count += 1

                    # Student (tutor) feedback for the Terrific demo schools: 6 order_lines
                    # per session, each carrying one tutor rating submitted the same night.
                    # Guard: skip if order_lines already exist for this order.
                    if slot_id in SLOT_STUDENT_RATINGS:
                        cur.execute(
                            "SELECT 1 FROM order_lines WHERE order_id = %s LIMIT 1",
                            (order_id,),
                        )
                        if not cur.fetchone():
                            student_scores = SLOT_STUDENT_RATINGS[slot_id][week_idx]
                            enrolment_ids = _slot_enrolment_ids(
                                cur, slot_id, STUDENT_LINES_PER_SESSION
                            )
                            for i, (enr_id, score) in enumerate(
                                zip(enrolment_ids, student_scores)
                            ):
                                menu_item_id = terrific_menu[i % len(terrific_menu)]
                                cur.execute(
                                    """
                                    INSERT INTO order_lines (
                                        order_id, enrolment_id, menu_item_id, source
                                    ) VALUES (%s, %s, %s, 'rotation')
                                    RETURNING id
                                    """,
                                    (order_id, enr_id, menu_item_id),
                                )
                                order_line_id = cur.fetchone()[0]
                                order_line_count += 1

                                cur.execute(
                                    """
                                    INSERT INTO feedback (
                                        source, order_line_id, tutor_id, caterer_id,
                                        rating, submitted_at
                                    ) VALUES (
                                        'tutor', %s, %s, %s, %s, %s
                                    )
                                    """,
                                    (
                                        order_line_id, tutor_id, caterer_id,
                                        score, submitted_at,
                                    ),
                                )
                                tutor_feedback_count += 1

            conn.commit()

    print(f"orders (historical):     {order_count} new rows")
    print(f"manager feedback:        {feedback_count} new rows")
    print(f"order_lines (student):   {order_line_count} new rows")
    print(f"tutor feedback:          {tutor_feedback_count} new rows")
    print()
    print("Terrific Noodles manager rating trajectory:")
    for i, wk in enumerate(WEEK_STARTS):
        r = RATINGS[2][i]
        print(f"  Week {i+1} ({wk}): {r}")


if __name__ == "__main__":
    run()
