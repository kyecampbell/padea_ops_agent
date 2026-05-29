#!/usr/bin/env python3
"""
scripts/test_compose_session_order.py

Tests for compose_session_order (src/tools/orders.py) — specifically the
safety_records extension and the closure of the request-source safety hole.

Seed facts (verified from DB at test-design time):
  JPC:       school_id=2,  Terrific caterer (caterer_id=2)
  Slot 2:    JPC Tuesday (day_of_week=2), session_slot_id=2
  TEST_DATE: 2026-08-04 (Tuesday) — no existing order, no JPC exclusions
  Cohort:    28 students active on TEST_DATE (after get_enrolments_for_session)

  Dietary students in cohort:
    enr 22  Benjamin Wilson   — [no_beef]          has prefs for Terrific → rotation → safe=True
    enr 36  Pooja Mehta       — [vegetarian]        no prefs, no safe Terrific item → escalation (correct)
    enr 37  Georgia Clark     — [halal]             has prefs for Terrific → rotation → safe=True
    enr 23  Rashid Khalil     — [halal, vegetarian] no prefs, no safe Terrific item

  Item 12:  Stir-fry Noodles topped with Chicken (Terrific)
            tags = [halal, no_beef, no_dairy, no_nuts, no_pork, no_red_meat, no_seafood, gluten_free]
            MISSING: vegetarian → unsafe for enr 23 (needs halal + vegetarian)

The test injects a meal_request for enr 23 → item 12. This:
  - Takes the 'request' path (bypassing rotation/auto_pick).
  - Triggers item_is_safe_for_enrolment(12, 23) → False (vegetarian tag missing on item 12).
  - Produces safety_records entry: safe=False, source='request'.
  - Still appears in order_lines (unsafe meal logged, not silently dropped).

Separately, enr 36 (Pooja Mehta, vegetarian) produces a correct 'no safe meal' escalation
because Terrific has no vegetarian-tagged items. This is expected, not a bug.

The test then simulates the loop's post-dispatch safety logging:
  - Calls log_agent_step(urgency='urgent', tool_name='dietary_safety_violation') for each
    safe=False entry in safety_records.
  - Calls log_agent_step(urgency='urgent', tool_name='unverified_allergy_note') for each
    non-null other_allergy_notes entry (none in this fixture; verified absent).
  - Asserts the urgent agent_steps row was written to the DB.

Cleanup (always in finally):
  - DELETE order (CASCADE removes order_lines)
  - DELETE meal_request (was consumed; not cascade-deleted by order)
  - DELETE agent_run (CASCADE removes agent_steps)
"""
import sys
import datetime

from src.ingest.db import get_conn
from src.tools.orders import compose_session_order
from src.tools.infrastructure import create_agent_run, log_agent_step

# ── seed constants ────────────────────────────────────────────────────────────
TEST_SLOT_ID    = 2                                  # JPC Tuesday
TEST_DATE       = datetime.date(2026, 8, 4)          # Tuesday — no existing orders/exclusions
TEST_ENR        = 23                                 # Rashid Khalil: [halal, vegetarian]
TEST_ITEM       = 12                                 # Stir-fry Noodles: halal but NOT vegetarian → UNSAFE

ENR_POOJA       = 36                                 # Pooja Mehta: [vegetarian] — no safe Terrific item
EXPECTED_COHORT = 28                                 # active non-opted-out students in slot 2 on TEST_DATE


def _preconditions() -> None:
    """Fail fast if seed data doesn't match the constants above."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Slot 2 must exist, be a Tuesday, be active
            cur.execute(
                "SELECT day_of_week, active FROM session_slots WHERE id = %s",
                (TEST_SLOT_ID,),
            )
            row = cur.fetchone()
            assert row is not None, f"session_slot {TEST_SLOT_ID} not found"
            dow, active = row
            assert dow == 2, f"slot {TEST_SLOT_ID} must be day_of_week=2 (Tuesday), got {dow}"
            assert active, f"slot {TEST_SLOT_ID} must be active"
            assert TEST_DATE.isoweekday() == 2, f"{TEST_DATE} must be a Tuesday"

            # No existing order for the test slot/date
            cur.execute(
                "SELECT 1 FROM orders WHERE session_slot_id = %s AND session_date = %s",
                (TEST_SLOT_ID, TEST_DATE),
            )
            assert cur.fetchone() is None, (
                f"Order already exists for slot {TEST_SLOT_ID}/{TEST_DATE}; choose a different test date"
            )

            # No existing meal_request for enr 23 on this date (clean slate)
            cur.execute(
                "SELECT 1 FROM meal_requests WHERE enrolment_id = %s "
                "AND session_slot_id = %s AND session_date = %s",
                (TEST_ENR, TEST_SLOT_ID, TEST_DATE),
            )
            assert cur.fetchone() is None, (
                f"meal_request already exists for enr {TEST_ENR}/slot {TEST_SLOT_ID}/{TEST_DATE}"
            )

            # enr 23 in enrolment_session_slots for slot 2 with left_date IS NULL
            cur.execute(
                "SELECT 1 FROM enrolment_session_slots "
                "WHERE enrolment_id = %s AND session_slot_id = %s AND left_date IS NULL",
                (TEST_ENR, TEST_SLOT_ID),
            )
            assert cur.fetchone() is not None, (
                f"enrolment {TEST_ENR} not in enrolment_session_slots for slot {TEST_SLOT_ID}"
            )

            # enr 23 must be active on TEST_DATE
            cur.execute(
                "SELECT current_period_end_date FROM enrolments WHERE id = %s",
                (TEST_ENR,),
            )
            row = cur.fetchone()
            assert row is not None, f"enrolment {TEST_ENR} not found"
            end_date = row[0]
            assert end_date is None or end_date > TEST_DATE, (
                f"enrolment {TEST_ENR} has end_date {end_date} ≤ {TEST_DATE} — not active on test date"
            )

    print("  [preconditions] slot, date, enrolment, session membership — all clean")


def test_request_source_safety_violation() -> None:
    """
    A request-source meal that violates the student's dietary tags:
      1. Produces safe=False in safety_records (was: silent hole — check never ran).
      2. Still appears in order_lines (logged and escalated, not silently dropped).
      3. All other students in safety_records have safe=True.
      4. Simulated loop logging writes an urgent agent_steps row for the violation.

    Also confirms the safety_records shape: enrolment_id, student_name,
    menu_item_id, meal_name, source, dietary_tags, safe, other_allergy_notes.
    """
    order_id: int | None        = None
    meal_request_id: int | None = None
    run_id: int | None          = None

    try:
        # ── create agent_run (loop would do this) ────────────────────────────
        run_id = create_agent_run("test_request_source_safety_violation")

        # ── insert unsafe meal_request: enr 23 wants item 12 ─────────────────
        # item 12 has [halal] but NOT [vegetarian] → unsafe for enr 23 (needs both)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO meal_requests
                        (enrolment_id, session_slot_id, session_date, menu_item_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (TEST_ENR, TEST_SLOT_ID, TEST_DATE, TEST_ITEM),
                )
                meal_request_id = cur.fetchone()[0]
            conn.commit()

        # ── run compose_session_order ─────────────────────────────────────────
        result = compose_session_order(TEST_SLOT_ID, TEST_DATE)
        order_id = result["order_id"]

        # ── safety_records must be in result ──────────────────────────────────
        assert "safety_records" in result, (
            "safety_records missing from compose_session_order result"
        )

        safety_records = result["safety_records"]
        order_lines    = result["order_lines"]
        escalations    = result["escalations"]

        # ── cohort accounting ─────────────────────────────────────────────────
        # Pooja Mehta (enr 36, vegetarian) has no safe Terrific item → escalation.
        # Everyone else gets a meal (27 students in order_lines + safety_records).
        assert len(order_lines) == EXPECTED_COHORT - 1, (
            f"Expected {EXPECTED_COHORT - 1} order_lines (cohort {EXPECTED_COHORT} - 1 for Pooja), "
            f"got {len(order_lines)}"
        )
        assert len(safety_records) == len(order_lines), (
            f"safety_records ({len(safety_records)}) must match order_lines ({len(order_lines)})"
        )
        assert len(escalations) == 1, (
            f"Expected 1 escalation (Pooja Mehta — no safe Terrific item), got {len(escalations)}: "
            f"{escalations}"
        )
        assert str(ENR_POOJA) in escalations[0], (
            f"Escalation must reference enrolment {ENR_POOJA} (Pooja Mehta), got: {escalations[0]!r}"
        )

        # ── enr 23 must be in order_lines — unsafe request is logged, NOT dropped ─
        enr23_in_lines = next(
            (l for l in order_lines if l["enrolment_id"] == TEST_ENR), None
        )
        assert enr23_in_lines is not None, (
            f"Enrolment {TEST_ENR} must be in order_lines — "
            f"an unsafe request is logged and escalated, not silently removed"
        )
        assert enr23_in_lines["menu_item_id"] == TEST_ITEM, (
            f"Enrolment {TEST_ENR} in order_lines must have menu_item_id={TEST_ITEM} "
            f"(the requested item), got {enr23_in_lines['menu_item_id']}"
        )
        assert enr23_in_lines["source"] == "request", (
            f"Expected source='request' in order_lines for enr {TEST_ENR}, "
            f"got {enr23_in_lines['source']!r}"
        )

        # ── find enr 23's safety_record ───────────────────────────────────────
        rec_23 = next(
            (r for r in safety_records if r["enrolment_id"] == TEST_ENR), None
        )
        assert rec_23 is not None, (
            f"No safety_record for enrolment {TEST_ENR} (Rashid Khalil)"
        )

        # Shape: all eight required keys must be present
        for key in ("enrolment_id", "student_name", "menu_item_id", "meal_name",
                    "source", "dietary_tags", "safe", "other_allergy_notes"):
            assert key in rec_23, f"safety_record missing required key: {key!r}"

        # Content: the specific violation
        assert rec_23["source"] == "request", (
            f"Expected source='request' in safety_record for enr {TEST_ENR}, "
            f"got {rec_23['source']!r}"
        )
        assert rec_23["menu_item_id"] == TEST_ITEM, (
            f"Expected menu_item_id={TEST_ITEM} in safety_record for enr {TEST_ENR}, "
            f"got {rec_23['menu_item_id']}"
        )
        assert rec_23["safe"] is False, (
            f"Expected safe=False for enr {TEST_ENR} (item {TEST_ITEM} lacks 'vegetarian' tag "
            f"but student requires it). Before this fix, item_is_safe_for_enrolment was never "
            f"called on request-source meals — this would have been a silent safety hole. "
            f"Got safe={rec_23['safe']!r}"
        )
        assert "halal" in rec_23["dietary_tags"], (
            f"Expected 'halal' in dietary_tags for enr {TEST_ENR}, got {rec_23['dietary_tags']}"
        )
        assert "vegetarian" in rec_23["dietary_tags"], (
            f"Expected 'vegetarian' in dietary_tags for enr {TEST_ENR}, "
            f"got {rec_23['dietary_tags']}"
        )
        # other_allergy_notes: None for enr 23 (no note in seed data)
        assert rec_23["other_allergy_notes"] is None, (
            f"Expected other_allergy_notes=None for enr {TEST_ENR} (no note seeded), "
            f"got {rec_23['other_allergy_notes']!r}"
        )

        print(
            f"  ✓ compose_session_order safety_records: "
            f"enr {TEST_ENR} safe=False, source='request', "
            f"dietary_tags={rec_23['dietary_tags']}, still in order_lines"
        )
        print(
            f"  ✓ escalation for enr {ENR_POOJA} (no safe Terrific item) — 1 total"
        )

        # ── all OTHER safety_records must have safe=True (defense-in-depth) ───
        unsafe_others = [
            r for r in safety_records
            if r["enrolment_id"] != TEST_ENR and r["safe"] is not True
        ]
        assert len(unsafe_others) == 0, (
            f"Expected all non-enr-{TEST_ENR} safety_records to have safe=True, "
            f"found {len(unsafe_others)} unsafe: "
            + ", ".join(
                f"enr {r['enrolment_id']} source={r['source']!r} safe={r['safe']!r}"
                for r in unsafe_others
            )
        )
        print(
            f"  ✓ all {len(safety_records) - 1} other students: safe=True "
            f"(rotation/auto_pick paths confirmed sound)"
        )

        # ── simulate loop post-dispatch: log urgent steps for safe=False ──────
        # This is exactly what the loop's post-dispatch block will do.
        step_index = 0
        urgent_steps_logged = 0

        for rec in safety_records:
            if not rec["safe"]:
                log_agent_step(
                    run_id=run_id,
                    step_index=step_index,
                    tool_name="dietary_safety_violation",
                    tool_input={
                        "enrolment_id": rec["enrolment_id"],
                        "menu_item_id": rec["menu_item_id"],
                    },
                    tool_output_full=rec,
                    reasoning=(
                        f"UNSAFE MATCH: {rec['student_name']} (enrolment {rec['enrolment_id']}) "
                        f"assigned {rec['meal_name']!r} (item {rec['menu_item_id']}) — "
                        f"item tags do not cover student dietary requirements "
                        f"{rec['dietary_tags']}. "
                        f"Source was '{rec['source']}'. "
                        f"Operator verification required before order email sends."
                    ),
                    urgency="urgent",
                )
                step_index += 1
                urgent_steps_logged += 1

            if rec["other_allergy_notes"]:
                log_agent_step(
                    run_id=run_id,
                    step_index=step_index,
                    tool_name="unverified_allergy_note",
                    tool_input={
                        "enrolment_id": rec["enrolment_id"],
                        "student_name": rec["student_name"],
                    },
                    tool_output_full={
                        "student_name":        rec["student_name"],
                        "other_allergy_notes": rec["other_allergy_notes"],
                    },
                    reasoning=(
                        f"{rec['student_name']} has an unverified free-text allergy note: "
                        f"'{rec['other_allergy_notes']}'. Cannot be auto-checked against "
                        f"dietary tags. Caterer must confirm which menu items are safe."
                    ),
                    urgency="urgent",
                )
                step_index += 1
                urgent_steps_logged += 1

        assert urgent_steps_logged == 1, (
            f"Expected exactly 1 urgent step (enr {TEST_ENR} safe=False; "
            f"no other_allergy_notes in fixture), got {urgent_steps_logged}"
        )

        # ── verify the urgent agent_steps row exists in DB ────────────────────
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, tool_name, urgency, tool_input
                    FROM agent_steps
                    WHERE run_id = %s AND urgency = 'urgent'
                    ORDER BY step_index
                    """,
                    (run_id,),
                )
                urgent_rows = cur.fetchall()

        assert len(urgent_rows) == 1, (
            f"Expected 1 urgent agent_steps row for run_id {run_id}, got {len(urgent_rows)}"
        )
        step_id, tool_name_db, urgency_db, tool_input_db = urgent_rows[0]
        assert tool_name_db == "dietary_safety_violation", (
            f"Expected tool_name='dietary_safety_violation', got {tool_name_db!r}"
        )
        assert urgency_db == "urgent", (
            f"Expected urgency='urgent', got {urgency_db!r}"
        )
        assert tool_input_db["enrolment_id"] == TEST_ENR, (
            f"Expected tool_input enrolment_id={TEST_ENR}, got {tool_input_db}"
        )
        assert tool_input_db["menu_item_id"] == TEST_ITEM, (
            f"Expected tool_input menu_item_id={TEST_ITEM}, got {tool_input_db}"
        )

        print(
            f"  ✓ log_agent_step: 1 urgent 'dietary_safety_violation' step "
            f"(step_id={step_id}) written to agent_steps for run_id={run_id}"
        )
        print(
            f"  ✓ tool_input: enrolment_id={tool_input_db['enrolment_id']}, "
            f"menu_item_id={tool_input_db['menu_item_id']}"
        )

    finally:
        if order_id is not None:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))
                conn.commit()
            print(f"  ✓ cleanup: deleted order {order_id} (CASCADE → order_lines)")

        if meal_request_id is not None:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM meal_requests WHERE id = %s", (meal_request_id,))
                conn.commit()
            print(f"  ✓ cleanup: deleted meal_request {meal_request_id} (was consumed)")

        if run_id is not None:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM agent_runs WHERE id = %s", (run_id,))
                conn.commit()
            print(f"  ✓ cleanup: deleted agent_run {run_id} (CASCADE → agent_steps)")


if __name__ == "__main__":
    print("\n=== test_compose_session_order.py ===\n")
    try:
        _preconditions()
        print()
        test_request_source_safety_violation()
        print("\nAll compose_session_order tests passed.\n")
    except AssertionError as exc:
        print(f"\nFAIL: {exc}\n", file=sys.stderr)
        sys.exit(1)
