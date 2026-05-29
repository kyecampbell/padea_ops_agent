#!/usr/bin/env python3
"""
seed_schools.py
6 schools from data/source/sessions.xlsx.
Postcodes: real QLD postcodes for each school location.
current_caterer_id set to NULL here; seed_caterers.py fills it in.
"""
from src.ingest.db import get_conn

# (name, building, postcode)
SCHOOLS = [
    ("Moreton Bay Boys' College",       "Library",       "4165"),  # Victoria Point
    ("John Paul College",               "G Centre",      "4127"),  # Daisy Hill
    ("MacGregor State High School",     "Library",       "4109"),  # MacGregor
    ("Indooroopilly State High School", "X Block",       "4068"),  # Indooroopilly
    ("Loreto College",                  "Ella Building", "4151"),  # Coorparoo
    ("Cannon Hill Anglican College",    "E Centre",      "4170"),  # Cannon Hill
]


def run() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            inserted = 0
            for name, building, postcode in SCHOOLS:
                cur.execute("SELECT id FROM schools WHERE name = %s", (name,))
                if cur.fetchone():
                    continue
                cur.execute(
                    "INSERT INTO schools (name, building, postcode) VALUES (%s, %s, %s)",
                    (name, building, postcode),
                )
                inserted += 1
            conn.commit()

            cur.execute("SELECT id, name, postcode FROM schools ORDER BY id")
            rows = cur.fetchall()
            print(f"schools: {len(rows)} total rows ({inserted} inserted)")
            for r in rows:
                print(f"  {r[0]}  {r[1]}  ({r[2]})")


if __name__ == "__main__":
    run()
