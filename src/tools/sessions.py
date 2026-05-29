"""
src/tools/sessions.py
Session scheduling tools — read-only, no writes.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from config.settings import settings
from src.ingest.db import get_conn

BRISBANE = ZoneInfo("Australia/Brisbane")


def get_sessions_needing_orders(
    as_of: datetime,
    window_hours: float = 1.0,
) -> list[dict]:
    """
    Return session slots whose T-72h ordering mark falls within
    [as_of - window_hours, as_of + window_hours] and that have no order yet.

    Algorithm:
      The T-72h mark for a session = session_start_datetime - order_hours_before_session.
      We want:  as_of - window_hours  <=  session_start - H  <=  as_of + window_hours
      Rearranged: target_low = as_of + H - window   target_high = as_of + H + window
      Then scan each active session_slot for a date in [target_low.date - 1, target_high.date + 1]
      matching day_of_week, build the aware datetime, test it against the window, and
      exclude any (slot, date) that already has an orders row.

    as_of may be naive (treated as Brisbane local) or timezone-aware.

    Returns list of dicts:
        session_slot_id, session_date, school_id, caterer_id, session_start_datetime
    """
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=BRISBANE)

    H = settings.order_hours_before_session
    target_low = as_of + timedelta(hours=H - window_hours)
    target_high = as_of + timedelta(hours=H + window_hours)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ss.id, ss.school_id, ss.day_of_week, ss.start_time,
                       sc.current_caterer_id
                FROM session_slots ss
                JOIN schools sc ON sc.id = ss.school_id
                WHERE ss.active = true
                """
            )
            slots = cur.fetchall()

            result: list[dict] = []
            for slot_id, school_id, dow, start_time, caterer_id in slots:
                # Precondition: window_hours must be << 24h. The -1..+2 date scan finds
                # at most one matching weekday per slot. Callers must not pass window_hours >= 24.
                # Scan ±1 day around target_low to catch the one matching weekday.
                for offset in range(-1, 3):
                    candidate_date: date = target_low.date() + timedelta(days=offset)
                    if candidate_date.isoweekday() != dow:
                        continue

                    session_dt = datetime.combine(
                        candidate_date, start_time, tzinfo=BRISBANE
                    )
                    if not (target_low <= session_dt <= target_high):
                        continue

                    cur.execute(
                        "SELECT 1 FROM orders WHERE session_slot_id = %s AND session_date = %s",
                        (slot_id, candidate_date),
                    )
                    if cur.fetchone() is not None:
                        continue

                    result.append({
                        "session_slot_id":       slot_id,
                        "session_date":          candidate_date,
                        "school_id":             school_id,
                        "caterer_id":            caterer_id,
                        "session_start_datetime": session_dt,
                    })

    return result


def get_session_slot(session_slot_id: int) -> dict:
    """
    Return the full session_slots row for the given ID.

    Raises ValueError if the slot does not exist.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, school_id, day_of_week, start_time, dinner_time,
                       end_time, room, active, created_at, updated_at
                FROM session_slots
                WHERE id = %s
                """,
                (session_slot_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise ValueError(f"session_slot_id {session_slot_id} not found")

    return {
        "id":          row[0],
        "school_id":   row[1],
        "day_of_week": row[2],
        "start_time":  row[3],
        "dinner_time": row[4],
        "end_time":    row[5],
        "room":        row[6],
        "active":      row[7],
        "created_at":  row[8],
        "updated_at":  row[9],
    }
