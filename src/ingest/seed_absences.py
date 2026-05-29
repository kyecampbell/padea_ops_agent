#!/usr/bin/env python3
"""
seed_absences.py
10 absences for the demo week (1–4 May 2026) from data/source/absences.pdf.
Absences link to specific enrolments via (student_name, school_name).
received_at set to session date at 14:00 AEST (plausible same-day notification).
"""
import datetime
from zoneinfo import ZoneInfo
from src.ingest.db import get_conn

AEST = ZoneInfo("Australia/Brisbane")

# (absence_date, school_name, student_name)
ABSENCES = [
    (datetime.date(2026, 5, 1), "Loreto College",                  "Holly Hill"),
    (datetime.date(2026, 5, 1), "Loreto College",                  "Imogen Evans"),
    (datetime.date(2026, 5, 2), "Moreton Bay Boys' College",       "Noah Baker"),
    (datetime.date(2026, 5, 2), "John Paul College",               "Christina Hu"),
    (datetime.date(2026, 5, 2), "John Paul College",               "Nathan Smith"),
    (datetime.date(2026, 5, 2), "Indooroopilly State High School", "Charlie Morris"),
    (datetime.date(2026, 5, 2), "Indooroopilly State High School", "Jack Carter"),
    (datetime.date(2026, 5, 2), "Indooroopilly State High School", "Charlie Mitchell"),
    (datetime.date(2026, 5, 3), "Cannon Hill Anglican College",    "Henry Cook"),
    (datetime.date(2026, 5, 4), "MacGregor State High School",     "Rose Smith"),
]


def run() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            inserted = 0
            not_found = []

            for absence_date, school_name, student_name in ABSENCES:
                # look up enrolment_id
                cur.execute(
                    """
                    SELECT e.id FROM enrolments e
                    JOIN schools s ON s.id = e.school_id
                    WHERE s.name = %s AND e.student_name = %s
                    """,
                    (school_name, student_name),
                )
                row = cur.fetchone()
                if not row:
                    not_found.append((absence_date, school_name, student_name))
                    continue
                enrolment_id = row[0]

                received_at = datetime.datetime(
                    absence_date.year, absence_date.month, absence_date.day,
                    14, 0, 0, tzinfo=AEST
                )

                cur.execute(
                    """
                    INSERT INTO absences (enrolment_id, absence_date, received_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (enrolment_id, absence_date) DO NOTHING
                    """,
                    (enrolment_id, absence_date, received_at),
                )
                if cur.rowcount:
                    inserted += 1

            conn.commit()

            cur.execute("SELECT COUNT(*) FROM absences")
            total = cur.fetchone()[0]
            print(f"absences: {total} total ({inserted} inserted)")

            if not_found:
                print(f"\nWARNING: {len(not_found)} enrolments not found:")
                for d, school, student in not_found:
                    print(f"  {d}  {school}  {student}")

            cur.execute(
                """
                SELECT a.absence_date, sc.name, e.student_name
                FROM absences a
                JOIN enrolments e ON e.id = a.enrolment_id
                JOIN schools sc ON sc.id = e.school_id
                ORDER BY a.absence_date, sc.name
                """
            )
            print("\nAbsences loaded:")
            for date, school, student in cur.fetchall():
                print(f"  {date}  {school:<45} {student}")


if __name__ == "__main__":
    run()
