#!/usr/bin/env python3
"""
seed_enrolment_session_slots.py
Links every enrolment to its session_slot via the V4-OPT-07 junction table.

Mapping logic:
  Each students.xlsx sheet encodes both school and day-of-week in its name
  (e.g. "ISHS - Monday" → ISHS school, day_of_week=1). This script reads
  that mapping, looks up the matching session_slot, and inserts one junction
  row per (enrolment, session_slot) pair.

Expected result: 320 rows — one per enrolment, because each student appears
on exactly one sheet (one cohort per student in the source data).

joined_date defaults to the V4 term start date (2026-04-21) to match the
enrolment current_period_start_date set in seed_enrolments.py.
"""
import datetime
from pathlib import Path
import openpyxl
from src.ingest.db import get_conn

STUDENTS_XLSX = Path("data/source/students.xlsx")
TERM_START    = datetime.date(2026, 4, 21)

# sheet_name → (school_name, day_of_week)   day_of_week: 1=Mon … 4=Thu (ISO)
SHEET_TO_SLOT: dict[str, tuple[str, int]] = {
    "MBBC":            ("Moreton Bay Boys' College",        2),
    "JPC - Tuesday":   ("John Paul College",                2),
    "JPC - Wednesday": ("John Paul College",                3),
    "MSHS":            ("MacGregor State High School",      4),
    "ISHS - Monday":   ("Indooroopilly State High School",  1),
    "ISHS - Tuesday":  ("Indooroopilly State High School",  2),
    "ISHS - Thursday": ("Indooroopilly State High School",  4),
    "LC - Monday":     ("Loreto College",                   1),
    "LC - Tuesday":    ("Loreto College",                   2),
    "CHAC - Monday":   ("Cannon Hill Anglican College",     1),
    "CHAC - Wednesday":("Cannon Hill Anglican College",     3),
}


def run() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            # ── lookup maps ──────────────────────────────────────────────────
            cur.execute("SELECT name, id FROM schools")
            school_id: dict[str, int] = {name: sid for name, sid in cur.fetchall()}

            cur.execute("SELECT school_id, day_of_week, id FROM session_slots")
            # (school_id, day_of_week) → slot_id
            slot_id: dict[tuple[int, int], int] = {
                (sid, dow): slot for sid, dow, slot in cur.fetchall()
            }

            wb = openpyxl.load_workbook(STUDENTS_XLSX, data_only=True)
            inserted = 0
            skipped  = 0

            for sheet_name, (school_name, dow) in SHEET_TO_SLOT.items():
                sid   = school_id[school_name]
                sslot = slot_id.get((sid, dow))
                if sslot is None:
                    raise RuntimeError(
                        f"No session_slot found for {school_name!r} day_of_week={dow}"
                    )

                ws = wb[sheet_name]
                for row in ws.iter_rows(min_row=4, values_only=True):
                    student_name = row[0]
                    if not student_name:
                        continue

                    cur.execute(
                        "SELECT id FROM enrolments WHERE school_id = %s AND student_name = %s",
                        (sid, student_name),
                    )
                    enrolment_row = cur.fetchone()
                    if enrolment_row is None:
                        print(f"  WARNING: no enrolment for {student_name!r} @ {school_name}")
                        skipped += 1
                        continue

                    enrolment_id = enrolment_row[0]
                    cur.execute(
                        """
                        INSERT INTO enrolment_session_slots
                            (enrolment_id, session_slot_id, joined_date)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (enrolment_id, sslot, TERM_START),
                    )
                    if cur.rowcount:
                        inserted += 1
                    else:
                        skipped += 1

            conn.commit()

            cur.execute("SELECT COUNT(*) FROM enrolment_session_slots")
            total = cur.fetchone()[0]
            print(f"enrolment_session_slots:   {total} total ({inserted} inserted, {skipped} skipped/duplicate)")

            # per-slot breakdown
            cur.execute(
                """
                SELECT sc.name, ss.day_of_week, COUNT(ess.enrolment_id)
                FROM session_slots ss
                JOIN schools sc ON sc.id = ss.school_id
                LEFT JOIN enrolment_session_slots ess ON ess.session_slot_id = ss.id
                GROUP BY sc.name, ss.day_of_week, ss.id
                ORDER BY sc.name, ss.day_of_week
                """
            )
            days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
            print("\nEnrolments per session_slot:")
            for school, dow, count in cur.fetchall():
                print(f"  {days[dow-1]}  {school:<45}  {count} students")


if __name__ == "__main__":
    run()
