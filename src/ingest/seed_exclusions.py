#!/usr/bin/env python3
"""
seed_exclusions.py
3 session exclusions for the demo week from data/source/exclusions.pdf.

Exclusion One:   ISHS 04/05 — whole session, all year levels (Open Day)
Exclusion Two:   LC   02/05 — whole session, all year levels (Parent-Teacher Interviews)
Exclusion Three: CHAC 03/05 — PARTIAL, Years 10 and 12 only (School Camp)
                             Year 11 still attends.

The V4 exclusions table supports year-level partials via one row per excluded
year-level per date (school_id set; enrolment_id NULL = applies to all enrolments
in those year levels at that school). The exclusions tool at order composition
must filter enrolments by year_level where the reason indicates a partial exclusion.

For whole-session exclusions (Exclusions 1 & 2): one row with school_id, date range,
and reason. For the partial exclusion (Exclusion 3): one row per excluded year level
(Yr10 and Yr12 = 2 rows). The reason field carries enough context for the agent to
distinguish whole vs partial.

NOTE: The exclusions table schema uses start_date/end_date (date range). For single-day
exclusions, start_date = end_date.
"""
import datetime
from src.ingest.db import get_conn

# Each entry: (school_name, start_date, end_date, reason, year_levels_excluded_or_None)
# year_levels=None → whole school; year_levels=[10,12] → partial
EXCLUSIONS = [
    (
        "Indooroopilly State High School",
        datetime.date(2026, 5, 4),
        datetime.date(2026, 5, 4),
        "Open Day — whole session cancelled, all year levels",
        None,                # whole session
    ),
    (
        "Loreto College",
        datetime.date(2026, 5, 2),
        datetime.date(2026, 5, 2),
        "Parent-Teacher Interviews — whole session cancelled, all year levels",
        None,                # whole session
    ),
    (
        "Cannon Hill Anglican College",
        datetime.date(2026, 5, 3),
        datetime.date(2026, 5, 3),
        "School Camp — Year 10 excluded",
        [10],
    ),
    (
        "Cannon Hill Anglican College",
        datetime.date(2026, 5, 3),
        datetime.date(2026, 5, 3),
        "School Camp — Year 12 excluded",
        [12],
    ),
]


def run() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, id FROM schools")
            school_id: dict[str, int] = {name: sid for name, sid in cur.fetchall()}

            inserted = 0
            for school_name, start_date, end_date, reason, year_levels in EXCLUSIONS:
                sid = school_id[school_name]

                # idempotency: skip if same (school, start_date, reason) already exists
                cur.execute(
                    """
                    SELECT id FROM exclusions
                    WHERE school_id = %s AND start_date = %s AND reason = %s
                    """,
                    (sid, start_date, reason),
                )
                if cur.fetchone():
                    continue

                cur.execute(
                    """
                    INSERT INTO exclusions (school_id, start_date, end_date, reason, year_levels_excluded)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (sid, start_date, end_date, reason, year_levels or []),
                )
                inserted += 1

            conn.commit()

            cur.execute("SELECT COUNT(*) FROM exclusions")
            total = cur.fetchone()[0]
            print(f"exclusions: {total} total ({inserted} inserted)")

            cur.execute(
                """
                SELECT e.start_date, sc.name, e.reason
                FROM exclusions e
                JOIN schools sc ON sc.id = e.school_id
                ORDER BY e.start_date, sc.name
                """
            )
            print("\nExclusions loaded:")
            for date, school, reason in cur.fetchall():
                print(f"  {date}  {school:<45}  {reason}")


if __name__ == "__main__":
    run()
