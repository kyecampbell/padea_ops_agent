#!/usr/bin/env python3
"""
seed_upcoming_exclusions.py — DUMMY DATA
Adds upcoming school events that affect catering orders:

  1. ISHS Year 10 school camp — week of Jun 8 (Mon–Thu)
     Year 10 students at all three ISHS sessions are excluded (non-dietary only).
     Dietary-restricted Year 10 students still receive a meal per CLAUDE.md rule 3.
     Triggers the 10% exclusion buffer for each affected ISHS session.

  2. QLD Term 2 school holidays — Jun 29 – Jul 10
     All 6 schools have whole-session exclusions for this period.
     The agent will see these as whole-school closures and skip order composition.

FAKE DATA: Specific dates and school camp details are invented for demo purposes.
QLD Term 2 2026 end date is approximately Jun 26; these dates are plausible.
"""
import datetime

from src.ingest.db import get_conn

# ── ISHS school camp: Year 10, week of Jun 8 ─────────────────────────────────
# ISHS = school_id 4.  Sessions: slot 5 (Mon), slot 6 (Tue), slot 7 (Thu).
ISHS_CAMP_SCHOOL_ID = 4
ISHS_CAMP_DATES = [
    datetime.date(2026, 6, 8),   # ISHS Mon (slot 5)
    datetime.date(2026, 6, 9),   # ISHS Tue (slot 6)
    datetime.date(2026, 6, 11),  # ISHS Thu (slot 7)
]
ISHS_CAMP_REASON_TEMPLATE = "School Camp — Year 10 excluded"

# ── QLD Term 2 school holidays ────────────────────────────────────────────────
# All sessions from Jun 29 (Mon) to Jul 10 (Fri) are cancelled.
HOLIDAY_START = datetime.date(2026, 6, 27)
HOLIDAY_END   = datetime.date(2026, 7, 12)
HOLIDAY_REASON = "Term 2 school holidays — all year levels, school closed"


def run() -> None:
    exclusion_count = 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM schools ORDER BY id")
            all_school_ids = [r[0] for r in cur.fetchall()]

            # ── 1. ISHS Year 10 camp ─────────────────────────────────────────
            for camp_date in ISHS_CAMP_DATES:
                # Check idempotency
                cur.execute(
                    """
                    SELECT id FROM exclusions
                    WHERE school_id = %s AND start_date = %s AND reason = %s
                    """,
                    (ISHS_CAMP_SCHOOL_ID, camp_date, ISHS_CAMP_REASON_TEMPLATE),
                )
                if cur.fetchone():
                    continue

                cur.execute(
                    """
                    INSERT INTO exclusions (school_id, enrolment_id, start_date, end_date, reason, year_levels_excluded)
                    VALUES (%s, NULL, %s, %s, %s, %s)
                    """,
                    (ISHS_CAMP_SCHOOL_ID, camp_date, camp_date, ISHS_CAMP_REASON_TEMPLATE, [10]),
                )
                exclusion_count += 1

            # ── 2. Term 2 school holidays — all schools ───────────────────────
            for school_id in all_school_ids:
                cur.execute(
                    """
                    SELECT id FROM exclusions
                    WHERE school_id = %s AND start_date = %s AND reason = %s
                    """,
                    (school_id, HOLIDAY_START, HOLIDAY_REASON),
                )
                if cur.fetchone():
                    continue

                cur.execute(
                    """
                    INSERT INTO exclusions (school_id, enrolment_id, start_date, end_date, reason, year_levels_excluded)
                    VALUES (%s, NULL, %s, %s, %s, %s)
                    """,
                    (school_id, HOLIDAY_START, HOLIDAY_END, HOLIDAY_REASON, []),
                )
                exclusion_count += 1

            conn.commit()

    camp_label = f"ISHS Year 10 camp ({', '.join(str(d) for d in ISHS_CAMP_DATES)})"
    holiday_label = f"Term 2 holidays all schools ({HOLIDAY_START} – {HOLIDAY_END})"
    print(f"exclusions added: {exclusion_count}")
    print(f"  {camp_label}")
    print(f"  {holiday_label}")


if __name__ == "__main__":
    run()
