#!/usr/bin/env python
"""
scripts/test_loop_cap.py

Test STEP 3b: hard-cap logic.

Setup: MAX=2, model returns 3 tool_use blocks in its first response.
Expected sequence:
  - Block id-a: dispatched (call_count → 1), logged, non-error tool_result
  - Block id-b: dispatched (call_count → 2), logged, non-error tool_result
  - Block id-c: cap_count(2) >= MAX(2) → max_calls_reached urgent step logged
                (once), is_error tool_result, continue (not break)
  - messages appended: assistant turn + 3 tool_results
  - cap_hit=True → one UNCOUNTED final summarising call (no tools param)
  - complete_agent_run("[CAP HIT at 2/2] ...")

No real API or DB. All infrastructure + dispatch mocked.
"""
from __future__ import annotations

import json
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


# ── test ─────────────────────────────────────────────────────────────────────

def test_hard_cap() -> None:
    print("\n=== test_hard_cap: MAX=2, first response has 3 tool_use blocks ===")
    print("    Expected: 2 dispatched, 1 is_error'd, 1 urgent step, 1 final call\n")

    # First response: reasoning text + 3 tool_use blocks
    first_resp = _response(
        _text_block("I need to look up three session slots."),
        _tool_use_block("get_session_slot", "id-a", {"session_slot_id": 1}),
        _tool_use_block("get_session_slot", "id-b", {"session_slot_id": 2}),
        _tool_use_block("get_session_slot", "id-c", {"session_slot_id": 3}),
    )

    # Final (summary) response: text only — no tool_use blocks
    summary_resp = _response(
        _text_block(
            "Completed 2 of 3 tool calls (slots 1 and 2). "
            "Slot 3 was not reached due to the tool-call cap."
        )
    )

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [first_resp, summary_resp]

    log_calls: list[dict] = []
    complete_calls: list[tuple] = []

    def fake_log(**kwargs) -> int:
        log_calls.append(kwargs)
        return len(log_calls)

    def fake_complete(run_id: int, notes: str) -> None:
        complete_calls.append((run_id, notes))

    def fake_dispatch(tool_name: str, tool_input: dict, run_id: int, step_index: int):
        return {"session_slot_id": tool_input.get("session_slot_id"), "found": True}, False

    with (
        patch("src.agent.loop.anthropic.Anthropic", return_value=mock_client),
        patch("src.agent.loop.create_agent_run", return_value=42),
        patch("src.agent.loop.complete_agent_run", side_effect=fake_complete),
        patch("src.agent.loop.log_agent_step", side_effect=fake_log),
        patch("src.agent.loop.dispatch", side_effect=fake_dispatch),
        patch("src.agent.loop._load_system_prompt", return_value="SYSTEM PROMPT"),
        patch("src.agent.loop.settings") as mock_settings,
    ):
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.agent_model = "claude-sonnet-4-6"
        mock_settings.max_tool_calls_per_run = 2

        run("T-72h order trigger")

    # ── 1. Total model calls = 2 (1 main + 1 final summary) ──────────────────
    n_calls = mock_client.messages.create.call_count
    check(
        "messages.create called exactly 2 times (1 main + 1 final)",
        n_calls == 2,
        f"got {n_calls}",
    )

    # ── 2. Final call has NO 'tools' parameter → can't recurse ───────────────
    final_call = mock_client.messages.create.call_args_list[1]
    final_kwargs = final_call.kwargs
    check(
        "final summary call has no 'tools' parameter (can't recurse)",
        "tools" not in final_kwargs,
        f"final_kwargs keys: {list(final_kwargs.keys())}",
    )
    print(f"         final call kwargs keys:  {list(final_kwargs.keys())}")
    print(f"         final call max_tokens:   {final_kwargs.get('max_tokens')}")

    # ── 3. complete_agent_run called once with [CAP HIT prefix ───────────────
    check(
        "complete_agent_run called exactly once",
        len(complete_calls) == 1,
        f"got {len(complete_calls)} calls",
    )
    if complete_calls:
        _, notes = complete_calls[0]
        check(
            "complete_agent_run note starts '[CAP HIT'",
            notes.startswith("[CAP HIT"),
            f"got: {notes!r}",
        )
        print(f"         complete_agent_run note: {notes!r}")

    # ── 4. Exactly 1 urgent max_calls_reached step ────────────────────────────
    cap_steps = [s for s in log_calls if s.get("tool_name") == "max_calls_reached"]
    check(
        "exactly 1 max_calls_reached step logged (not one per remaining block)",
        len(cap_steps) == 1,
        f"got {len(cap_steps)} cap steps",
    )
    if cap_steps:
        cs = cap_steps[0]
        check(
            "max_calls_reached urgency=urgent",
            cs.get("urgency") == "urgent",
            f"got urgency={cs.get('urgency')!r}",
        )
        print(f"         max_calls_reached step_index: {cs.get('step_index')}")
        print(f"         max_calls_reached tool_input: {cs.get('tool_input')}")
        print(f"         max_calls_reached reasoning:  {cs.get('reasoning')!r}")

    # ── 5. Two dispatched steps (id-a and id-b) before cap ────────────────────
    dispatched_steps = [s for s in log_calls if s.get("tool_name") == "get_session_slot"]
    check(
        "2 get_session_slot steps logged (dispatched before cap)",
        len(dispatched_steps) == 2,
        f"got {len(dispatched_steps)}",
    )
    if dispatched_steps:
        print(
            f"         dispatched steps: "
            + ", ".join(
                f"step_index={s['step_index']} "
                f"session_slot_id={s['tool_input'].get('session_slot_id')}"
                for s in dispatched_steps
            )
        )

    # ── 6. 3 tool_results sent in the user turn (one per block) ──────────────
    # These are in the messages list passed to the final summarising call.
    final_messages = final_kwargs.get("messages", [])
    # The last user turn in the messages list should contain the tool_results.
    user_turns_with_list_content = [
        m for m in final_messages
        if m.get("role") == "user" and isinstance(m.get("content"), list)
    ]
    check(
        "at least 1 user turn with list content in final call messages",
        len(user_turns_with_list_content) >= 1,
        f"got {len(user_turns_with_list_content)} such turns",
    )
    if user_turns_with_list_content:
        tr = user_turns_with_list_content[-1]["content"]
        check(
            "3 tool_results present (one per block including cap-tripped)",
            len(tr) == 3,
            f"got {len(tr)}",
        )
        if len(tr) >= 3:
            check(
                "id-a tool_result is_error=False (dispatched OK)",
                tr[0].get("is_error") is False,
                f"got is_error={tr[0].get('is_error')!r}",
            )
            check(
                "id-b tool_result is_error=False (dispatched OK)",
                tr[1].get("is_error") is False,
                f"got is_error={tr[1].get('is_error')!r}",
            )
            check(
                "id-c tool_result is_error=True (cap-tripped)",
                tr[2].get("is_error") is True,
                f"got is_error={tr[2].get('is_error')!r}",
            )
            cap_content = json.loads(tr[2]["content"])
            check(
                "id-c content type=HardCap",
                cap_content.get("type") == "HardCap",
                f"got: {cap_content}",
            )
            print(f"         tool_results[0] tool_use_id={tr[0].get('tool_use_id')} is_error={tr[0].get('is_error')}")
            print(f"         tool_results[1] tool_use_id={tr[1].get('tool_use_id')} is_error={tr[1].get('is_error')}")
            print(f"         tool_results[2] tool_use_id={tr[2].get('tool_use_id')} is_error={tr[2].get('is_error')}")
            print(f"         tool_results[2] cap content: {cap_content}")

    # ── total ─────────────────────────────────────────────────────────────────
    print(f"\n=== cap test: {PASS} passed, {FAIL} failed ===\n")


def test_business_shortfall_urgency() -> None:
    """
    A dispatched tool returning is_error=False with a business-signal dict
    (e.g. check_weekly_moq with shortfall > 0) must log urgency='informational',
    NOT 'none'. 'none' = grey/collapsed in the decision log — invisible.
    'informational' = green, visible as part of the audit trail.

    Business escalation (add_note with 'notable'/'urgent') is the MODEL's job.
    The loop step is the audit trail; it must be visible.
    """
    print("\n=== test_business_shortfall_urgency: is_error=False → informational, not none ===\n")

    # Turn 1: model calls check_weekly_moq (one tool_use block)
    turn1 = _response(
        _text_block("Checking weekly MOQ for caterer 1."),
        _tool_use_block("check_weekly_moq", "id-moq", {"caterer_id": 1, "week_of": "2026-06-02"}),
    )
    # Turn 2: model finishes (no tool_use blocks — end_turn)
    turn2 = _response(
        _text_block("MOQ shortfall detected. Filing escalation via add_note.")
    )

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [turn1, turn2]

    log_calls: list[dict] = []

    def fake_log(**kwargs) -> int:
        log_calls.append(kwargs)
        return len(log_calls)

    def fake_complete(run_id: int, notes: str) -> None:
        pass

    # Business-signal shape (b): is_error=False, result is a shortfall dict
    def fake_dispatch(tool_name: str, tool_input: dict, run_id: int, step_index: int):
        return {
            "total_items": 10,
            "moq_applicable": 60,
            "shortfall": 50,
            "shortfall_cents": 500,
        }, False  # is_error=False — this is NOT a system error

    with (
        patch("src.agent.loop.anthropic.Anthropic", return_value=mock_client),
        patch("src.agent.loop.create_agent_run", return_value=99),
        patch("src.agent.loop.complete_agent_run", side_effect=fake_complete),
        patch("src.agent.loop.log_agent_step", side_effect=fake_log),
        patch("src.agent.loop.dispatch", side_effect=fake_dispatch),
        patch("src.agent.loop._load_system_prompt", return_value="SYSTEM PROMPT"),
        patch("src.agent.loop.settings") as mock_settings,
    ):
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.agent_model = "claude-sonnet-4-6"
        mock_settings.max_tool_calls_per_run = 15  # high cap, never hit

        run("quality check trigger")

    moq_steps = [s for s in log_calls if s.get("tool_name") == "check_weekly_moq"]
    check(
        "1 check_weekly_moq step logged",
        len(moq_steps) == 1,
        f"got {len(moq_steps)}",
    )
    if moq_steps:
        s = moq_steps[0]
        urgency = s.get("urgency")
        check(
            "shortfall (is_error=False) logs urgency='informational' (not 'none')",
            urgency == "informational",
            f"got urgency={urgency!r} — 'none' would make this invisible in the decision log",
        )
        check(
            "shortfall does NOT log urgency='none'",
            urgency != "none",
            f"got urgency={urgency!r}",
        )
        print(f"         urgency={urgency!r}")
        print(f"         tool_output_full={s.get('tool_output_full')}")
        print(f"         (model would use add_note to escalate this to 'notable')")

    print(f"\n=== shortfall urgency test: {PASS} passed, {FAIL} failed ===\n")


if __name__ == "__main__":
    test_hard_cap()
    test_business_shortfall_urgency()
    if FAIL:
        sys.exit(1)
