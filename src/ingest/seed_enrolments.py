#!/usr/bin/env python3
"""
seed_enrolments.py
320 enrolments + enrolment_dietary_tags from data/source/students.xlsx.

Excel structure per sheet:
  Row 1: school+session title  (skip)
  Row 2: blank                  (skip)
  Row 3: column headers         (skip)
  Row 4+: data

Columns (0-indexed):
  0 student_name   1 year_level   2 subjects (not stored)
  3 dietary        4 student_email (not in schema — not stored)
  5 parent_name    6 parent_email  7 parent_mobile

Dietary column parsing (data_inventory.md):
  - Split on comma, strip whitespace
  - "Opted out of Catering" → opted_out_of_catering = True (not a tag)
  - Remaining values mapped via TAG_LOOKUP to dietary_tag names
  - Conservative: "No Fish" → no_seafood; "No Shellfish" → no_seafood

Cross-school duplicate names: treated as DIFFERENT students (D3).
No within-school duplicates exist in the source data (data_observations.md).

Schema gap note: enrolments are per-(student, school), not per-(student, session_slot).
V4 order composition queries all active enrolments for a school, meaning students from
different sessions at the same school (e.g. ISHS Mon vs ISHS Tue) are all "active"
for every session. This is a known V4 limitation; the per-session cohort distinction
is not captured in the schema. Flagged for V5: add session_slot_id to enrolments.

Seed dates: original_start_date = current_period_start_date = 2026-04-21
(QLD Term 2 2026 approximate start). current_period_end_date = NULL (all active).
"""
import datetime
from pathlib import Path
import openpyxl
from src.ingest.db import get_conn

STUDENTS_XLSX = Path("data/source/students.xlsx")
TERM_START    = datetime.date(2026, 4, 21)
DEMO_EMAIL    = "kyec898@gmail.com"
DEMO_MOBILE   = "0458971565"

OPT_OUT_MARKER = "Opted out of Catering"

TAG_LOOKUP: dict[str, str] = {
    "Halal":           "halal",
    "No Beef":         "no_beef",
    "Vegetarian":      "vegetarian",
    "Nut Free":        "no_nuts",
    "Dairy Free":      "no_dairy",
    "Gluten Free":     "gluten_free",
    "No Fish":         "no_seafood",   # conservative: maps to no_seafood
    "No Pork":         "no_pork",
    "No Red Meat":     "no_red_meat",
    "No Seafood":      "no_seafood",
    "No Shellfish":    "no_seafood",   # conservative: maps to no_seafood
}

# xlsx sheet name → school name (must match schools.name exactly)
SHEET_TO_SCHOOL: dict[str, str] = {
    "MBBC":            "Moreton Bay Boys' College",
    "JPC - Tuesday":   "John Paul College",
    "JPC - Wednesday": "John Paul College",
    "MSHS":            "MacGregor State High School",
    "ISHS - Monday":   "Indooroopilly State High School",
    "ISHS - Tuesday":  "Indooroopilly State High School",
    "ISHS - Thursday": "Indooroopilly State High School",
    "LC - Monday":     "Loreto College",
    "LC - Tuesday":    "Loreto College",
    "CHAC - Monday":   "Cannon Hill Anglican College",
    "CHAC - Wednesday":"Cannon Hill Anglican College",
}


def parse_dietary(raw: str | None) -> tuple[bool, list[str]]:
    """Returns (opted_out, [tag_name, ...])."""
    if not raw:
        return False, []
    parts = [p.strip() for p in str(raw).split(",")]
    opted_out = OPT_OUT_MARKER in parts
    tags: list[str] = []
    for part in parts:
        if part == OPT_OUT_MARKER:
            continue
        tag = TAG_LOOKUP.get(part)
        if tag:
            if tag not in tags:
                tags.append(tag)
        else:
            print(f"  WARNING: unrecognised dietary value '{part}'")
    return opted_out, tags


def run() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            # ── lookup maps ──────────────────────────────────────────────────
            cur.execute("SELECT name, id FROM schools")
            school_id: dict[str, int] = {name: sid for name, sid in cur.fetchall()}

            cur.execute("SELECT name, id FROM dietary_tags")
            tag_id: dict[str, int] = {name: tid for name, tid in cur.fetchall()}

            wb = openpyxl.load_workbook(STUDENTS_XLSX, data_only=True)
            enrolments_inserted = 0
            tags_inserted = 0

            for sheet_name, school_name in SHEET_TO_SCHOOL.items():
                ws = wb[sheet_name]
                sid = school_id[school_name]

                # rows start at row 4 (index 3); skip title, blank, header
                for row in ws.iter_rows(min_row=4, values_only=True):
                    student_name = row[0]
                    if not student_name:
                        continue  # blank trailing row

                    year_level  = row[1]  # integer or None
                    dietary_raw = row[3]  # may be None
                    parent_name = row[5] or ""
                    parent_email= DEMO_EMAIL
                    parent_phone= DEMO_MOBILE

                    opted_out, tags = parse_dietary(dietary_raw)

                    # idempotency: skip if (student_name, school_id) already present
                    # Note: this is per-sheet, so ISHS Monday + ISHS Tuesday students
                    # (different names in practice) both insert fine.
                    cur.execute(
                        """
                        SELECT id FROM enrolments
                        WHERE school_id = %s AND student_name = %s
                        """,
                        (sid, student_name),
                    )
                    existing = cur.fetchone()
                    if existing:
                        enrolment_id = existing[0]
                    else:
                        cur.execute(
                            """
                            INSERT INTO enrolments (
                                school_id, student_name, student_year_level,
                                parent_name, parent_email, parent_phone,
                                original_start_date, current_period_start_date,
                                opted_out_of_catering
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            RETURNING id
                            """,
                            (sid, student_name, year_level,
                             parent_name, parent_email, parent_phone,
                             TERM_START, TERM_START,
                             opted_out),
                        )
                        enrolment_id = cur.fetchone()[0]
                        enrolments_inserted += 1

                    # dietary tags
                    for tag_name in tags:
                        tid = tag_id.get(tag_name)
                        if tid is None:
                            print(f"  WARNING: tag '{tag_name}' not in dietary_tags")
                            continue
                        cur.execute(
                            """
                            INSERT INTO enrolment_dietary_tags (enrolment_id, dietary_tag_id)
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING
                            """,
                            (enrolment_id, tid),
                        )
                        if cur.rowcount:
                            tags_inserted += 1

                conn.commit()
                # per-sheet progress
                cur.execute(
                    "SELECT COUNT(*) FROM enrolments WHERE school_id = %s", (sid,)
                )

            cur.execute("SELECT COUNT(*) FROM enrolments")
            total_e = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM enrolment_dietary_tags")
            total_t = cur.fetchone()[0]

            print(f"enrolments:            {total_e} total ({enrolments_inserted} inserted)")
            print(f"enrolment_dietary_tags:{total_t} total ({tags_inserted} inserted)")

            # opted-out count
            cur.execute("SELECT COUNT(*) FROM enrolments WHERE opted_out_of_catering = true")
            opted = cur.fetchone()[0]
            print(f"opted_out_of_catering: {opted} students")

            # per-school counts
            cur.execute(
                """
                SELECT sc.name, COUNT(e.id)
                FROM schools sc
                LEFT JOIN enrolments e ON e.school_id = sc.id
                GROUP BY sc.name, sc.id ORDER BY sc.id
                """
            )
            print("\nEnrolments by school:")
            for school, count in cur.fetchall():
                print(f"  {school:<45} {count}")


if __name__ == "__main__":
    run()
