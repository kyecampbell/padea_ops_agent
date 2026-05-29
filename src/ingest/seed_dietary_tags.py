#!/usr/bin/env python3
"""
seed_dietary_tags.py
Add no_beef and no_red_meat to the 9 tags already seeded by v4_schema.sql.

Schema-seeded tags (already present):
  no_pork, no_seafood, no_nuts, no_dairy, halal, vegetarian, vegan, gluten_free, mild_only

New tags added here (required by students.xlsx source data):
  no_beef     — students with "No Beef" requirement
  no_red_meat — students with "No Red Meat" requirement (beef + lamb + pork)
"""
from src.ingest.db import get_conn

EXTRA_TAGS = [
    ("no_beef",     "No beef",     "Beef-free"),
    ("no_red_meat", "No red meat", "Free of beef, lamb, and pork"),
]

def run() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            for name, label, description in EXTRA_TAGS:
                cur.execute(
                    """
                    INSERT INTO dietary_tags (name, label, description)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO NOTHING
                    """,
                    (name, label, description),
                )
            conn.commit()

            cur.execute("SELECT id, name, label FROM dietary_tags ORDER BY id")
            rows = cur.fetchall()
            print(f"dietary_tags: {len(rows)} total rows")
            for r in rows:
                print(f"  {r[0]:3d}  {r[1]:<20}  {r[2]}")


if __name__ == "__main__":
    run()
