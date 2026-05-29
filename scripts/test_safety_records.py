#!/usr/bin/env python
"""
scripts/test_safety_records.py

Test STEP 3c: safety_records unconditional logging.

Part 1 — unit tests (mocked, no DB):
  Model emits one compose_session_order call whose dispatch returns a result
  with three safety_records:
    (a) safe=True,  other_allergy_notes=None  → NO safety step
    (b) safe=False, other_allergy_notes=None  → ONE urgent dietary_safety_violation step
    (c) safe=True,  other_allergy_notes="peanut allergy not on file"
                                              → ONE urgent allergy_note_unverified step

  Assertions:
    - record (a) produces no safety step
    - record (b) produces exactly one dietary_safety_violation step (urgency=urgent)
    - record (c) produces exactly one allergy_note_unverified step (urgency=urgent)
    - reasoning for (b) names the student AND the meal
    - reasoning for (c) includes the verbatim note text and student name
    - call_count NOT incremented by safety logging (no max_calls_reached step)
    - all step_indices are unique (no UNIQUE(run_id, step_index) collision)
    - compose_session_order dispatch errors → no crash, no safety steps

Part 2 — integration check (real DB, real compose_session_order):
  Calls the REAL compose_session_order against the seeded DB.
  Asserts safety_records is present with the eight real field names.
  Proves the mock fixture's field names match reality — if 3c reads a field
  that doesn't exist in the real return, loop-owned safety logging silently
  produces None-filled reasoning on the live run.
  Cleans up (DELETE order CASCADE) in a finally block.
"""
from __future__ import annotations

import datetime
import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test")
sys.path.insert(0, ".")

from src.agent.loop import run  # noqa: E402

PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        detail: {detail}" if detail else ""))


# ── mock helpers ──────────────────────────────────────────────────────────────

def _tool_use_block(name: str, bid: str, input_dict: dict) -> MagicMock:
    b = MagicMock()
    b.type = "tool_use"
    b.name = name
    b.id = bid
    b.input = input_dict
    return b


def _text_block(text: str) -> MagicMock:
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _response(*blocks) -> MagicMock:
    r = MagicMock()
    r.content = list(blocks)
    return r


# ── safety_records result fixture — matches REAL compose_session_order shape ──
#
# Real shape (from src/tools/orders.py):
#   enrolment_id, student_name, menu_item_id, meal_name, source,
#   dietary_tags, safe, other_allergy_notes
#
# NO 'reason' field — the real function never sets one.
# The integration check in Part 2 asserts this explicitly.

SAFETY_RECORDS_RESULT = {
    "order_id": 1,
    "caterer_id": 2,
    "total_students": 3,
    "total_cost_cents": 4500,
    "order_lines": [],
    "escalations": [],
    "safety_records": [
        # (a) safe row — must produce NO safety step
        {
            "enrolment_id":        10,
            "student_name":        "Alice Safe",
            "menu_item_id":        5,
            "meal_name":           "Chicken Rice",
            "source":              "rotation",
            "dietary_tags":        [],
            "safe":                True,
            "other_allergy_notes": None,
        },
        # (b) unsafe row — must produce ONE dietary_safety_violation step
        {
            "enrolment_id":        20,
            "student_name":        "Bob Unsafe",
            "menu_item_id":        12,
            "meal_name":           "Stir-fry Noodles topped with Chicken",
            "source":              "request",
            "dietary_tags":        ["halal", "vegetarian"],
            "safe":                False,
            "other_allergy_notes": None,
        },
        # (c) allergy-note row — must produce ONE allergy_note_unverified step
        {
            "enrolment_id":        30,
            "student_name":        "Carol Allergy",
            "menu_item_id":        7,
            "meal_name":           "Pasta Bake",
            "source":              "dietary_auto_pick",
            "dietary_tags":        ["gluten_free"],
            "safe":                True,
            "other_allergy_notes": "peanut allergy not on file",
        },
    ],
}


# ── PART 1 — unit tests (mocked) ─────────────────────────────────────────────

def test_safety_records_logging() -> None:
    print("\n=== PART 1: test_safety_records_logging (mocked) ===")
    print("    Setup: 1 compose_session_order call, 3 safety_records (safe, unsafe, allergy)")
    print("    Expected: 0 safe-row steps, 1 violation step, 1 allergy step\n")

    turn1 = _response(
        _text_block("Composing order for session slot 5 on 2026-08-04."),
        _tool_use_block(
            "compose_session_order",
            "id-cso",
            {"session_slot_id": 5, "session_date": "2026-08-04"},
        ),
    )
    turn2 = _response(
        _text_block("Order composed successfully. Two safety flags raised.")
    )

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [turn1, turn2]

    log_calls: list[dict] = []

    def fake_log(**kwargs) -> int:
        log_calls.append(kwargs)
        return len(log_calls)

    def fake_dispatch(tool_name: str, tool_input: dict, run_id: int, step_index: int):
        return SAFETY_RECORDS_RESULT, False

    with (
        patch("src.agent.loop.anthropic.Anthropic", return_value=mock_client),
        patch("src.agent.loop.create_agent_run", return_value=77),
        patch("src.agent.loop.complete_agent_run"),
        patch("src.agent.loop.log_agent_step", side_effect=fake_log),
        patch("src.agent.loop.dispatch", side_effect=fake_dispatch),
        patch("src.agent.loop._load_system_prompt", return_value="SYSTEM PROMPT"),
        patch("src.agent.loop.settings") as mock_settings,
    ):
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.agent_model = "claude-sonnet-4-6"
        mock_settings.max_tool_calls_per_run = 15

        run("T-72h order trigger")

    # ── 1. compose_session_order normal step ──────────────────────────────────
    cso_steps = [s for s in log_calls if s.get("tool_name") == "compose_session_order"]
    check("1 compose_session_order step logged", len(cso_steps) == 1, f"got {len(cso_steps)}")
    if cso_steps:
        cs = cso_steps[0]
        check(
            "compose_session_order urgency=informational",
            cs.get("urgency") == "informational",
            f"got urgency={cs.get('urgency')!r}",
        )
        print(f"         compose step_index={cs.get('step_index')} urgency={cs.get('urgency')!r}")

    # ── 2. record (b): dietary_safety_violation ───────────────────────────────
    violation_steps = [s for s in log_calls if s.get("tool_name") == "dietary_safety_violation"]
    check("1 dietary_safety_violation step (record b)", len(violation_steps) == 1, f"got {len(violation_steps)}")
    if violation_steps:
        vs = violation_steps[0]
        check("dietary_safety_violation urgency=urgent", vs.get("urgency") == "urgent", f"got {vs.get('urgency')!r}")
        reasoning = vs.get("reasoning") or ""
        check(
            "violation reasoning names student 'Bob Unsafe'",
            "Bob Unsafe" in reasoning,
            f"got: {reasoning!r}",
        )
        check(
            "violation reasoning names meal 'Stir-fry Noodles topped with Chicken'",
            "Stir-fry Noodles topped with Chicken" in reasoning,
            f"got: {reasoning!r}",
        )
        check(
            "violation reasoning says 'confirmed dietary violation'",
            "confirmed dietary violation" in reasoning,
            f"got: {reasoning!r}",
        )
        check(
            "violation tool_input contains menu_item_id",
            "menu_item_id" in vs.get("tool_input", {}),
            f"tool_input={vs.get('tool_input')}",
        )
        print(f"         violation step_index={vs.get('step_index')}")
        print(f"         violation reasoning: {reasoning!r}")

    # ── 3. record (c): allergy_note_unverified ────────────────────────────────
    allergy_steps = [s for s in log_calls if s.get("tool_name") == "allergy_note_unverified"]
    check("1 allergy_note_unverified step (record c)", len(allergy_steps) == 1, f"got {len(allergy_steps)}")
    if allergy_steps:
        als = allergy_steps[0]
        check("allergy_note_unverified urgency=urgent", als.get("urgency") == "urgent", f"got {als.get('urgency')!r}")
        reasoning = als.get("reasoning") or ""
        check(
            "allergy reasoning names student 'Carol Allergy'",
            "Carol Allergy" in reasoning,
            f"got: {reasoning!r}",
        )
        check(
            "allergy reasoning includes verbatim note text",
            "peanut allergy not on file" in reasoning,
            f"got: {reasoning!r}",
        )
        check(
            "allergy reasoning says 'human verification'",
            "human verification" in reasoning,
            f"got: {reasoning!r}",
        )
        print(f"         allergy step_index={als.get('step_index')}")
        print(f"         allergy reasoning: {reasoning!r}")

    # ── 4. record (a): safe row → no safety step ──────────────────────────────
    safe_row_steps = [
        s for s in log_calls
        if s.get("tool_input", {}).get("student_name") == "Alice Safe"
    ]
    check("no safety step for record (a) safe=True student", len(safe_row_steps) == 0, f"got {len(safe_row_steps)}")
    all_tool_names = [s.get("tool_name") for s in log_calls]
    print(f"         all logged tool_names: {all_tool_names}")

    # ── 5. call_count not consumed by safety logging ──────────────────────────
    cap_steps = [s for s in log_calls if s.get("tool_name") == "max_calls_reached"]
    check("no max_calls_reached step (cap not consumed)", len(cap_steps) == 0, f"got {len(cap_steps)}")

    # ── 6. step_index uniqueness ──────────────────────────────────────────────
    step_indices = [s.get("step_index") for s in log_calls]
    check(
        "all step_indices unique (no UNIQUE constraint collision)",
        len(step_indices) == len(set(step_indices)),
        f"step_indices={step_indices}",
    )
    print(f"         step_indices: {step_indices}")

    # ── 7. total log calls = 3 ────────────────────────────────────────────────
    check(
        "total log_agent_step calls = 3 (compose + violation + allergy)",
        len(log_calls) == 3,
        f"got {len(log_calls)}: {all_tool_names}",
    )

    print(f"\n=== unit test: {PASS} passed, {FAIL} failed ===\n")


def test_safety_records_skipped_on_error() -> None:
    """
    compose_session_order dispatch returns is_error=True (e.g. DB failure).
    Result is an error dict with no 'safety_records' key.
    Guard must not crash and must not log any safety steps.
    """
    global PASS, FAIL
    saved_pass, saved_fail = PASS, FAIL
    print("\n=== test_safety_records_skipped_on_error ===")
    print("    Setup: compose_session_order dispatch returns is_error=True\n")

    turn1 = _response(
        _text_block("Composing order."),
        _tool_use_block("compose_session_order", "id-err", {"session_slot_id": 5, "session_date": "2026-08-04"}),
    )
    turn2 = _response(_text_block("Tool call failed."))

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [turn1, turn2]

    log_calls: list[dict] = []

    def fake_log(**kwargs) -> int:
        log_calls.append(kwargs)
        return len(log_calls)

    def fake_dispatch_error(tool_name: str, tool_input: dict, run_id: int, step_index: int):
        return {"error": True, "type": "DBError", "message": "connection refused"}, True

    with (
        patch("src.agent.loop.anthropic.Anthropic", return_value=mock_client),
        patch("src.agent.loop.create_agent_run", return_value=88),
        patch("src.agent.loop.complete_agent_run"),
        patch("src.agent.loop.log_agent_step", side_effect=fake_log),
        patch("src.agent.loop.dispatch", side_effect=fake_dispatch_error),
        patch("src.agent.loop._load_system_prompt", return_value="SYSTEM PROMPT"),
        patch("src.agent.loop.settings") as mock_settings,
    ):
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.agent_model = "claude-sonnet-4-6"
        mock_settings.max_tool_calls_per_run = 15

        run("T-72h order trigger")

    safety_steps = [
        s for s in log_calls
        if s.get("tool_name") in ("dietary_safety_violation", "allergy_note_unverified")
    ]
    check(
        "no safety steps on is_error=True (guard short-circuits at not is_error)",
        len(safety_steps) == 0,
        f"got {len(safety_steps)}",
    )
    cso_err = [s for s in log_calls if s.get("tool_name") == "compose_session_order"]
    if cso_err:
        check("compose error step urgency=urgent", cso_err[0].get("urgency") == "urgent", f"got {cso_err[0].get('urgency')!r}")
        print(f"         compose error urgency={cso_err[0].get('urgency')!r}")

    print(f"\n=== error-guard test: {PASS - saved_pass} passed, {FAIL - saved_fail} failed ===\n")


# ── PART 2 — integration check (real DB) ─────────────────────────────────────

# JPC Tuesday: session_slot_id=2, school_id=2, caterer_id=2 (Terrific)
# Use 2026-08-11 (Tuesday) — different from 2026-08-04 used in test_compose_session_order.py
INTEG_SLOT_ID = 2
INTEG_DATE    = datetime.date(2026, 8, 11)

# Eight real field names emitted by compose_session_order's safety_records list.
# If ANY of these are wrong, loop.py's 3c logging silently fires with None values.
REAL_SAFETY_RECORD_FIELDS = (
    "enrolment_id",
    "student_name",
    "menu_item_id",
    "meal_name",
    "source",
    "dietary_tags",
    "safe",
    "other_allergy_notes",
)


def test_real_safety_records_shape() -> None:
    """
    Integration check: call the REAL compose_session_order against the seeded DB
    and assert that safety_records contains the exact field names loop.py reads.

    This proves the mock fixture matches reality.  A 'reason' key must NOT be
    present — loop.py 3c does not reference it, but the old mock fixture had it,
    which would have been a silent mismatch on the live run.
    """
    global PASS, FAIL
    saved_pass, saved_fail = PASS, FAIL

    print("\n=== PART 2: test_real_safety_records_shape (real DB) ===")
    print(f"    slot={INTEG_SLOT_ID}, date={INTEG_DATE} (JPC Tuesday)\n")

    # Load real .env values — the module-level setdefault installed a fake
    # DATABASE_URL so the unit tests above don't need a real DB.
    # override=True replaces it with the real one for this integration check.
    from dotenv import load_dotenv
    load_dotenv(override=True)

    from src.ingest.db import get_conn
    from src.tools.orders import compose_session_order as real_cso

    # Precondition: no existing order for this slot/date
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM orders WHERE session_slot_id = %s AND session_date = %s",
                (INTEG_SLOT_ID, INTEG_DATE),
            )
            existing = cur.fetchone()
    if existing:
        print(
            f"  SKIP  integration check — order already exists for slot {INTEG_SLOT_ID}/{INTEG_DATE}; "
            f"delete it manually or choose a different date to re-run"
        )
        return

    order_id: int | None = None
    try:
        result = real_cso(INTEG_SLOT_ID, INTEG_DATE)
        order_id = result["order_id"]

        # ── safety_records key exists ─────────────────────────────────────────
        check(
            "'safety_records' key present in real compose_session_order result",
            "safety_records" in result,
            f"keys present: {list(result.keys())}",
        )
        safety_records = result.get("safety_records", [])

        print(f"         real result: order_id={order_id}, "
              f"total_students={result.get('total_students')}, "
              f"len(safety_records)={len(safety_records)}, "
              f"escalations={result.get('escalations')}")

        # ── shape: all eight required fields present on every record ──────────
        if safety_records:
            for i, rec in enumerate(safety_records):
                for field in REAL_SAFETY_RECORD_FIELDS:
                    check(
                        f"safety_records[{i}] has field '{field}'",
                        field in rec,
                        f"keys={list(rec.keys())}",
                    )

            # ── no 'reason' field — the old mock had it, the real function doesn't ──
            spurious_fields = [
                f"safety_records[{i}] has unexpected 'reason' field"
                for i, rec in enumerate(safety_records)
                if "reason" in rec
            ]
            check(
                "no 'reason' field in any safety_record (mock was wrong to include it)",
                len(spurious_fields) == 0,
                "; ".join(spurious_fields) if spurious_fields else "",
            )

            # ── 'safe' is always bool, not None — important for the `not` check ──
            non_bool_safe = [
                f"safety_records[{i}] safe={rec.get('safe')!r} (not bool)"
                for i, rec in enumerate(safety_records)
                if not isinstance(rec.get("safe"), bool)
            ]
            check(
                "all safety_records[*].safe are bool (True or False, never None)",
                len(non_bool_safe) == 0,
                "; ".join(non_bool_safe) if non_bool_safe else "",
            )

            # ── 'meal_name' is non-empty string — loop.py reasoning uses !r ──
            no_meal_name = [
                f"safety_records[{i}] meal_name={rec.get('meal_name')!r}"
                for i, rec in enumerate(safety_records)
                if not rec.get("meal_name")
            ]
            check(
                "all safety_records[*].meal_name are non-empty (loop reasoning uses meal_name)",
                len(no_meal_name) == 0,
                "; ".join(no_meal_name) if no_meal_name else "",
            )

            # Print first record so the shape is visible
            first = safety_records[0]
            print(f"         sample record[0]: {first}")
        else:
            print("         safety_records is empty — cohort may be 0 on this date; "
                  "shape checks skipped (no rows to inspect)")

    finally:
        if order_id is not None:
            from src.ingest.db import get_conn as gc
            with gc() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM orders WHERE id = %s", (order_id,))
                conn.commit()
            print(f"         cleanup: deleted order {order_id} (CASCADE → order_lines)")

    print(f"\n=== integration check: {PASS - saved_pass} passed, {FAIL - saved_fail} failed ===\n")


if __name__ == "__main__":
    test_safety_records_logging()
    test_safety_records_skipped_on_error()
    test_real_safety_records_shape()
    total_pass = PASS
    total_fail = FAIL
    print(f"=== TOTAL: {total_pass} passed, {total_fail} failed ===")
    if total_fail:
        sys.exit(1)
