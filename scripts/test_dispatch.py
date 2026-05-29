#!/usr/bin/env python3
"""
scripts/test_dispatch.py

Unit tests for src.agent.loop.dispatch() and _serialise().

Tests all three observation shapes:
  (a) success with data       → (_serialise(result), False)
  (b) business empty/signal   → (None or shortfall_dict, False)
  (c) system error            → ({"error": True, ...}, True)

Key assertion: is_error=True ONLY on shape (c).

All tool calls are mocked — no database connection required.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date, datetime, time as time_
from decimal import Decimal
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock, call

from src.agent.loop import dispatch, _serialise

BRISBANE = ZoneInfo("Australia/Brisbane")

PASS_COUNT = 0
FAIL_COUNT = 0


def _run(label: str, fn):
    global PASS_COUNT, FAIL_COUNT
    try:
        fn()
        print(f"  PASS  {label}")
        PASS_COUNT += 1
    except Exception as exc:
        import traceback
        print(f"  FAIL  {label}: {exc}")
        traceback.print_exc()
        FAIL_COUNT += 1


# =============================================================================
# SHAPE (a) — success with data
# =============================================================================

def test_shape_a_dict():
    """Tool returns a dict → (_serialise(dict), False). is_error=False."""
    mock_fn = MagicMock(return_value={"order_id": 42, "total_cost_cents": 1500})

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"mock_tool": mock_fn}):
        result, is_error = dispatch("mock_tool", {}, run_id=1, step_index=0)

    assert is_error is False, f"Expected is_error=False, got {is_error!r}"
    assert result == {"order_id": 42, "total_cost_cents": 1500}
    print(f"         result={result!r}, is_error={is_error}")


def test_shape_a_list():
    """Tool returns a list → (_serialise(list), False)."""
    mock_fn = MagicMock(return_value=[{"enrolment_id": 1}, {"enrolment_id": 2}])

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"mock_tool": mock_fn}):
        result, is_error = dispatch("mock_tool", {}, run_id=1, step_index=0)

    assert is_error is False
    assert result == [{"enrolment_id": 1}, {"enrolment_id": 2}]
    print(f"         result={result!r}, is_error={is_error}")


def test_shape_a_bool():
    """item_is_safe_for_enrolment returns bool — passes through as bool."""
    mock_fn = MagicMock(return_value=True)

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"mock_tool": mock_fn}):
        result, is_error = dispatch("mock_tool", {}, run_id=1, step_index=0)

    assert is_error is False
    assert result is True
    print(f"         result={result!r} (type={type(result).__name__}), is_error={is_error}")


# =============================================================================
# SHAPE (b) — business empty or signal
# =============================================================================

def test_shape_b_none():
    """
    Tool returns None (no absence filed, no request, no rotation meal, etc.)
    → (None, False). This is NOT an error — it's a business signal meaning
    'nothing found, use the fallback path'.
    """
    mock_fn = MagicMock(return_value=None)

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"mock_tool": mock_fn}):
        result, is_error = dispatch("mock_tool", {}, run_id=1, step_index=0)

    assert is_error is False, f"Expected is_error=False for None result, got {is_error!r}"
    assert result is None
    print(f"         result={result!r}, is_error={is_error}  (None = business-empty, not error)")


def test_shape_b_shortfall_dict():
    """
    check_weekly_moq returns a dict with a shortfall signal → (dict, False).
    shortfall > 0 is a business event the agent inspects; is_error stays False.
    """
    shortfall = {
        "total_items":    8,
        "moq_applicable": 10,
        "shortfall":      2,
        "shortfall_cents": 1800,
    }
    mock_fn = MagicMock(return_value=shortfall)

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"mock_tool": mock_fn}):
        result, is_error = dispatch("mock_tool", {}, run_id=1, step_index=0)

    assert is_error is False, f"Expected is_error=False for shortfall dict, got {is_error!r}"
    assert result["shortfall"] == 2
    assert result["shortfall_cents"] == 1800
    print(f"         result={result!r}, is_error={is_error}  (shortfall=2 but NOT an error)")


def test_shape_b_empty_list():
    """get_sessions_needing_orders returns [] (no sessions due) → ([], False)."""
    mock_fn = MagicMock(return_value=[])

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"mock_tool": mock_fn}):
        result, is_error = dispatch("mock_tool", {}, run_id=1, step_index=0)

    assert is_error is False
    assert result == []
    print(f"         result={result!r}, is_error={is_error}")


# =============================================================================
# SHAPE (c) — system error (exception)
# =============================================================================

def test_shape_c_value_error():
    """
    Tool raises ValueError → ({"error": True, "type": "ValueError", ...}, True).
    is_error=True ONLY for this shape.
    """
    mock_fn = MagicMock(side_effect=ValueError("session_slot_id 999 not found"))

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"mock_tool": mock_fn}):
        result, is_error = dispatch("mock_tool", {}, run_id=1, step_index=0)

    assert is_error is True,  f"Expected is_error=True for exception, got {is_error!r}"
    assert result["error"] is True
    assert result["type"] == "ValueError"
    assert "session_slot_id 999 not found" in result["message"]
    print(f"         result={result!r}, is_error={is_error}")


def test_shape_c_runtime_error():
    """Tool raises RuntimeError → error_dict with correct type name."""
    mock_fn = MagicMock(side_effect=RuntimeError("DB connection lost"))

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"mock_tool": mock_fn}):
        result, is_error = dispatch("mock_tool", {}, run_id=1, step_index=0)

    assert is_error is True
    assert result["type"] == "RuntimeError"
    assert result["error"] is True
    assert "DB connection lost" in result["message"]
    print(f"         result={result!r}, is_error={is_error}")


def test_shape_c_unknown_tool():
    """Calling a tool name not in TOOL_REGISTRY → error_dict, is_error=True."""
    result, is_error = dispatch("does_not_exist", {}, run_id=1, step_index=0)

    assert is_error is True, f"Expected is_error=True for unknown tool, got {is_error!r}"
    assert result["error"] is True
    assert result["type"] == "UnknownTool"
    assert "does_not_exist" in result["message"]
    print(f"         result={result!r}, is_error={is_error}")


# =============================================================================
# CRITICAL INVARIANT: is_error=True ONLY on shape (c)
# =============================================================================

def test_is_error_only_on_shape_c():
    """
    Explicit cross-shape assertion: shapes (a) and (b) must have is_error=False;
    shape (c) must have is_error=True. This is the Anthropic API boundary:
    is_error=False is a normal result (even null); is_error=True signals tool failure.
    """
    # Shape (a): data
    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"t": MagicMock(return_value={"x": 1})}):
        _, is_err_a = dispatch("t", {}, run_id=1, step_index=0)

    # Shape (b): None
    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"t": MagicMock(return_value=None)}):
        _, is_err_b_none = dispatch("t", {}, run_id=1, step_index=0)

    # Shape (b): shortfall dict
    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"t": MagicMock(return_value={"shortfall": 5})}):
        _, is_err_b_dict = dispatch("t", {}, run_id=1, step_index=0)

    # Shape (c): exception
    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"t": MagicMock(side_effect=Exception("boom"))}):
        _, is_err_c = dispatch("t", {}, run_id=1, step_index=0)

    assert is_err_a is False,     f"Shape (a): expected False, got {is_err_a}"
    assert is_err_b_none is False, f"Shape (b) None: expected False, got {is_err_b_none}"
    assert is_err_b_dict is False, f"Shape (b) dict: expected False, got {is_err_b_dict}"
    assert is_err_c is True,       f"Shape (c): expected True, got {is_err_c}"
    print(f"         is_error: (a)={is_err_a}, (b/None)={is_err_b_none}, (b/dict)={is_err_b_dict}, (c)={is_err_c}")
    print(f"         is_error=True ONLY on shape (c) ✓")


# =============================================================================
# add_note special case
# =============================================================================

def test_add_note_notable():
    """add_note calls log_agent_step with label as tool_name. Returns (None, False)."""
    with patch("src.agent.loop.log_agent_step") as mock_log:
        result, is_error = dispatch(
            "add_note",
            {
                "label":   "sustained_decline_detected",
                "body":    "4w mean 2.8 < floor 3.0 (threshold 0.5 below 12w mean 3.4)",
                "urgency": "notable",
            },
            run_id=5,
            step_index=7,
        )

    assert is_error is False, f"Expected is_error=False for add_note, got {is_error!r}"
    assert result is None

    mock_log.assert_called_once_with(
        run_id=5,
        step_index=7,
        tool_name="sustained_decline_detected",
        tool_input={"body": "4w mean 2.8 < floor 3.0 (threshold 0.5 below 12w mean 3.4)"},
        tool_output_full=None,
        reasoning=None,
        urgency="notable",
    )
    print(f"         result={result!r}, is_error={is_error}")
    print(f"         log_agent_step called: {mock_log.call_args}")


def test_add_note_urgent():
    """add_note with urgency='urgent' passes urgency through correctly."""
    with patch("src.agent.loop.log_agent_step") as mock_log:
        result, is_error = dispatch(
            "add_note",
            {
                "label":   "dietary_violation",
                "body":    "Student A assigned halal-only meal but also requires vegetarian",
                "urgency": "urgent",
            },
            run_id=3,
            step_index=2,
        )

    assert is_error is False
    assert result is None
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["urgency"] == "urgent"
    assert call_kwargs["tool_name"] == "dietary_violation"
    assert call_kwargs["run_id"] == 3
    assert call_kwargs["step_index"] == 2
    print(f"         urgency='urgent' ✓, tool_name='{call_kwargs['tool_name']}' ✓")


def test_add_note_label_becomes_tool_name():
    """The label field — not the string 'add_note' — becomes tool_name in agent_steps."""
    with patch("src.agent.loop.log_agent_step") as mock_log:
        dispatch(
            "add_note",
            {"label": "moq_shortfall_noted", "body": "week shortfall $18.00", "urgency": "informational"},
            run_id=1,
            step_index=0,
        )

    logged_tool_name = mock_log.call_args.kwargs["tool_name"]
    assert logged_tool_name == "moq_shortfall_noted", (
        f"Expected label 'moq_shortfall_noted' as tool_name, got {logged_tool_name!r}"
    )
    assert logged_tool_name != "add_note", "tool_name must be the label, not 'add_note'"
    print(f"         agent_steps.tool_name='{logged_tool_name}' (not 'add_note') ✓")


# =============================================================================
# Type coercion
# =============================================================================

def test_coerce_date_session_date():
    """'YYYY-MM-DD' string → date object for params mapped in _PARAM_TYPES."""
    received: dict = {}

    def capture(**kwargs):
        received.update(kwargs)
        return {"order_id": 99}

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"compose_session_order": capture}):
        result, is_error = dispatch(
            "compose_session_order",
            {"session_slot_id": 2, "session_date": "2026-08-04"},
            run_id=1,
            step_index=0,
        )

    assert is_error is False
    assert isinstance(received["session_date"], date), (
        f"Expected date, got {type(received['session_date']).__name__}"
    )
    assert received["session_date"] == date(2026, 8, 4)
    assert isinstance(received["session_slot_id"], int)
    print(f"         session_date={received['session_date']!r} (type={type(received['session_date']).__name__}) ✓")


def test_coerce_date_absence_date():
    """absence_date: 'YYYY-MM-DD' → date object."""
    received: dict = {}

    def capture(**kwargs):
        received.update(kwargs)
        return None

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"get_absence": capture}):
        dispatch("get_absence", {"enrolment_id": 5, "absence_date": "2026-07-15"}, run_id=1, step_index=0)

    assert isinstance(received["absence_date"], date)
    assert received["absence_date"] == date(2026, 7, 15)
    print(f"         absence_date={received['absence_date']!r} ✓")


def test_coerce_date_exclusion_session_date():
    """get_exclusions uses session_date (not as_of) — corrected from locked design."""
    received: dict = {}

    def capture(**kwargs):
        received.update(kwargs)
        return []

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"get_exclusions": capture}):
        dispatch("get_exclusions", {"school_id": 1, "session_date": "2026-08-05"}, run_id=1, step_index=0)

    assert isinstance(received["session_date"], date)
    assert received["session_date"] == date(2026, 8, 5)
    print(f"         session_date={received['session_date']!r} ✓ (corrected from locked design's 'as_of')")


def test_coerce_date_check_weekly_moq_week_of():
    """check_weekly_moq week_of: 'YYYY-MM-DD' → date (corrected from locked design's as_of: datetime)."""
    received: dict = {}

    def capture(**kwargs):
        received.update(kwargs)
        return {"total_items": 10, "moq_applicable": 10, "shortfall": 0, "shortfall_cents": 0}

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"check_weekly_moq": capture}):
        dispatch("check_weekly_moq", {"caterer_id": 1, "week_of": "2026-08-04"}, run_id=1, step_index=0)

    assert isinstance(received["week_of"], date), (
        f"Expected date, got {type(received['week_of']).__name__}"
    )
    assert received["week_of"] == date(2026, 8, 4)
    print(f"         week_of={received['week_of']!r} (type={type(received['week_of']).__name__}) ✓")


def test_coerce_datetime_naive_to_brisbane():
    """Naive datetime string → tz-aware Brisbane datetime."""
    received: dict = {}

    def capture(**kwargs):
        received.update(kwargs)
        return []

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"get_sessions_needing_orders": capture}):
        dispatch(
            "get_sessions_needing_orders",
            {"as_of": "2026-08-01T15:00:00"},
            run_id=1,
            step_index=0,
        )

    assert isinstance(received["as_of"], datetime)
    assert received["as_of"].tzinfo is not None, "Naive datetime was not made tz-aware"
    assert str(received["as_of"].tzinfo) == "Australia/Brisbane"
    assert received["as_of"] == datetime(2026, 8, 1, 15, 0, 0, tzinfo=BRISBANE)
    print(f"         as_of (naive→Brisbane)={received['as_of']!r} ✓")


def test_coerce_datetime_aware_passthrough():
    """Already-tz-aware datetime string keeps its tzinfo unchanged."""
    received: dict = {}

    def capture(**kwargs):
        received.update(kwargs)
        return []

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"get_sessions_needing_orders": capture}):
        dispatch(
            "get_sessions_needing_orders",
            {"as_of": "2026-08-01T05:00:00+00:00"},
            run_id=1,
            step_index=0,
        )

    assert received["as_of"].tzinfo is not None, "tz-aware datetime lost its tzinfo"
    print(f"         as_of (already-aware)={received['as_of']!r} ✓")


def test_coerce_datetime_get_feedback_since():
    """get_feedback_since since_timestamp: ISO string → datetime (corrected from locked design)."""
    received: dict = {}

    def capture(**kwargs):
        received.update(kwargs)
        return []

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"get_feedback_since": capture}):
        dispatch(
            "get_feedback_since",
            {"since_timestamp": "2026-05-01T00:00:00"},
            run_id=1,
            step_index=0,
        )

    assert isinstance(received["since_timestamp"], datetime), (
        f"Expected datetime, got {type(received['since_timestamp']).__name__}"
    )
    assert received["since_timestamp"].tzinfo is not None
    print(f"         since_timestamp={received['since_timestamp']!r} ✓")


def test_as_of_injection_when_omitted():
    """
    When Claude omits as_of for get_sessions_needing_orders, dispatch injects
    datetime.now(BRISBANE). The real Python function requires as_of (not optional).
    """
    received: dict = {}

    def capture(**kwargs):
        received.update(kwargs)
        return []

    before = datetime.now(tz=BRISBANE)

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"get_sessions_needing_orders": capture}):
        dispatch("get_sessions_needing_orders", {}, run_id=1, step_index=0)

    after = datetime.now(tz=BRISBANE)

    assert "as_of" in received, "as_of was not injected when omitted"
    assert isinstance(received["as_of"], datetime)
    assert received["as_of"].tzinfo is not None, "Injected as_of is not tz-aware"
    assert before <= received["as_of"] <= after, (
        f"Injected as_of {received['as_of']!r} outside expected window "
        f"[{before!r}, {after!r}]"
    )
    print(f"         injected as_of={received['as_of']!r} (within [{before.isoformat()}, {after.isoformat()}]) ✓")


def test_non_coerced_params_passthrough():
    """Integer and string params that are NOT in _PARAM_TYPES pass through unchanged."""
    received: dict = {}

    def capture(**kwargs):
        received.update(kwargs)
        return []

    with patch.dict("src.agent.loop.TOOL_REGISTRY", {"get_enrolment_dietary_tags": capture}):
        dispatch("get_enrolment_dietary_tags", {"enrolment_id": 42}, run_id=1, step_index=0)

    assert received["enrolment_id"] == 42
    assert isinstance(received["enrolment_id"], int)
    print(f"         enrolment_id={received['enrolment_id']!r} passes through as int ✓")


# =============================================================================
# _serialise
# =============================================================================

def test_serialise_date():
    result = _serialise(date(2026, 8, 4))
    assert result == "2026-08-04", f"Got {result!r}"
    print(f"         date(2026,8,4) → {result!r} ✓")


def test_serialise_datetime_aware():
    dt = datetime(2026, 8, 4, 15, 0, 0, tzinfo=BRISBANE)
    result = _serialise(dt)
    assert isinstance(result, str)
    assert "2026-08-04" in result
    assert "15:00:00" in result
    print(f"         datetime(tz-aware) → {result!r} ✓")


def test_serialise_datetime_before_date():
    """datetime is a subclass of date; _serialise must check datetime first."""
    dt = datetime(2026, 8, 4, 12, 0, 0)
    result = _serialise(dt)
    # Must include time component — if date was checked first, we'd get "2026-08-04" only
    assert "T" in result or "12:00:00" in result, (
        f"datetime serialised as plain date (wrong order): {result!r}"
    )
    print(f"         datetime→'{result}' (contains time component, not just date) ✓")


def test_serialise_time():
    t = time_(17, 30, 0)
    result = _serialise(t)
    assert result == "17:30:00", f"Got {result!r}"
    print(f"         time(17,30) → {result!r} ✓")


def test_serialise_decimal():
    result = _serialise(Decimal("10.00"))
    assert isinstance(result, float)
    assert result == 10.0
    print(f"         Decimal('10.00') → {result!r} (type={type(result).__name__}) ✓")


def test_serialise_none():
    assert _serialise(None) is None
    print(f"         None → None ✓")


def test_serialise_primitives_passthrough():
    assert _serialise(42) == 42
    assert _serialise(3.14) == 3.14
    assert _serialise("hello") == "hello"
    assert _serialise(True) is True
    assert _serialise(False) is False
    print(f"         int/float/str/bool pass through unchanged ✓")


def test_serialise_nested_dict():
    obj = {
        "session_date": date(2026, 8, 4),
        "dinner_time":  time_(17, 30),
        "gst_rate":     Decimal("10.00"),
        "amount":       1500,
        "nested":       {"subtotal": Decimal("750"), "date": date(2026, 8, 5)},
    }
    s = _serialise(obj)

    assert s["session_date"] == "2026-08-04"
    assert s["dinner_time"] == "17:30:00"
    assert isinstance(s["gst_rate"], float) and s["gst_rate"] == 10.0
    assert s["amount"] == 1500
    assert isinstance(s["nested"]["subtotal"], float)
    assert s["nested"]["date"] == "2026-08-05"
    print(f"         nested dict → {s} ✓")


def test_serialise_list():
    obj = [date(2026, 8, 1), date(2026, 8, 2), {"score": Decimal("4.5")}]
    s = _serialise(obj)

    assert s[0] == "2026-08-01"
    assert s[1] == "2026-08-02"
    assert isinstance(s[2]["score"], float)
    print(f"         list → {s} ✓")


def test_serialise_session_slot_dict():
    """Realistic get_session_slot return value with time objects from psycopg."""
    slot = {
        "id":          3,
        "school_id":   2,
        "day_of_week": 2,
        "start_time":  time_(15, 30),
        "dinner_time": time_(17, 30),
        "end_time":    time_(18, 30),
        "room":        "Building A, Room 4",
        "active":      True,
        "created_at":  datetime(2026, 1, 1, 0, 0, 0, tzinfo=BRISBANE),
        "updated_at":  datetime(2026, 1, 1, 0, 0, 0, tzinfo=BRISBANE),
    }
    s = _serialise(slot)

    assert s["start_time"] == "15:30:00"
    assert s["dinner_time"] == "17:30:00"
    assert s["end_time"] == "18:30:00"
    assert s["active"] is True
    assert isinstance(s["created_at"], str)
    assert "2026-01-01" in s["created_at"]
    print(f"         session_slot with time objects → {s} ✓")


# =============================================================================
# MAIN
# =============================================================================

TESTS = [
    # Shape (a)
    ("shape_a_dict",                test_shape_a_dict),
    ("shape_a_list",                test_shape_a_list),
    ("shape_a_bool",                test_shape_a_bool),
    # Shape (b)
    ("shape_b_none",                test_shape_b_none),
    ("shape_b_shortfall_dict",      test_shape_b_shortfall_dict),
    ("shape_b_empty_list",          test_shape_b_empty_list),
    # Shape (c)
    ("shape_c_value_error",         test_shape_c_value_error),
    ("shape_c_runtime_error",       test_shape_c_runtime_error),
    ("shape_c_unknown_tool",        test_shape_c_unknown_tool),
    # Cross-shape is_error invariant
    ("is_error_only_on_shape_c",    test_is_error_only_on_shape_c),
    # add_note
    ("add_note_notable",            test_add_note_notable),
    ("add_note_urgent",             test_add_note_urgent),
    ("add_note_label_is_tool_name", test_add_note_label_becomes_tool_name),
    # Type coercion
    ("coerce_date_session_date",    test_coerce_date_session_date),
    ("coerce_date_absence_date",    test_coerce_date_absence_date),
    ("coerce_date_exclusion",       test_coerce_date_exclusion_session_date),
    ("coerce_date_week_of",         test_coerce_date_check_weekly_moq_week_of),
    ("coerce_datetime_naive",       test_coerce_datetime_naive_to_brisbane),
    ("coerce_datetime_aware",       test_coerce_datetime_aware_passthrough),
    ("coerce_datetime_since_ts",    test_coerce_datetime_get_feedback_since),
    ("as_of_injection",             test_as_of_injection_when_omitted),
    ("non_coerced_passthrough",     test_non_coerced_params_passthrough),
    # _serialise
    ("serialise_date",              test_serialise_date),
    ("serialise_datetime_aware",    test_serialise_datetime_aware),
    ("serialise_datetime_before_date", test_serialise_datetime_before_date),
    ("serialise_time",              test_serialise_time),
    ("serialise_decimal",           test_serialise_decimal),
    ("serialise_none",              test_serialise_none),
    ("serialise_primitives",        test_serialise_primitives_passthrough),
    ("serialise_nested_dict",       test_serialise_nested_dict),
    ("serialise_list",              test_serialise_list),
    ("serialise_session_slot",      test_serialise_session_slot_dict),
]

if __name__ == "__main__":
    print("\n=== test_dispatch.py ===\n")
    for label, fn in TESTS:
        print(f"  {label}:")
        _run(label, fn)

    total = PASS_COUNT + FAIL_COUNT
    print(f"\n{'=' * 50}")
    print(f"  {PASS_COUNT}/{total} passed, {FAIL_COUNT} failed")
    print(f"{'=' * 50}\n")

    if FAIL_COUNT > 0:
        sys.exit(1)
