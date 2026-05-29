#!/usr/bin/env python3
"""
seed_caterers.py
4 caterers from data/source/caterers.xlsx + data/source/caterer-contacts.pdf.

Delivery fee decisions (data_inventory.md):
  - Lakehouse: $0/delivery
  - Terrific:  $30/school/trip → store 3000 cents (per-school fee; agent multiplies by school count)
  - Kenko:     $10/school/trip → store 1000 cents (per-school fee)
  - GyG:       $0 (D9: built into item cost per operator direction)

GST:
  - Lakehouse, Terrific: price excludes GST (price_includes_gst=False)
  - Kenko, GyG: price includes GST (price_includes_gst=True)

Contact stored: primary order contact only (contact_email, contact_phone=None — no phone in source).
CC contacts (Terrific's James Chern does NOT want CC; GyG's Medium Giraffe DOES want CC)
are documented here as comments; the agent system_prompt carries the CC rules.
  - Terrific CC: none (James Chern explicitly does not want CC)
  - GyG CC:      dylan@padea.com.au (Medium Giraffe, chef)

After inserting caterers, schools.current_caterer_id is updated.
"""
from src.ingest.db import get_conn

DEMO_EMAIL = "kyec898@gmail.com"

# (name, contact_email, home_postcode, max_delivery_km,
#  delivery_fee_cents, price_includes_gst, gst_rate_percent,
#  moq_4, moq_5, moq_6)
CATERERS = [
    (
        "Lakehouse Victoria Point",
        DEMO_EMAIL,
        "4165",   # Victoria Point
        50,
        0,        # $0 delivery
        False,    # price excl GST
        10.0,
        15, 20, 25,
    ),
    (
        "Terrific Noodles",
        DEMO_EMAIL,
        "4101",   # South Brisbane area
        50,
        3000,     # $30/school/trip — agent multiplies by school count per delivery run
        False,    # price excl GST
        10.0,
        10, 20, 30,
    ),
    (
        "Kenko Sushi House",
        DEMO_EMAIL,
        "4068",   # Indooroopilly area
        50,
        1000,     # $10/school/trip
        True,     # price incl GST
        10.0,
        35, 40, 45,
    ),
    (
        "Guzman y Gomez",
        DEMO_EMAIL,
        "4000",   # Central Brisbane
        50,
        0,        # $0 (D9: built into item cost)
        True,     # price incl GST
        10.0,
        20, 25, 30,
    ),
]

# school_name → caterer_name  (current assignments from caterer-contacts.pdf)
SCHOOL_CATERER = {
    "Moreton Bay Boys' College":       "Lakehouse Victoria Point",
    "John Paul College":               "Terrific Noodles",
    "MacGregor State High School":     "Terrific Noodles",
    "Indooroopilly State High School": "Kenko Sushi House",
    "Loreto College":                  "Guzman y Gomez",
    "Cannon Hill Anglican College":    "Guzman y Gomez",
}


def run() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            # ── insert caterers ──────────────────────────────────────────────
            inserted = 0
            for (name, contact_email, home_postcode, max_delivery_km,
                 delivery_fee_cents, price_includes_gst, gst_rate_percent,
                 moq_4, moq_5, moq_6) in CATERERS:
                cur.execute("SELECT id FROM caterers WHERE name = %s", (name,))
                if cur.fetchone():
                    continue
                cur.execute(
                    """
                    INSERT INTO caterers
                        (name, contact_email, home_postcode, max_delivery_km,
                         delivery_fee_cents, price_includes_gst, gst_rate_percent,
                         moq_4_items, moq_5_items, moq_6_items)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (name, contact_email, home_postcode, max_delivery_km,
                     delivery_fee_cents, price_includes_gst, gst_rate_percent,
                     moq_4, moq_5, moq_6),
                )
                inserted += 1
            conn.commit()

            # ── build lookup maps ────────────────────────────────────────────
            cur.execute("SELECT id, name FROM caterers")
            caterer_id = {name: cid for cid, name in cur.fetchall()}

            cur.execute("SELECT id, name FROM schools")
            school_id = {name: sid for sid, name in cur.fetchall()}

            # ── update schools.current_caterer_id ────────────────────────────
            for school_name, caterer_name in SCHOOL_CATERER.items():
                cur.execute(
                    "UPDATE schools SET current_caterer_id = %s WHERE id = %s",
                    (caterer_id[caterer_name], school_id[school_name]),
                )
            conn.commit()

            cur.execute(
                """
                SELECT c.id, c.name, c.contact_email, c.delivery_fee_cents,
                       c.price_includes_gst, c.moq_4_items, c.moq_5_items, c.moq_6_items
                FROM caterers c ORDER BY c.id
                """
            )
            rows = cur.fetchall()
            print(f"caterers: {len(rows)} total rows ({inserted} inserted)")
            for r in rows:
                gst_flag = "incl" if r[4] else "excl"
                print(f"  {r[0]}  {r[1]:<30}  {r[2]:<40}  delivery={r[3]}c  GST={gst_flag}  MOQ={r[5]}/{r[6]}/{r[7]}")

            cur.execute(
                "SELECT s.name, c.name FROM schools s JOIN caterers c ON s.current_caterer_id = c.id ORDER BY s.id"
            )
            print("\nschool → caterer assignments:")
            for school, caterer in cur.fetchall():
                print(f"  {school:<45} → {caterer}")


if __name__ == "__main__":
    run()
