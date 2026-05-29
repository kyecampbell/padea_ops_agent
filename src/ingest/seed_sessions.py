#!/usr/bin/env python3
"""
seed_sessions.py
11 session_slots + 11 session_tutor_assignments from data/source/sessions.xlsx.

Sessions represent the RECURRING WEEKLY SCHEDULE (D2 — data_inventory.md).
Dates here are for the demo week (1–4 May 2026); session_slots store the
recurring (school, day_of_week) template. session_tutor_assignments carry
the specific date + manager assignment for the demo week.

room: set to the school's building name (only location info available in
source data; no room number recorded).

day_of_week encoding: 1=Mon, 2=Tue, 3=Wed, 4=Thu (Postgres ISO convention).
"""
import datetime
from src.ingest.db import get_conn

# (school_name, day_of_week, start_time, dinner_time, end_time,
#  session_date, manager_name)
SESSIONS = [
    ("Moreton Bay Boys' College",       2, "16:00", "17:30", "19:00",
     datetime.date(2026, 5, 2), "Triet"),
    ("John Paul College",               2, "16:30", "18:00", "19:30",
     datetime.date(2026, 5, 2), "Jessie"),
    ("John Paul College",               3, "16:30", "18:00", "19:30",
     datetime.date(2026, 5, 3), "Liam"),
    ("MacGregor State High School",     4, "15:15", "16:45", "18:15",
     datetime.date(2026, 5, 4), "Jessie"),
    ("Indooroopilly State High School", 1, "15:30", "17:00", "18:30",
     datetime.date(2026, 5, 1), "Lucian"),
    ("Indooroopilly State High School", 2, "15:30", "17:00", "18:30",
     datetime.date(2026, 5, 2), "Lucian"),
    ("Indooroopilly State High School", 4, "15:30", "17:00", "18:30",
     datetime.date(2026, 5, 4), "Ethan"),
    ("Loreto College",                  1, "15:30", "17:00", "18:30",
     datetime.date(2026, 5, 1), "Claire"),
    ("Loreto College",                  2, "15:30", "17:00", "18:30",
     datetime.date(2026, 5, 2), "Claire"),
    ("Cannon Hill Anglican College",    1, "15:30", "17:00", "18:30",
     datetime.date(2026, 5, 1), "Ethan"),
    ("Cannon Hill Anglican College",    3, "15:30", "17:00", "18:30",
     datetime.date(2026, 5, 3), "Camilo"),
]


def run() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            # ── lookup maps ──────────────────────────────────────────────────
            cur.execute("SELECT id, name, building FROM schools")
            school_rows = cur.fetchall()
            school_id   = {name: sid for sid, name, _ in school_rows}
            school_bldg = {name: bldg for _, name, bldg in school_rows}

            cur.execute("SELECT id, name FROM tutors")
            tutor_id = {name: tid for tid, name in cur.fetchall()}

            slots_inserted = 0
            assigns_inserted = 0

            for (school_name, dow, start_t, dinner_t, end_t,
                 session_date, manager_name) in SESSIONS:

                sid = school_id[school_name]
                room = school_bldg.get(school_name)

                # ── session_slot ─────────────────────────────────────────────
                cur.execute(
                    "SELECT id FROM session_slots WHERE school_id = %s AND day_of_week = %s",
                    (sid, dow),
                )
                row = cur.fetchone()
                if row:
                    slot_id = row[0]
                else:
                    cur.execute(
                        """
                        INSERT INTO session_slots
                            (school_id, day_of_week, start_time, dinner_time, end_time, room)
                        VALUES (%s, %s, %s::time, %s::time, %s::time, %s)
                        RETURNING id
                        """,
                        (sid, dow, start_t, dinner_t, end_t, room),
                    )
                    slot_id = cur.fetchone()[0]
                    slots_inserted += 1

                # ── session_tutor_assignment ─────────────────────────────────
                tid = tutor_id[manager_name]
                cur.execute(
                    """
                    SELECT id FROM session_tutor_assignments
                    WHERE session_slot_id = %s AND session_date = %s AND tutor_id = %s
                    """,
                    (slot_id, session_date, tid),
                )
                if not cur.fetchone():
                    cur.execute(
                        """
                        INSERT INTO session_tutor_assignments
                            (session_slot_id, session_date, tutor_id, is_manager, is_tutor)
                        VALUES (%s, %s, %s, true, true)
                        """,
                        (slot_id, session_date, tid),
                    )
                    assigns_inserted += 1

            conn.commit()

            cur.execute("SELECT COUNT(*) FROM session_slots")
            print(f"session_slots:             {cur.fetchone()[0]} total ({slots_inserted} inserted)")
            cur.execute("SELECT COUNT(*) FROM session_tutor_assignments")
            print(f"session_tutor_assignments: {cur.fetchone()[0]} total ({assigns_inserted} inserted)")

            cur.execute(
                """
                SELECT sc.name, ss.day_of_week, ss.start_time, ss.dinner_time,
                       sta.session_date, t.name
                FROM session_slots ss
                JOIN schools sc ON sc.id = ss.school_id
                JOIN session_tutor_assignments sta ON sta.session_slot_id = ss.id
                JOIN tutors t ON t.id = sta.tutor_id
                ORDER BY sta.session_date, ss.start_time
                """
            )
            print("\nSession schedule (demo week):")
            for school, dow, start, dinner, date, manager in cur.fetchall():
                days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
                print(f"  {date}  {days[dow-1]}  {str(start)[:5]}  dinner {str(dinner)[:5]}"
                      f"  {school:<45}  mgr: {manager}")


if __name__ == "__main__":
    run()
