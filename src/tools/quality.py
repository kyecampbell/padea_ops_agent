"""
src/tools/quality.py
Feedback and quality monitoring tools for the Padea operations agent.

Reads: get_feedback_for_session, compute_rolling_mean, get_feedback_since
Writes: none
"""
from __future__ import annotations

from datetime import datetime, timedelta
from datetime import date
from zoneinfo import ZoneInfo

from src.ingest.db import get_conn

TZ = ZoneInfo("Australia/Brisbane")


def get_feedback_for_session(session_slot_id: int, session_date: date) -> dict:
    """
    Return feedback summary for a specific (session_slot, date).

    Returns dict with:
        manager_rating: int | None              — 1-5 rating, None if not submitted.
        manager_comments: str | None            — free-text comment, or None.
        food_on_time: bool | None               — checklist: arrived on time?
        correct_count_received: bool | None     — checklist: correct meal count?
        correct_dietary_delivered: bool | None  — checklist: dietary-safe meals present?
        food_temperature_ok: bool | None        — checklist: food at right temperature?
        visibly_wrong: bool | None              — checklist: packaging/presentation wrong?
        meals_left: int | None                  — how many meals were uncollected.
        kids_who_didnt_eat: str | None          — free-text names of non-eaters.
        tutor_ratings: list[int|None]           — per-order-line tutor ratings (None = blank).
        student_avg: float | None               — mean of non-null tutor ratings, None if no data.

    If no order exists for (session_slot_id, session_date), all fields return
    None/empty — surfaced to the agent as missing-feedback data, not silently dropped.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM orders WHERE session_slot_id = %s AND session_date = %s",
                (session_slot_id, session_date),
            )
            row = cur.fetchone()
            if row is None:
                return {
                    "manager_rating": None,
                    "manager_comments": None,
                    "food_on_time": None,
                    "correct_count_received": None,
                    "correct_dietary_delivered": None,
                    "food_temperature_ok": None,
                    "visibly_wrong": None,
                    "meals_left": None,
                    "kids_who_didnt_eat": None,
                    "tutor_ratings": [],
                    "student_avg": None,
                }
            order_id = row[0]

            # Manager feedback: source='manager', one row per order.
            cur.execute(
                """
                SELECT rating, comment,
                       food_on_time, correct_count_received, correct_dietary_delivered,
                       food_temperature_ok, visibly_wrong, meals_left, kids_who_didnt_eat
                FROM feedback
                WHERE order_id = %s AND source = 'manager'
                """,
                (order_id,),
            )
            mgr_row = cur.fetchone()

            if mgr_row:
                (manager_rating, manager_comments,
                 food_on_time, correct_count_received, correct_dietary_delivered,
                 food_temperature_ok, visibly_wrong, meals_left, kids_who_didnt_eat) = mgr_row
            else:
                (manager_rating, manager_comments,
                 food_on_time, correct_count_received, correct_dietary_delivered,
                 food_temperature_ok, visibly_wrong, meals_left, kids_who_didnt_eat) = (
                    None, None, None, None, None, None, None, None, None
                )

            # Tutor feedback: source='tutor', attached to order_lines in this order.
            cur.execute(
                """
                SELECT f.rating
                FROM feedback f
                JOIN order_lines ol ON ol.id = f.order_line_id
                WHERE ol.order_id = %s AND f.source = 'tutor'
                ORDER BY f.id
                """,
                (order_id,),
            )
            tutor_rows = cur.fetchall()

    tutor_ratings: list[int | None] = [r[0] for r in tutor_rows]
    non_null = [r for r in tutor_ratings if r is not None]
    student_avg = sum(non_null) / len(non_null) if non_null else None

    return {
        "manager_rating":            manager_rating,
        "manager_comments":          manager_comments,
        "food_on_time":              food_on_time,
        "correct_count_received":    correct_count_received,
        "correct_dietary_delivered": correct_dietary_delivered,
        "food_temperature_ok":       food_temperature_ok,
        "visibly_wrong":             visibly_wrong,
        "meals_left":                meals_left,
        "kids_who_didnt_eat":        kids_who_didnt_eat,
        "tutor_ratings":             tutor_ratings,
        "student_avg":               student_avg,
    }


def compute_rolling_mean(
    caterer_id: int,
    weeks: int = 4,
    as_of: datetime | None = None,
) -> float | None:
    """
    Unweighted mean of all non-null feedback ratings (tutor + manager) for this
    caterer in the `weeks`-week window ending at `as_of` (default: now Brisbane).

    NULL ratings (= "rater did not fill in") are excluded from both the count
    and the average: the SQL filter is `AND rating IS NOT NULL`, so `len(ratings)`
    and the sum both operate only on submitted values.

    V4-OPT-04: caterer_id is denormalised onto feedback — no joins needed.
    Returns None if fewer than 3 non-null ratings exist (insufficient data).

    `as_of` is pinnable for deterministic tests and demo recording; defaults to
    `datetime.now(TZ)` so production calls need no argument.
    """
    if as_of is None:
        as_of = datetime.now(tz=TZ)
    since = as_of - timedelta(weeks=weeks)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rating
                FROM feedback
                WHERE caterer_id = %s
                  AND submitted_at >= %s
                  AND rating IS NOT NULL
                """,
                (caterer_id, since),
            )
            rows = cur.fetchall()

    ratings = [r[0] for r in rows]
    if len(ratings) < 3:
        return None
    return sum(ratings) / len(ratings)


def get_feedback_since(since_timestamp: datetime) -> list[dict]:
    """
    All feedback rows submitted strictly after since_timestamp.

    Joins through orders (and order_lines for tutor-source rows) to include
    session_slot_id and session_date in each returned dict.

    Returns list of dicts with:
        id, source, caterer_id, rating, submitted_at,
        session_slot_id, session_date
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    f.id,
                    f.source,
                    f.caterer_id,
                    f.rating,
                    f.submitted_at,
                    COALESCE(o_mgr.session_slot_id, o_tut.session_slot_id) AS session_slot_id,
                    COALESCE(o_mgr.session_date,    o_tut.session_date)    AS session_date
                FROM feedback f
                LEFT JOIN orders      o_mgr ON f.order_id       = o_mgr.id
                LEFT JOIN order_lines ol    ON f.order_line_id  = ol.id
                LEFT JOIN orders      o_tut ON ol.order_id      = o_tut.id
                WHERE f.submitted_at > %s
                ORDER BY f.submitted_at
                """,
                (since_timestamp,),
            )
            rows = cur.fetchall()

    return [
        {
            "id":              row[0],
            "source":          row[1],
            "caterer_id":      row[2],
            "rating":          row[3],
            "submitted_at":    row[4],
            "session_slot_id": row[5],
            "session_date":    row[6],
        }
        for row in rows
    ]
