#!/usr/bin/env python3
"""
seed_upcoming_absences.py — DUMMY DATA
Seeds ~10 upcoming student absences across the next two weeks of sessions.

Week of Jun 2–5:   9 absences across 7 sessions
Week of Jun 9–12:  1 absence (camp week — only non-Year-10 absence for ISHS Mon)

Absences are keyed by (student_name, school_id, absence_date).  The script
looks up the enrolment_id at run time so it remains correct if re-seeded.

FAKE DATA: These absences are entirely fabricated for demo purposes.
They will cause the agent to demonstrate the absence-handling and
dietary-override rules during a live run.
"""
import datetime

from src.ingest.db import get_conn

# (school_id, student_name, session_slot_id, absence_date)
# school_id is needed to disambiguate same-name students at different schools.
UPCOMING_ABSENCES = [
    # ── Week of Jun 2 ────────────────────────────────────────────────────────
    # ISHS Mon Jun 2
    (4, "Aria Lewis",         5,  datetime.date(2026, 6, 2)),
    (4, "Charlie Turner",     5,  datetime.date(2026, 6, 2)),
    # LC Mon Jun 2
    (5, "Amelia Wright",      8,  datetime.date(2026, 6, 2)),
    # CHAC Mon Jun 2
    (6, "Andy Ma",            10, datetime.date(2026, 6, 2)),
    # JPC Tue Jun 3
    (2, "Amy Liu",            2,  datetime.date(2026, 6, 3)),
    # ISHS Tue Jun 3
    (4, "Amelia Williams",    6,  datetime.date(2026, 6, 3)),
    # JPC Wed Jun 4
    (2, "Aanya Desai",        3,  datetime.date(2026, 6, 4)),
    # MSHS Thu Jun 5
    (3, "Aisha Ibrahim",      4,  datetime.date(2026, 6, 5)),
    # CHAC Wed Jun 4
    (6, "Annabelle Phillips", 11, datetime.date(2026, 6, 4)),
    # ── Week of Jun 9 (ISHS camp week) ───────────────────────────────────────
    # ISHS Mon Jun 9 — non-Year-10 absence (Year 10 cohort is excluded by school camp)
    (4, "Charlie Turner",     5,  datetime.date(2026, 6, 9)),
    # MBBC Tue Jun 10
    (1, "Bailey Collins",     1,  datetime.date(2026, 6, 10)),
]


def run() -> None:
    inserted = 0
    not_found = 0
    skipped = 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            for school_id, student_name, _slot_id, absence_date in UPCOMING_ABSENCES:
                # Resolve enrolment_id
                cur.execute(
                    "SELECT id FROM enrolments WHERE school_id = %s AND student_name = %s",
                    (school_id, student_name),
                )
                row = cur.fetchone()
                if row is None:
                    print(f"  WARNING: no enrolment for {student_name!r} at school {school_id}")
                    not_found += 1
                    continue

                enrolment_id = row[0]

                # Idempotency check
                cur.execute(
                    "SELECT id FROM absences WHERE enrolment_id = %s AND absence_date = %s",
                    (enrolment_id, absence_date),
                )
                if cur.fetchone():
                    skipped += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO absences (enrolment_id, absence_date)
                    VALUES (%s, %s)
                    """,
                    (enrolment_id, absence_date),
                )
                inserted += 1

            conn.commit()

    print(f"absences inserted: {inserted}  (skipped: {skipped}, not found: {not_found})")
    print(f"  Week of Jun 2–5:  9 absences across ISHS/LC/CHAC/JPC/MSHS")
    print(f"  Week of Jun 9–12: 2 absences (ISHS Mon non-Yr10 + MBBC Tue)")


if __name__ == "__main__":
    run()
