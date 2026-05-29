#!/usr/bin/env python3
"""
scripts/test_orders.py
Tests for src/tools/orders.py — compose_order_email.

compose_session_order + create_order are covered by integration (compose calls
create internally). compose_order_email needs explicit coverage because
order_lines = 0 in the seed (conscious scope cut).

Seed facts used:
  JPC:      school_id=2, building="G Centre"
  Terrific: caterer_id=2
  Slot 2:   JPC Tuesday (day_of_week=2), dinner_time=18:00 → deliver_by=17:50
             room="G Centre" (== building → rendered once, no duplication)
  Items 11: Spicy Miso Udon — tags include 'No beef' but NOT 'Vegetarian'
  Items 12: Stir-fry Noodles topped with Chicken — tags include 'Halal' but NOT 'Vegetarian'
  Enrolment 20: Hyun Choi        — no tags, no allergy note → SAFE
  Enrolment 22: Benjamin Wilson  — tag: 'No beef'; item 11 has 'No beef' → SAFE
                                   other_allergy_notes set temporarily to test allergy surface
  Enrolment 23: Rashid Khalil    — tags: 'Halal', 'Vegetarian'; item 12 lacks 'Vegetarian' → UNSAFE MATCH

Fixture:
  enr20 → item11 (SAFE, no tags)
  enr22 → item11 (SAFE, No beef tag + allergy note)
  enr23 → item12 (UNSAFE MATCH — meal missing Vegetarian)

Enrolment 22 other_allergy_notes is temporarily UPDATEd and restored in finally.
No seed enrolment has other_allergy_notes set.
"""
import sys
import datetime

from src.ingest.db import get_conn
from src.tools.orders import compose_order_email

TERRIFIC_ID       = 2
TEST_SLOT_ID      = 2                               # JPC Tuesday
TEST_DATE         = datetime.date(2026, 7, 21)      # Tuesday; past all seeded data
TEST_ALLERGY_NOTE = "tree nut allergy (cashews)"

ENR_20 = 20   # Hyun Choi        — no tags, no allergy note
ENR_22 = 22   # Benjamin Wilson  — no_beef tag; allergy note set in test
ENR_23 = 23   # Rashid Khalil    — halal + vegetarian tags


def test_compose_order_email() -> None:
    """
    Insert test order + 3 order_lines (enr20+enr22→item11, enr23→item12).
    Temporarily set enrolment 22 other_allergy_notes for allergy-surface test.

    Asserts:
      - demo header present
      - school name, caterer name, date present
      - location shows "G Centre" exactly once (building==room deduplication)
      - deliver-by 17:50 and dinner 18:00 present
      - all three student names present
      - both meal names present
      - per-meal summary counts correct
      - dietary tags shown: [No beef] for enr22, [Halal, Vegetarian] for enr23
      - enr23 line flagged ⚠ UNSAFE MATCH (item12 lacks Vegetarian)
      - enr22 line NOT flagged ⚠ UNSAFE MATCH (item11 has No beef)
      - allergy note shown: "tree nut allergy (cashews)"
      - meal-list line count == 3 (one per order_line)
      - no price values ('$' absent, 'cents' absent)
    """
    # ── look up actual names from DB — don't hardcode seed values ────────────
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM menu_items WHERE id IN (11, 12) ORDER BY id"
            )
            item_names: dict[int, str] = {row[0]: row[1] for row in cur.fetchall()}

            cur.execute(
                "SELECT id, student_name FROM enrolments WHERE id IN (%s, %s, %s) ORDER BY id",
                (ENR_20, ENR_22, ENR_23),
            )
            student_names: dict[int, str] = {row[0]: row[1] for row in cur.fetchall()}

    assert len(item_names) == 2, f"expected items 11+12 in DB, got {item_names}"
    assert len(student_names) == 3, f"expected enrolments 20/22/23 in DB, got {student_names}"

    item_11 = item_names[11]
    item_12 = item_names[12]
    name_20 = student_names[ENR_20]   # Hyun Choi
    name_22 = student_names[ENR_22]   # Benjamin Wilson
    name_23 = student_names[ENR_23]   # Rashid Khalil

    order_id: int | None = None
    allergy_note_was_set = False
    try:
        # ── temporarily set other_allergy_notes on enrolment 22 ──────────────
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE enrolments SET other_allergy_notes = %s WHERE id = %s",
                    (TEST_ALLERGY_NOTE, ENR_22),
                )
            conn.commit()
        allergy_note_was_set = True

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders
                        (session_slot_id, caterer_id, session_date,
                         total_items, total_cost_cents, gst_rate_percent)
                    VALUES (%s, %s, %s, 3, 0, 10.0)
                    RETURNING id
                    """,
                    (TEST_SLOT_ID, TERRIFIC_ID, TEST_DATE),
                )
                order_id = cur.fetchone()[0]

                # enr20 → item11 (SAFE), enr22 → item11 (SAFE), enr23 → item12 (UNSAFE)
                for enr_id, item_id in [(ENR_20, 11), (ENR_22, 11), (ENR_23, 12)]:
                    cur.execute(
                        """
                        INSERT INTO order_lines
                            (order_id, enrolment_id, menu_item_id, source)
                        VALUES (%s, %s, %s, 'rotation'::order_line_source)
                        """,
                        (order_id, enr_id, item_id),
                    )
            conn.commit()

        body = compose_order_email(order_id)

        # ── structural assertions ─────────────────────────────────────────────
        assert isinstance(body, str), "body must be str"

        assert body.startswith("[DEMO — Intended for:"), (
            f"expected demo header at start of body, got: {body[:80]!r}"
        )
        assert "John Paul College" in body, "school name missing from body"
        assert "Terrific Noodles"  in body, "caterer name missing from body"
        assert "21 July 2026"      in body, "session date missing from body"

        # location deduplication: building == room == "G Centre" → rendered once
        delivery_line = next(ln for ln in body.splitlines() if "Delivery to:" in ln)
        assert "G Centre" in delivery_line, "delivery location 'G Centre' missing"
        assert delivery_line.count("G Centre") == 1, (
            f"location duplicated — 'G Centre' appears more than once: {delivery_line!r}"
        )

        # delivery time
        assert "Deliver by:" in body, "'Deliver by:' label missing from body"
        assert "17:50"       in body, "deliver_by time 17:50 missing from body"
        assert "18:00"       in body, "dinner time 18:00 missing from body"

        # student names
        for enr_id, name in student_names.items():
            assert name in body, f"student name {name!r} (enrolment {enr_id}) missing from body"

        # meal names
        assert item_11 in body, f"meal {item_11!r} missing from body"
        assert item_12 in body, f"meal {item_12!r} missing from body"

        # per-meal summary counts
        assert f"{item_11} × 2" in body, f"expected '{item_11} × 2' in summary block"
        assert f"{item_12} × 1" in body, f"expected '{item_12} × 1' in summary block"

        # dietary tag labels shown for students who have them
        assert "[No beef]" in body, "dietary tag '[No beef]' missing for enrolment 22"
        assert "[Halal, Vegetarian]" in body, "dietary tags '[Halal, Vegetarian]' missing for enrolment 23"

        # safety flag: enr23 (Halal+Vegetarian) → item12 (no Vegetarian) → UNSAFE MATCH
        lines_by_student = {
            name: ln
            for ln in body.splitlines()
            for name in (name_20, name_22, name_23)
            if name in ln and ln.startswith("  ")
        }
        assert name_23 in lines_by_student, f"{name_23!r} not found in allocation lines"
        assert "⚠ UNSAFE MATCH" in lines_by_student[name_23], (
            f"expected ⚠ UNSAFE MATCH on {name_23}'s line (item12 lacks Vegetarian), "
            f"got: {lines_by_student[name_23]!r}"
        )
        # safe lines must NOT carry the flag
        assert name_22 in lines_by_student, f"{name_22!r} not found in allocation lines"
        assert "⚠ UNSAFE MATCH" not in lines_by_student[name_22], (
            f"unexpected ⚠ UNSAFE MATCH on {name_22}'s line (item11 has No beef → safe), "
            f"got: {lines_by_student[name_22]!r}"
        )
        assert name_20 in lines_by_student, f"{name_20!r} not found in allocation lines"
        assert "⚠ UNSAFE MATCH" not in lines_by_student[name_20], (
            f"unexpected ⚠ UNSAFE MATCH on {name_20}'s (no-tag) line"
        )

        # allergy note surface (unverified)
        assert TEST_ALLERGY_NOTE in body, (
            f"allergy note {TEST_ALLERGY_NOTE!r} missing from body"
        )
        assert "ALLERGY NOTE (unverified)" in body, (
            "'ALLERGY NOTE (unverified)' label missing from body"
        )

        # meal-list line count: exactly 3 lines (one per order_line)
        alloc_start = body.index("Meal allocations")
        alloc_end   = body.index("Summary:")
        alloc_block = body[alloc_start:alloc_end]
        alloc_lines = [ln for ln in alloc_block.splitlines() if ln.startswith("  ")]
        assert len(alloc_lines) == 3, (
            f"expected 3 allocation lines, got {len(alloc_lines)}: {alloc_lines}"
        )

        # V4 ruling: no costs on per-session order email
        assert "$"      not in body,       "order email must not contain '$'"
        assert "cents"  not in body.lower(), "order email must not contain 'cents'"

        print(
            f"  ✓ compose_order_email: {len(body)} chars, demo header ✓, "
            f"school/caterer/date ✓, location no-dupe ✓, "
            f"deliver_by=17:50 ✓, dinner=18:00 ✓, "
            f"all student names ✓, meal names ✓, summary counts ✓, "
            f"dietary tags ✓, UNSAFE MATCH flag ✓, no-flag on safe lines ✓, "
            f"allergy note ✓, {len(alloc_lines)} alloc lines ✓, no costs ✓"
        )
        print(f"\n  order_id used: {order_id}")
        print("\n  Body:")
        for line in body.split("\n"):
            print(f"    {line}")

    finally:
        if order_id is not None:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))
                conn.commit()
            print(f"  ✓ cleanup: deleted test order {order_id}")
        if allergy_note_was_set:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE enrolments SET other_allergy_notes = NULL WHERE id = %s",
                        (ENR_22,),
                    )
                conn.commit()
            print(f"  ✓ cleanup: restored enrolment {ENR_22} other_allergy_notes = NULL")


if __name__ == "__main__":
    print("\n=== test_orders.py ===\n")
    try:
        test_compose_order_email()
        print("\nAll orders.py tests passed.\n")
    except AssertionError as exc:
        print(f"\nFAIL: {exc}\n", file=sys.stderr)
        sys.exit(1)
