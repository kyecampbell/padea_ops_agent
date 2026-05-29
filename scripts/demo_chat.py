#!/usr/bin/env python
"""
scripts/demo_chat.py — interactive demo console for the Padea ops agent.

Talk to the agent in plain English and drive its REAL workflows on a fake
"demo clock", e.g.:

    @2026-05-30 16:00 it's 72h before Tuesday's session — run the orders that are due
    @2026-06-01 15:30 it's Monday afternoon — send the weekly payment summary and check the inbox

Each message becomes one full agent run (Sonnet + all 27 tools). The demo
clock only changes what the agent treats as "now" for time-dependent tools
(ordering window, weekly summary, rolling means). It does NOT fake anything
real: the inbound Gmail poll still reads the live inbox at the true clock,
emails still send/queue for real, the decision log records every step.

Commands:
    /clock <iso>      set the persistent demo clock   (e.g. /clock 2026-06-01 15:30)
    /clock            show the current demo clock
    /real             show the real wall-clock time
    /sessions [days]  list upcoming sessions + the exact @clock that triggers each
    /auto on|off      skip / require the "Proceed?" confirm before each run
    /help             show this help
    /quit  /exit      leave

Inline clock:
    Prefix any message with @<iso> to set the clock for just that message:
        @2026-05-30 16:00 run whatever orders are due now

Usage:  python scripts/demo_chat.py
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"),
    override=True,
)

from config.settings import settings
from src.agent.loop import run
from src.ingest.db import get_conn

BRISBANE = ZoneInfo("Australia/Brisbane")

# matches a leading "@2026-05-30 16:00 <rest>" or "@2026-05-30T16:00:00 <rest>"
_INLINE_CLOCK = re.compile(
    r"^@(\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?)\s+(.*)$",
    re.DOTALL,
)


def parse_clock(raw: str) -> datetime:
    """Parse an ISO-ish string into a Brisbane-aware datetime. Raises ValueError."""
    dt = datetime.fromisoformat(raw.strip().replace(" ", "T"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BRISBANE)
    return dt


def fmt(dt: datetime) -> str:
    return dt.astimezone(BRISBANE).strftime("%A %d %B %Y, %I:%M %p AEST")


def show_sessions(days: int) -> None:
    """List active sessions in the next `days` days and the @clock that triggers each."""
    now = datetime.now(BRISBANE)
    H = settings.order_hours_before_session
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ss.id, ss.day_of_week, ss.start_time, sc.name, sc2.name
            FROM session_slots ss
            JOIN schools  sc  ON sc.id  = ss.school_id
            LEFT JOIN caterers sc2 ON sc2.id = sc.current_caterer_id
            WHERE ss.active = true
            ORDER BY ss.day_of_week, ss.start_time
            """
        )
        rows = cur.fetchall()

    upcoming: list[tuple[datetime, datetime, int, str, str]] = []
    for slot_id, dow, start_time, school, caterer in rows:
        for offset in range(0, days + 1):
            d = (now + timedelta(days=offset)).date()
            if d.isoweekday() != dow:
                continue
            session_dt = datetime.combine(d, start_time, tzinfo=BRISBANE)
            trigger_dt = session_dt - timedelta(hours=H)
            upcoming.append((trigger_dt, session_dt, slot_id, school, caterer or "—"))

    upcoming.sort(key=lambda t: t[0])
    if not upcoming:
        print(f"  (no active sessions in the next {days} days)")
        return

    print(f"\n  Upcoming sessions (next {days} days) — T-{H}h trigger clock:\n")
    for trigger_dt, session_dt, slot_id, school, caterer in upcoming:
        print(f"  slot {slot_id:>2}  {school} / {caterer}")
        print(f"           session : {fmt(session_dt)}")
        print(f"           order at : @{trigger_dt.strftime('%Y-%m-%d %H:%M')}   "
              f"(say: @{trigger_dt.strftime('%Y-%m-%d %H:%M')} run the orders that are due)")
        print()


def report(before_id: int) -> None:
    """Compact read-only report of what the last run produced."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, started_at, completed_at, notes FROM agent_runs "
            "WHERE id > %s ORDER BY id",
            (before_id,),
        )
        runs = cur.fetchall()
        if not runs:
            print("  (no new agent_run was created)")
            return
        run_id, started, completed, notes = runs[-1]
        print(f"\n  ── run {run_id} ── {started} → {completed}")

        cur.execute(
            "SELECT step_index, tool_name, urgency, reasoning FROM agent_steps "
            "WHERE run_id=%s ORDER BY step_index",
            (run_id,),
        )
        steps = cur.fetchall()
        print(f"  steps: {len(steps)}")
        for idx, tool, urg, reasoning in steps:
            flag = "" if urg in (None, "none") else f"  [{urg.upper()}]"
            print(f"    [{idx:02d}] {tool}{flag}")
            rsn = (reasoning or "").strip().replace("\n", " ")
            if rsn:
                print(f"         {rsn[:160]}" + (" …" if len(rsn) > 160 else ""))

        cur.execute(
            "SELECT id, email_type, status, intended_to_address FROM outbound_emails "
            "WHERE related_run_id=%s ORDER BY id",
            (run_id,),
        )
        emails = cur.fetchall()
        if emails:
            print(f"  emails: {len(emails)}")
            for eid, etype, status, to in emails:
                print(f"    email {eid}  {etype}  [{status}]  → {to}")

        if notes:
            print(f"  notes: {notes.strip()[:200]}")
    print()


def build_trigger(message: str, clock: datetime) -> str:
    return (
        f"DEMO CONTROL — the current date and time is "
        f"{clock.isoformat()} ({fmt(clock)}). Treat this as \"now\" for this run. "
        f"For any time-dependent tool (get_sessions_needing_orders, "
        f"generate_weekly_summary, compute_rolling_mean), use this exact value "
        f"as the as_of / reference time.\n\n"
        f"Operator request: {message}"
    )


def rebuild_renderer() -> None:
    """Regenerate renderer/index.html so the dashboard reflects the run just made.
    Read-only against the DB; failure here must never break the demo run."""
    try:
        from scripts.build_renderer import main as build_main
        build_main()
        print("  renderer refreshed → renderer/index.html\n")
    except Exception as exc:  # noqa: BLE001 — demo console, never crash on rebuild
        print(f"  [renderer rebuild failed: {type(exc).__name__}: {exc}]\n")


def do_run(message: str, clock: datetime, auto: bool) -> None:
    trigger = build_trigger(message, clock)
    print(f"\n  demo clock : {fmt(clock)}")
    print(f"  request    : {message}")
    if not auto:
        ans = input("  Proceed?  [Enter = yes / s = skip] ").strip().lower()
        if ans == "s":
            print("  skipped.\n")
            return

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM agent_runs")
        before = cur.fetchone()[0]

    print("\n  --- agent running ---", flush=True)
    try:
        run(trigger, as_of_override=clock)
    except Exception as exc:  # noqa: BLE001 — demo console, surface anything
        import traceback
        print(f"\n  [EXCEPTION: {type(exc).__name__}: {exc}]")
        traceback.print_exc()
    print("  --- done ---")
    report(before)
    rebuild_renderer()


HELP = __doc__


def main() -> None:
    clock = datetime.now(BRISBANE)
    auto = False
    print("Padea ops agent — demo console.  Type /help for commands, /quit to leave.")
    print(f"Demo clock starts at real now: {fmt(clock)}")
    print(f"Agent model: {settings.agent_model}   email mode: {settings.email_mode}\n")

    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            return
        if not line:
            continue

        if line in ("/quit", "/exit"):
            print("bye.")
            return
        if line in ("/help", "/?"):
            print(HELP)
            continue
        if line == "/real":
            print(f"  real now: {fmt(datetime.now(BRISBANE))}\n")
            continue
        if line.startswith("/clock"):
            arg = line[len("/clock"):].strip()
            if not arg:
                print(f"  demo clock: {fmt(clock)}\n")
            else:
                try:
                    clock = parse_clock(arg)
                    print(f"  demo clock set: {fmt(clock)}\n")
                except ValueError:
                    print("  could not parse — use e.g. /clock 2026-06-01 15:30\n")
            continue
        if line.startswith("/sessions"):
            arg = line[len("/sessions"):].strip()
            days = int(arg) if arg.isdigit() else 10
            show_sessions(days)
            continue
        if line.startswith("/auto"):
            arg = line[len("/auto"):].strip().lower()
            auto = arg in ("on", "true", "1", "yes")
            print(f"  auto-proceed: {'ON' if auto else 'OFF'}\n")
            continue
        if line.startswith("/"):
            print("  unknown command — /help for the list\n")
            continue

        # inline clock?  "@2026-05-30 16:00 <message>"
        m = _INLINE_CLOCK.match(line)
        if m:
            try:
                clock = parse_clock(m.group(1))
            except ValueError:
                print("  bad inline @clock — ignoring it\n")
            message = m.group(2).strip() if m else line
        else:
            message = line

        do_run(message, clock, auto)


if __name__ == "__main__":
    main()
