"""
src/tools/infrastructure.py
Agent run lifecycle and step logging tools.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Literal

from psycopg.types.json import Jsonb

from src.ingest.db import get_conn


def create_agent_run(trigger_reason: str) -> int:
    """Create an agent_runs row. Returns run_id."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO agent_runs (trigger_reason) VALUES (%s) RETURNING id",
                (trigger_reason,),
            )
            run_id: int = cur.fetchone()[0]
        conn.commit()
    return run_id


def complete_agent_run(run_id: int, notes: str) -> None:
    """Set completed_at and write summary notes on an agent_runs row."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE agent_runs SET completed_at = now(), notes = %s WHERE id = %s",
                (notes, run_id),
            )
        conn.commit()


def log_agent_step(
    run_id: int,
    step_index: int,
    tool_name: str | None,
    tool_input: dict | None,
    tool_output_full: dict | None,
    reasoning: str | None,
    urgency: Literal["urgent", "notable", "informational", "none"] = "none",
) -> int:
    """
    Append one step record to agent_steps. Returns the new step_id.

    UNIQUE (run_id, step_index) enforced at the DB level — callers must not
    reuse a step_index within the same run.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_steps
                    (run_id, step_index, tool_name, tool_input,
                     tool_output_full, reasoning, urgency)
                VALUES (%s, %s, %s, %s, %s, %s, %s::step_urgency)
                RETURNING id
                """,
                (
                    run_id,
                    step_index,
                    tool_name,
                    Jsonb(tool_input) if tool_input is not None else None,
                    Jsonb(tool_output_full) if tool_output_full is not None else None,
                    reasoning,
                    urgency,
                ),
            )
            step_id: int = cur.fetchone()[0]
        conn.commit()
    return step_id


def check_and_resolve_crashed_runs(staleness_minutes: int = 30) -> list[int]:
    """
    Find runs that started more than staleness_minutes ago and never completed.
    Close them by setting completed_at = now() with a crash note.
    Returns the list of closed run_ids.

    V4 has no status column — completed_at IS NULL means still running.
    Stale incomplete runs are closed here so the new run starts with a clean slate.
    """
    note = (
        f"CRASHED: closed after exceeding {staleness_minutes}-minute staleness threshold"
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE agent_runs
                SET completed_at = now(), notes = %s
                WHERE completed_at IS NULL
                  AND started_at < now() - %s
                RETURNING id
                """,
                (note, timedelta(minutes=staleness_minutes)),
            )
            crashed = [r[0] for r in cur.fetchall()]
        conn.commit()
    return crashed
