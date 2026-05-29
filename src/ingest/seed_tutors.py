#!/usr/bin/env python3
"""
seed_tutors.py
7 session managers from data/source/sessions.xlsx.
Real names and mobiles; emails generated as firstname@padea.com.au.

Schema note: tutors are first-class per V3-IL-01. The is_manager/is_tutor
flags live on session_tutor_assignments, not on the tutors table itself.
All 7 are session managers; none are seeded as non-manager tutors (demo
simplification — full roster deferred, ~5 students/tutor noted for future).
"""
from src.ingest.db import get_conn

DEMO_EMAIL  = "kyec898@gmail.com"
DEMO_MOBILE = "0458971565"

# (name, mobile, generated_email)
TUTORS = [
    ("Triet",   DEMO_MOBILE, DEMO_EMAIL),
    ("Jessie",  DEMO_MOBILE, DEMO_EMAIL),
    ("Liam",    DEMO_MOBILE, DEMO_EMAIL),
    ("Lucian",  DEMO_MOBILE, DEMO_EMAIL),
    ("Ethan",   DEMO_MOBILE, DEMO_EMAIL),
    ("Claire",  DEMO_MOBILE, DEMO_EMAIL),
    ("Camilo",  DEMO_MOBILE, DEMO_EMAIL),
]


def run() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            inserted = 0
            for name, mobile, email in TUTORS:
                cur.execute("SELECT id FROM tutors WHERE email = %s", (email,))
                if cur.fetchone():
                    continue
                cur.execute(
                    "INSERT INTO tutors (name, email, mobile) VALUES (%s, %s, %s)",
                    (name, email, mobile),
                )
                inserted += 1
            conn.commit()

            cur.execute("SELECT id, name, email, mobile FROM tutors ORDER BY id")
            rows = cur.fetchall()
            print(f"tutors: {len(rows)} total rows ({inserted} inserted)")
            for r in rows:
                print(f"  {r[0]}  {r[1]:<10}  {r[2]:<30}  {r[3]}")


if __name__ == "__main__":
    run()
