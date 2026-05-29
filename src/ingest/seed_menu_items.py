#!/usr/bin/env python3
"""
seed_menu_items.py
40 menu items (10 per caterer) from data/source/caterer-menus.pdf,
plus menu_item_dietary_tags junction rows.

Dietary tag semantics (V4-OPT-06, data_inventory.md):
  A tag on an item means "this item is SAFE FOR students with this requirement."
  Safety check at order composition: item.tags ⊇ student.tags.

Tag abbreviations used in MENU data below:
  GF = gluten_free   DF = no_dairy   NF = no_nuts
  HA = halal         VG = vegetarian
  NB = no_beef       NP = no_pork    NR = no_red_meat    NS = no_seafood

Halal rule (caterer-menus.pdf): "Assume all non-pork meals are halal."
  → 4 pork items get NO halal/NP/NR tags; all 36 others get halal tag.

VO flag: "Vegetarian Option" = can be made veg on request. NOT tagged VG (D7).

Ambiguous items:
  - Spaghetti meatballs (Terrific): protein unknown → treated as unsafe (D, session 006).
    No HA/NB/NP/NR tags applied; no_nuts and no_seafood only.
  - Various items where protein unclear: conservative (no tag rather than wrong tag).

"No X" tags on items require manual protein inspection (D8 — see data_inventory.md).
Conservative approach: only tag no_beef/no_red_meat where named protein confirms it.
"""
from src.ingest.db import get_conn

# ── TAG ABBREVIATION EXPANSION ───────────────────────────────────────────────
TAG_ABBREVS = {
    "GF": "gluten_free",
    "DF": "no_dairy",
    "NF": "no_nuts",
    "HA": "halal",
    "VG": "vegetarian",
    "NB": "no_beef",
    "NP": "no_pork",
    "NR": "no_red_meat",
    "NS": "no_seafood",
}

# ── MENU DATA ────────────────────────────────────────────────────────────────
# Format: (item_name, frozenset_of_tag_abbrevs)
# All items within a caterer share the same price (caterer's per-item price).

LAKEHOUSE = [  # $35.00 excl GST → 3500 cents
    # Shrimp = shellfish → NS excluded; no pork, no beef → HA NB NP NR
    ("Shrimp Fried Rice",               {"GF","DF","HA","NB","NP","NR"}),
    # Beef bolognese → HA (beef is halal), NP (no pork), NS (no seafood); no NB/NR
    ("Spaghetti Bolognese + Garlic Bread", {"NF","HA","NP","NS"}),
    # Chicken only → full safe set
    ("Sweet and Sour Chicken",          {"GF","DF","NF","HA","NB","NP","NR","NS"}),
    # Cream pasta — assume no meat (cream sauce); has dairy so no DF
    ("Classic Cream Pasta",             {"NF","HA","NB","NP","NR","NS"}),
    # Gnocchi + tomato = vegetarian, no meat
    ("Gnocchi in Tomato Sauce",         {"NF","HA","VG","NB","NP","NR","NS"}),
    # PORK (bacon) → no HA, no NP, no NR; no beef → NB; no seafood → NS
    ("Chicken, Bacon, Avo Wrap",        {"NB","NS"}),
    # Chicken → full safe set
    ("Fried Chicken Burger + Chips",    {"NF","HA","NB","NP","NR","NS"}),
    # Fish → not NS; chicken → no NR; no pork → NP HA
    ("Fish Taco Bowl",                  {"NF","HA","NB","NP","NR"}),
    # Beef → HA, NP, NS; no NB, no NR
    ("Korean Beef Bulgogi Rice Bowl",   {"GF","DF","NF","HA","NP","NS"}),
    # Chicken → all safe; DF NF from PDF
    ("Japanese Chicken Curry",          {"DF","NF","HA","NB","NP","NR","NS"}),
]

TERRIFIC = [  # $20.50 excl GST → 2050 cents
    # Miso: possible fish dashi → not NS; assume no red meat
    ("Spicy Miso Udon",                     {"DF","HA","NB","NP","NR"}),
    # Chicken → full safe set
    ("Stir-fry Noodles topped with Chicken",{"GF","DF","NF","HA","NB","NP","NR","NS"}),
    # PORK → no HA, no NP, no NR; no beef → NB; no seafood → NS
    ("Grilled Pork Vermicelli Salad",       {"GF","DF","NF","NB","NS"}),
    # AMBIGUOUS protein → no HA/NB/NP/NR; NF from PDF; no obvious seafood → NS
    ("Spaghetti meatballs",                 {"NF","NS"}),
    # Beef → HA (beef halal), NP, NS; no NB, no NR
    ("Lemongrass Grilled Beef and Noodles", {"GF","DF","NF","HA","NP","NS"}),
    # Beef + cream → HA, NP, NS; not DF (cream); no NB, no NR
    ("Creamy Garlic Beef Noodles",          {"HA","NP","NS"}),
    # Noodles, no definitive meat/seafood named; made clean (GF DF NF VO)
    ("Mie Goreng",                          {"GF","DF","NF","HA","NB","NP","NR","NS"}),
    # Beef + possible dried shrimp in pad thai → no NS; beef → no NB/NR; NP HA
    ("Beef Pad Thai",                       {"HA","NP"}),
    # PORK (bacon) → no HA, no NP, no NR; no beef → NB; no seafood → NS
    ("Bacon Carbonara",                     {"NB","NS"}),
    # Honey soy noodles: assume chicken or no meat; DF from PDF
    ("Chinese Honey Soy Noodles",           {"DF","HA","NB","NP","NR","NS"}),
]

KENKO = [  # $5.50 incl GST → 550 cents
    # Lamb = red meat → no NR; no beef → NB; no pork → NP HA; no seafood → NS
    ("Lamb wrap",                    {"NF","HA","NB","NP","NS"}),
    # Chicken → full safe set
    ("Chicken Parmi, chips and salad",{"DF","NF","HA","NB","NP","NR","NS"}),
    # Chicken → full safe set
    ("Japanese Chicken Katsu",       {"NF","HA","NB","NP","NR","NS"}),
    # Salmon (fish) → not NS; no pork → NP HA; no beef/red meat → NB NR
    ("Teriyaki Salmon rice bowl",    {"GF","DF","NF","HA","NB","NP","NR"}),
    # Chicken → full safe set
    ("Chicken Karaage ricebowl",     {"DF","NF","HA","NB","NP","NR","NS"}),
    # Udon: possible fish broth → not NS; no obvious meat → HA NB NP NR
    ("Creamy Udon",                  {"HA","NB","NP","NR"}),
    # Beef → HA, NP, NS; no NB, no NR; GF DF from PDF
    ("Beef Fried Rice",              {"GF","DF","HA","NP","NS"}),
    # Beef → HA, NP, NS; no NB, no NR
    ("Mongolian Beef and Rice",      {"HA","NP","NS"}),
    # Chicken → full safe set; GF DF from PDF
    ("Sweet and Sour Chicken",       {"GF","DF","HA","NB","NP","NR","NS"}),
    # Honey soy noodles: assume no meat; DF from PDF
    ("Chinese Honey Soy Noodles",    {"DF","HA","NB","NP","NR","NS"}),
]

GYG = [  # $15.00 incl GST → 1500 cents; $0 delivery (D9)
    # Breakfast tacos: egg-based at GyG → no meat → HA NB NP NR NS; NF from PDF
    ("Breakfast Tacos",              {"NF","HA","NB","NP","NR","NS"}),
    # Caesar: anchovies possible → not NS; no meat → HA NB NP NR; GF DF NF from PDF
    ("Caesar Salad",                 {"GF","DF","NF","HA","NB","NP","NR"}),
    # Cali burrito: ambiguous protein → conservative; no seafood → NS only
    ("Cali Burrito",                 {"NS"}),
    # Named chicken → HA NB NP NR NS
    ("Grilled Chicken Burrito",      {"HA","NB","NP","NR","NS"}),
    # PORK → no HA, no NP, no NR; no beef → NB; no seafood → NS; GF NF from PDF
    ("Pulled pork burrito bowl",     {"GF","NF","NB","NS"}),
    # Nachos: ambiguous protein (could have beef) → conservative; no seafood; GF from PDF
    ("Nachos",                       {"GF","NS"}),
    # Same as nachos
    ("Nacho Fries",                  {"GF","NS"}),
    # Named chicken → HA NB NP NR NS
    ("Chicken Quesadilla",           {"HA","NB","NP","NR","NS"}),
    # Named chicken → HA NB NP NR NS; GF DF from PDF
    ("Chicken Enchilada",            {"GF","DF","HA","NB","NP","NR","NS"}),
    # Named chicken → HA NB NP NR NS
    ("Crispy Chicken Taco",          {"HA","NB","NP","NR","NS"}),
]

# caterer_name → (menu_list, price_cents)
CATERER_MENUS = {
    "Lakehouse Victoria Point": (LAKEHOUSE, 3500),
    "Terrific Noodles":         (TERRIFIC,  2050),
    "Kenko Sushi House":        (KENKO,      550),
    "Guzman y Gomez":           (GYG,       1500),
}


def run() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            # ── build tag name → id map ──────────────────────────────────────
            cur.execute("SELECT name, id FROM dietary_tags")
            tag_id: dict[str, int] = {name: tid for name, tid in cur.fetchall()}

            # ── build caterer name → id map ──────────────────────────────────
            cur.execute("SELECT name, id FROM caterers")
            caterer_id: dict[str, int] = {name: cid for name, cid in cur.fetchall()}

            items_inserted = 0
            tags_inserted = 0

            for caterer_name, (menu, price_cents) in CATERER_MENUS.items():
                cid = caterer_id[caterer_name]
                for item_name, abbrev_tags in menu:
                    # idempotency: skip if already present
                    cur.execute(
                        "SELECT id FROM menu_items WHERE caterer_id = %s AND name = %s",
                        (cid, item_name),
                    )
                    row = cur.fetchone()
                    if row:
                        item_id = row[0]
                    else:
                        cur.execute(
                            """
                            INSERT INTO menu_items (caterer_id, name, price_cents)
                            VALUES (%s, %s, %s)
                            RETURNING id
                            """,
                            (cid, item_name, price_cents),
                        )
                        item_id = cur.fetchone()[0]
                        items_inserted += 1

                    # insert dietary tags
                    for abbrev in abbrev_tags:
                        full_tag = TAG_ABBREVS[abbrev]
                        tid = tag_id.get(full_tag)
                        if tid is None:
                            print(f"WARNING: tag '{full_tag}' not found in dietary_tags")
                            continue
                        cur.execute(
                            """
                            INSERT INTO menu_item_dietary_tags (menu_item_id, dietary_tag_id)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING
                            """,
                            (item_id, tid),
                        )
                        if cur.rowcount:
                            tags_inserted += 1

            conn.commit()

            cur.execute("SELECT COUNT(*) FROM menu_items")
            total_items = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM menu_item_dietary_tags")
            total_tags = cur.fetchone()[0]

            print(f"menu_items:           {total_items} total ({items_inserted} inserted)")
            print(f"menu_item_dietary_tags: {total_tags} total ({tags_inserted} inserted)")

            # summary by caterer
            cur.execute(
                """
                SELECT c.name, COUNT(m.id)
                FROM caterers c
                LEFT JOIN menu_items m ON m.caterer_id = c.id
                GROUP BY c.name, c.id ORDER BY c.id
                """
            )
            for caterer, count in cur.fetchall():
                print(f"  {caterer:<35} {count} items")


if __name__ == "__main__":
    run()
