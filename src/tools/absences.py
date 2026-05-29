"""
src/tools/absences.py
Absence and exclusion tools.

Writes: upsert_absence (calls conn.commit explicitly).
Reads:  get_absence, get_exclusions, get_year_level_exclusions (no commit).
"""
from __future__ import annotations

from datetime import date

from src.ingest.db import get_conn


def get_absence(enrolment_id: int, absence_date: date) -> dict | None:
    """
    Return the absence row for (enrolment_id, absence_date), or None.

    Walk-back in V4 = deletion of the row. No walked-back absence rows exist,
    so presence of a row means the absence is active.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, enrolment_id, absence_date, received_at,
                       source_email_filename, source_email_message_id, notes
                FROM absences
                WHERE enrolment_id = %s AND absence_date = %s
                """,
                (enrolment_id, absence_date),
            )
            row = cur.fetchone()

    if row is None:
        return None

    return {
        "id":                       row[0],
        "enrolment_id":             row[1],
        "absence_date":             row[2],
        "received_at":              row[3],
        "source_email_filename":    row[4],
        "source_email_message_id":  row[5],
        "notes":                    row[6],
    }


def upsert_absence(
    enrolment_id: int,
    absence_date: date,
    source_email_message_id: str | None = None,
    notes: str | None = None,
) -> int:
    """
    Insert an absence for (enrolment_id, absence_date). Returns absence_id.

    ON CONFLICT DO NOTHING — first notification is the record of truth. A second
    email about the same absence is silently ignored; the original received_at and
    source_email_message_id are preserved intact. Walk-back = deletion, not update.

    Targets the UNIQUE (enrolment_id, absence_date) constraint. When DO NOTHING
    fires, RETURNING yields no row, so we fetch the existing id explicitly.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO absences (enrolment_id, absence_date, source_email_message_id, notes)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (enrolment_id, absence_date)
                DO NOTHING
                RETURNING id
                """,
                (enrolment_id, absence_date, source_email_message_id, notes),
            )
            row = cur.fetchone()
            if row is None:
                # Conflict fired — row already exists; fetch the existing id
                cur.execute(
                    "SELECT id FROM absences WHERE enrolment_id = %s AND absence_date = %s",
                    (enrolment_id, absence_date),
                )
                row = cur.fetchone()
            absence_id: int = row[0]
        conn.commit()
    return absence_id


def get_exclusions(school_id: int, session_date: date) -> list[dict]:
    """
    Return all exclusion rows covering this school on session_date.

    Includes full-school (year_levels_excluded=[]), year-level (year_levels_excluded
    non-empty), and enrolment-specific rows. The agent inspects year_levels_excluded
    to determine scope — an empty list means all year levels are excluded.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, school_id, enrolment_id, reason,
                       start_date, end_date, year_levels_excluded
                FROM exclusions
                WHERE school_id = %s
                  AND start_date <= %s
                  AND end_date   >= %s
                ORDER BY id
                """,
                (school_id, session_date, session_date),
            )
            rows = cur.fetchall()

    return [
        {
            "id":                   row[0],
            "school_id":            row[1],
            "enrolment_id":         row[2],
            "reason":               row[3],
            "start_date":           row[4],
            "end_date":             row[5],
            "year_levels_excluded": row[6],   # list[int]; [] = whole school
        }
        for row in rows
    ]


def get_year_level_exclusions(school_id: int, session_date: date) -> list[dict]:
    """
    Return school-level exclusions that target specific year levels on session_date.

    Filters to enrolment_id IS NULL and year_levels_excluded != '{}' so only
    school-scoped year-level rows are returned (full-school and per-student rows
    are excluded). V4 uses an integer[] column — no text-parsing of reason.

    Returns list of {id, reason, excluded_year_levels: list[int]}.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, reason, year_levels_excluded
                FROM exclusions
                WHERE school_id           = %s
                  AND start_date         <= %s
                  AND end_date           >= %s
                  AND enrolment_id        IS NULL
                  AND year_levels_excluded != '{}'
                ORDER BY id
                """,
                (school_id, session_date, session_date),
            )
            rows = cur.fetchall()

    return [
        {
            "id":                   row[0],
            "reason":               row[1],
            "excluded_year_levels": row[2],   # list[int]
        }
        for row in rows
    ]
