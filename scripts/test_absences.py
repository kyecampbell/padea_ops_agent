#!/usr/bin/env python3
"""
Test: src/tools/absences.py

Covers:
  1. get_absence — existing seeded row, missing row
  2. upsert_absence — insert, then upsert same key with changed field:
       (a) new row appears with correct data
       (b) second call updates the row (count stays 1, field changes)
       (c) third call with identical data is a no-op (count still 1, field unchanged)
       (d) cleanup: row removed, get_absence returns None
  3. get_exclusions — date-in-range, boundary checks
  4. get_year_level_exclusions — year-level rows returned, full-school rows excluded

Requires seeded data:
  - exclusion id=5: school_id=4, date 2026-06-08, year_levels=[10]
  - exclusion id=8: school_id=4, date 2026-07-01 (holiday range), year_levels=[]
  - exclusion id=1: school_id=4, date 2026-05-04, year_levels=[]
  - absences table: at least one row (enrolment_id=1) for get_absence positive test
"""
from datetime import date

from src.ingest.db import get_conn
from src.tools.absences import (
    get_absence,
    get_exclusions,
    get_year_level_exclusions,
    upsert_absence,
)

# Test data — far-future date with no seeded absence
TEST_ENROLMENT_ID = 1
TEST_ABSENCE_DATE = date(2026, 9, 1)


def _row_count(enrolment_id: int, absence_date: date) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM absences WHERE enrolment_id = %s AND absence_date = %s",
                (enrolment_id, absence_date),
            )
            return cur.fetchone()[0]


def _delete_test_absence(enrolment_id: int, absence_date: date) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM absences WHERE enrolment_id = %s AND absence_date = %s",
                (enrolment_id, absence_date),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# 1. get_absence
# ---------------------------------------------------------------------------

def test_get_absence_missing() -> None:
    result = get_absence(TEST_ENROLMENT_ID, TEST_ABSENCE_DATE)
    assert result is None, f"Expected None for unseeded date, got {result}"
    print("  [ok] get_absence: returns None for missing row")


def test_get_absence_existing() -> None:
    # Use a row that was seeded by seed_absences.py or seed_upcoming_absences.py
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT enrolment_id, absence_date FROM absences LIMIT 1")
            row = cur.fetchone()
    assert row is not None, "No seeded absences found — cannot run positive get_absence test"
    enrolment_id, absence_date = row
    result = get_absence(enrolment_id, absence_date)
    assert result is not None, f"Expected a row for ({enrolment_id}, {absence_date}), got None"
    assert result["enrolment_id"] == enrolment_id
    assert result["absence_date"] == absence_date
    assert "id" in result
    print(f"  [ok] get_absence: returns row for existing (enrolment_id={enrolment_id}, {absence_date})")


# ---------------------------------------------------------------------------
# 2. upsert_absence — full upsert semantics
# ---------------------------------------------------------------------------

def test_upsert_absence() -> None:
    # Precondition: test slot is clean
    assert _row_count(TEST_ENROLMENT_ID, TEST_ABSENCE_DATE) == 0, (
        f"Row already exists for ({TEST_ENROLMENT_ID}, {TEST_ABSENCE_DATE}) — pick a different test date"
    )

    try:
        # (a) Insert new row
        absence_id = upsert_absence(
            TEST_ENROLMENT_ID,
            TEST_ABSENCE_DATE,
            source_email_message_id="msg-001",
            notes="initial note",
        )
        assert absence_id > 0, f"Expected positive absence_id, got {absence_id}"
        assert _row_count(TEST_ENROLMENT_ID, TEST_ABSENCE_DATE) == 1
        row = get_absence(TEST_ENROLMENT_ID, TEST_ABSENCE_DATE)
        assert row["notes"] == "initial note", f"Expected 'initial note', got {row['notes']!r}"
        assert row["source_email_message_id"] == "msg-001"
        print(f"  [ok] upsert_absence: insert — id={absence_id}, notes='initial note'")

        # (b) Same key, different data — DO NOTHING: first-write-wins, row UNCHANGED
        absence_id2 = upsert_absence(
            TEST_ENROLMENT_ID,
            TEST_ABSENCE_DATE,
            source_email_message_id="msg-002",
            notes="this should be ignored",
        )
        assert absence_id2 == absence_id, (
            f"FAIL: second upsert returned id={absence_id2}, expected same id={absence_id} — row was duplicated"
        )
        assert _row_count(TEST_ENROLMENT_ID, TEST_ABSENCE_DATE) == 1, (
            "FAIL: row count > 1 after second upsert — duplicate inserted"
        )
        row = get_absence(TEST_ENROLMENT_ID, TEST_ABSENCE_DATE)
        assert row["notes"] == "initial note", (
            f"FAIL: DO NOTHING violated — notes was overwritten to {row['notes']!r}, "
            f"expected original 'initial note'"
        )
        assert row["source_email_message_id"] == "msg-001", (
            f"FAIL: DO NOTHING violated — source_email_message_id was overwritten to "
            f"{row['source_email_message_id']!r}, expected original 'msg-001'"
        )
        print("  [ok] upsert_absence: DO NOTHING — second call ignored, original notes preserved, count=1")

        # (c) Identical call — also a no-op
        absence_id3 = upsert_absence(
            TEST_ENROLMENT_ID,
            TEST_ABSENCE_DATE,
            source_email_message_id="msg-001",
            notes="initial note",
        )
        assert absence_id3 == absence_id
        assert _row_count(TEST_ENROLMENT_ID, TEST_ABSENCE_DATE) == 1
        print("  [ok] upsert_absence: identical re-call — count still 1")

    finally:
        _delete_test_absence(TEST_ENROLMENT_ID, TEST_ABSENCE_DATE)
        print("  [cleanup] test absence deleted")

    # (d) Confirms cleanup
    assert get_absence(TEST_ENROLMENT_ID, TEST_ABSENCE_DATE) is None
    print("  [ok] upsert_absence: get_absence returns None after cleanup")


# ---------------------------------------------------------------------------
# 3. get_exclusions
# ---------------------------------------------------------------------------

def test_get_exclusions() -> None:
    # school_id=4 (ISHS), date 2026-06-08: ISHS camp (year 10), not yet holidays
    results = get_exclusions(4, date(2026, 6, 8))
    ids = [r["id"] for r in results]
    assert 5 in ids, f"Expected exclusion id=5 (ISHS camp Jun 8), got ids={ids}"
    # Holiday row (id=11) covers 2026-06-27 to 2026-07-12 — must NOT appear on Jun 8
    assert 11 not in ids, f"Holiday exclusion id=11 must not appear on 2026-06-08, got ids={ids}"
    for r in results:
        assert "year_levels_excluded" in r
        assert isinstance(r["year_levels_excluded"], list)
    print(f"  [ok] get_exclusions (school=4, 2026-06-08): ids={ids}")

    # school_id=4, date 2026-07-01: inside holiday range
    results2 = get_exclusions(4, date(2026, 7, 1))
    ids2 = [r["id"] for r in results2]
    assert 11 in ids2, f"Expected holiday exclusion id=11 on 2026-07-01, got ids={ids2}"
    # Camp row (id=5) only covers Jun 8 — must NOT appear on Jul 1
    assert 5 not in ids2, f"Camp exclusion id=5 must not appear on 2026-07-01, got ids={ids2}"
    print(f"  [ok] get_exclusions (school=4, 2026-07-01): ids={ids2}")

    # school_id=4, date 2026-05-04: Open Day (whole-session, year_levels=[])
    results3 = get_exclusions(4, date(2026, 5, 4))
    ids3 = [r["id"] for r in results3]
    assert 1 in ids3, f"Expected Open Day exclusion id=1 on 2026-05-04, got ids={ids3}"
    open_day = next(r for r in results3 if r["id"] == 1)
    assert open_day["year_levels_excluded"] == [], (
        f"Expected [] for full-school exclusion, got {open_day['year_levels_excluded']}"
    )
    print(f"  [ok] get_exclusions (school=4, 2026-05-04): ids={ids3}, year_levels=[]")


# ---------------------------------------------------------------------------
# 4. get_year_level_exclusions
# ---------------------------------------------------------------------------

def test_get_year_level_exclusions() -> None:
    # school_id=4, date 2026-06-08: year-level camp row (year_levels=[10])
    results = get_year_level_exclusions(4, date(2026, 6, 8))
    assert len(results) >= 1, f"Expected at least 1 year-level exclusion, got {results}"
    camp = next((r for r in results if r["id"] == 5), None)
    assert camp is not None, "Expected exclusion id=5 in year-level results"
    assert camp["excluded_year_levels"] == [10], (
        f"Expected [10], got {camp['excluded_year_levels']}"
    )
    print(f"  [ok] get_year_level_exclusions (school=4, 2026-06-08): {results}")

    # school_id=4, date 2026-07-01: holiday has year_levels=[] — must NOT appear
    results2 = get_year_level_exclusions(4, date(2026, 7, 1))
    ids2 = [r["id"] for r in results2]
    assert 11 not in ids2, (
        f"Full-school holiday (id=11, year_levels=[]) must not appear in year-level results, got {ids2}"
    )
    print(f"  [ok] get_year_level_exclusions (school=4, 2026-07-01): correctly empty (holiday is full-school)")

    # school_id=4, date 2026-05-04: Open Day (year_levels=[]) — must NOT appear
    results3 = get_year_level_exclusions(4, date(2026, 5, 4))
    ids3 = [r["id"] for r in results3]
    assert 1 not in ids3, (
        f"Full-school Open Day (id=1, year_levels=[]) must not appear in year-level results, got {ids3}"
    )
    print(f"  [ok] get_year_level_exclusions (school=4, 2026-05-04): correctly empty (Open Day is full-school)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n--- get_absence ---")
    test_get_absence_missing()
    test_get_absence_existing()

    print("\n--- upsert_absence ---")
    test_upsert_absence()

    print("\n--- get_exclusions ---")
    test_get_exclusions()

    print("\n--- get_year_level_exclusions ---")
    test_get_year_level_exclusions()

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
