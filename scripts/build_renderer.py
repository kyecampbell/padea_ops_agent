"""
scripts/build_renderer.py

Padea Operations Agent — decision-log / dashboard renderer (Block C).

READ-ONLY against the DB: SELECT statements only. No writes, no agent calls.
Queries agent_runs + agent_steps and writes ONE self-contained static HTML file
to renderer/index.html — opens in any browser, no server, no framework, no live
CDN, no auth. Everything is inlined.

Stage 1: decision-log timeline only (run sections + step cards + urgency colours
+ demo-view toggle). Email bodies (Stage 2), current-state panel (Stage 3),
charts (Stage 4), and the style pass (Stage 5) come later.

Run:  python scripts/build_renderer.py
"""
from __future__ import annotations

import html
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import settings
from src.ingest.db import get_conn

# =============================================================================
# DEMO VIEW — runs shown by default, in narrative order.
#
# LIVE MODE (default): leave this EMPTY. The demo view then shows every run in
# the DB, oldest-first — so after a reset you just talk to the agent and each
# new run appears in the timeline as it happens, no editing needed.
#
# CURATED MODE: set explicit ids (e.g. [16, 9, 20, 18]) to pin a hand-picked
# narrative order; anything else drops to the full-history toggle.
# =============================================================================
DEMO_RUN_IDS: list[int] = []


def resolve_demo_run_ids(runs: list[dict]) -> list[int]:
    """Ordered run ids for the curated demo view.

    If DEMO_RUN_IDS is set, use it verbatim. If empty (live mode), fall back to
    every run in the DB sorted oldest-first by started_at, so a live demo
    (reset -> talk to the agent) surfaces each new run automatically.
    """
    if DEMO_RUN_IDS:
        return DEMO_RUN_IDS
    _epoch = datetime.min.replace(tzinfo=timezone.utc)
    return [r["id"] for r in sorted(runs, key=lambda r: r["started_at"] or _epoch)]

_OUT_PATH = Path(__file__).parent.parent / "renderer" / "index.html"
_LOGO_PATH = Path(__file__).parent.parent / "renderer" / "padealogo.webp"


def load_logo_data_uri() -> str | None:
    """Base64-embed the PADEA logo so the output HTML is fully self-contained
    and renders the brand offline (no web URL, no external fetch)."""
    import base64
    try:
        raw = _LOGO_PATH.read_bytes()
    except OSError:
        return None
    return "data:image/webp;base64," + base64.b64encode(raw).decode("ascii")

# Urgency ordering: urgent first, then notable, informational, none.
_URGENCY_RANK = {"urgent": 0, "notable": 1, "informational": 2, "none": 3}
_URGENCY_ORDER = ["urgent", "notable", "informational", "none"]

# All run dates/times are shown in Brisbane time (the operator's timezone).
_TZ_BNE = ZoneInfo("Australia/Brisbane")
_WEEKDAY = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
            4: "Friday", 5: "Saturday", 6: "Sunday"}
_MONTH = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May",
          6: "June", 7: "July", 8: "August", 9: "September", 10: "October",
          11: "November", 12: "December"}


# =============================================================================
# DATA ACCESS (READ-ONLY)
# =============================================================================

def fetch_runs() -> list[dict]:
    """Return every agent_runs row with its steps attached, newest run last."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, trigger_reason, started_at, completed_at, notes
                FROM agent_runs
                ORDER BY id
                """
            )
            runs = [
                {
                    "id": r[0],
                    "trigger_reason": r[1],
                    "started_at": r[2],
                    "completed_at": r[3],
                    "notes": r[4],
                    "steps": [],
                }
                for r in cur.fetchall()
            ]
            by_id = {run["id"]: run for run in runs}

            cur.execute(
                """
                SELECT run_id, step_index, tool_name, tool_input,
                       tool_output_full, reasoning, urgency, created_at
                FROM agent_steps
                ORDER BY run_id, step_index
                """
            )
            for s in cur.fetchall():
                run = by_id.get(s[0])
                if run is None:
                    continue
                run["steps"].append(
                    {
                        "step_index": s[1],
                        "tool_name": s[2],
                        "tool_input": s[3],
                        "tool_output_full": s[4],
                        "reasoning": s[5],
                        "urgency": s[6],
                        "created_at": s[7],
                    }
                )
    return runs


def fetch_emails() -> dict[int, dict]:
    """Return every outbound_emails row keyed by id (the actual artifacts)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email_type, status, subject, rendered_body,
                       intended_to_address, sent_at, queued_for_approval_at,
                       related_run_id, related_order_id
                FROM outbound_emails
                """
            )
            return {
                r[0]: {
                    "id": r[0],
                    "email_type": r[1],
                    "status": r[2],
                    "subject": r[3],
                    "rendered_body": r[4],
                    "intended_to_address": r[5],
                    "sent_at": r[6],
                    "queued_for_approval_at": r[7],
                    "related_run_id": r[8],
                    "related_order_id": r[9],
                }
                for r in cur.fetchall()
            }


def fetch_recent_disruptions(back_days: int = 14, fwd_days: int = 21) -> list[dict]:
    """Whole-school / year-level exclusions whose start_date falls in a window
    around now (Brisbane) — recent past plus near future — so the operator can
    see sessions that were or will be cancelled (e.g. a school with no session
    this week). Read-only. School-holiday closures are excluded: they are a
    known term-boundary event, not an operational disruption worth flagging."""
    now = datetime.now(tz=_TZ_BNE).date()
    lo, hi = now - timedelta(days=back_days), now + timedelta(days=fwd_days)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.start_date, sc.name, e.reason, e.year_levels_excluded
                FROM exclusions e
                JOIN schools sc ON sc.id = e.school_id
                WHERE e.start_date BETWEEN %s AND %s
                  AND e.reason NOT ILIKE '%%school holidays%%'
                ORDER BY e.start_date, sc.name
                """,
                (lo, hi),
            )
            rows = cur.fetchall()
    out: list[dict] = []
    for start_date, school_name, reason, year_levels in rows:
        out.append({
            "date": start_date,
            "school_name": school_name,
            "reason": reason,
            "year_levels": list(year_levels or []),
            "is_past": start_date < now,
        })
    return out


def fetch_upcoming_sessions(hours: int = 168) -> list[dict]:
    """Active session slots whose next occurrence falls within `hours` of now
    (Brisbane). day_of_week is ISO weekday (Mon=1..Sun=7). Read-only.

    Default window is 7 days: a strict 72h window shows nothing when "now" is a
    Friday (the next sessions are Monday, ~73h out), so the panel uses a one-week
    forward view to reliably show upcoming state on any film day."""
    now = datetime.now(tz=_TZ_BNE)
    horizon = now + timedelta(hours=hours)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ss.id, sc.name, ss.day_of_week, ss.start_time,
                       ss.dinner_time, ss.room
                FROM session_slots ss
                JOIN schools sc ON sc.id = ss.school_id
                WHERE ss.active = true
                """
            )
            slots = cur.fetchall()

    out: list[dict] = []
    for slot_id, school_name, dow, start_time, dinner_time, room in slots:
        # next date on/after today matching this ISO weekday
        delta = (dow - now.isoweekday()) % 7
        cand_date = now.date() + timedelta(days=delta)
        session_dt = datetime.combine(cand_date, start_time, tzinfo=_TZ_BNE)
        if session_dt < now:  # today's slot already passed → next week
            session_dt += timedelta(days=7)
        if now <= session_dt <= horizon:
            out.append({
                "slot_id": slot_id,
                "school_name": school_name,
                "session_dt": session_dt,
                "dinner_time": dinner_time,
                "room": room,
            })
    out.sort(key=lambda s: s["session_dt"])
    return out


def fetch_chart_data() -> dict:
    """Per-caterer weekly satisfaction (mean rating) and weekly cost, plus the
    school->caterer mapping for the selector. Read-only SELECTs only.

    Cost basis: each weekly bar is the SAME figure the caterer's weekly summary
    invoices as TOTAL DUE -- meals subtotal + (delivery_fee x sessions that week),
    with one GST round at the boundary per the caterer's GST treatment. So a bar
    reconciles to the cent with the consolidated-summary email for that week
    (e.g. Terrific, week of 2026-06-01 -> $1,441.55), instead of the old
    ex-GST/ex-delivery meal subtotal which did not.

    Weeks shown: per caterer, the operational baseline (weeks that have feedback)
    plus any week the agent actually closed with a weekly consolidated summary
    (read from the generate_weekly_summary step's week_of, normalised to its
    Monday). This keeps every bar a full, comparable weekly total and drops stray
    single-session test orders that were never part of a summarised week. The rule
    is structural, not hard-coded to dates, so a live re-run at film time picks up
    its fresh summary week automatically."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, current_caterer_id FROM schools ORDER BY id"
            )
            schools_raw = cur.fetchall()

            cur.execute(
                """SELECT id, name, price_includes_gst, gst_rate_percent,
                          delivery_fee_cents
                   FROM caterers"""
            )
            cat_rows = cur.fetchall()

            cur.execute(
                """
                SELECT caterer_id, date_trunc('week', submitted_at)::date,
                       avg(rating)::float, count(*)
                FROM feedback
                WHERE rating IS NOT NULL
                GROUP BY 1, 2
                ORDER BY 1, 2
                """
            )
            sat_rows = cur.fetchall()

            # Per-SCHOOL weekly satisfaction. Feedback carries no school directly,
            # so resolve it through the session it belongs to: manager rows via
            # order_id -> orders, tutor rows via order_line_id -> order_lines ->
            # orders, then orders.session_slot_id -> session_slots.school_id.
            #
            # Per (school, week) prefer the STUDENT (tutor) average where any tutor
            # ratings exist; otherwise fall back to the session-manager rating. This
            # gives the Terrific demo schools (JPC, MacGregor) real decimal student
            # lines while non-tutor-rated schools (MBBC, ISHS, the GYG pair) keep
            # their manager integers and don't go blank. `n` reports the number of
            # ratings actually shown (student count when student, else manager count).
            cur.execute(
                """
                WITH fb AS (
                    SELECT f.rating, f.source, f.submitted_at,
                           COALESCE(o_mgr.session_slot_id,
                                    o_tut.session_slot_id) AS slot_id
                    FROM feedback f
                    LEFT JOIN orders      o_mgr ON o_mgr.id = f.order_id
                    LEFT JOIN order_lines ol    ON ol.id    = f.order_line_id
                    LEFT JOIN orders      o_tut ON o_tut.id = ol.order_id
                    WHERE f.rating IS NOT NULL
                ),
                per AS (
                    SELECT ss.school_id AS school_id,
                           date_trunc('week', fb.submitted_at)::date AS week,
                           avg(fb.rating) FILTER (WHERE fb.source = 'tutor')::float   AS tutor_avg,
                           count(*)       FILTER (WHERE fb.source = 'tutor')          AS tutor_n,
                           avg(fb.rating) FILTER (WHERE fb.source = 'manager')::float AS mgr_avg,
                           count(*)       FILTER (WHERE fb.source = 'manager')        AS mgr_n
                    FROM fb
                    JOIN session_slots ss ON ss.id = fb.slot_id
                    GROUP BY 1, 2
                )
                SELECT school_id, week,
                       CASE WHEN tutor_n > 0 THEN tutor_avg ELSE mgr_avg END,
                       CASE WHEN tutor_n > 0 THEN tutor_n   ELSE mgr_n   END,
                       (tutor_n > 0) AS is_student
                FROM per
                ORDER BY 1, 2
                """
            )
            school_sat_rows = cur.fetchall()

            cur.execute(
                """
                SELECT caterer_id, date_trunc('week', session_date)::date,
                       sum(total_cost_cents)::int, count(*)::int
                FROM orders
                GROUP BY 1, 2
                ORDER BY 1, 2
                """
            )
            cost_rows = cur.fetchall()

            # Per-SCHOOL weekly cost. Recomputed cleanly from meal COUNT x the
            # caterer's flat per-item price (the source menus charge one rate per
            # caterer, e.g. Terrific $20.50/item) + delivery x sessions, so it is
            # consistent across historical orders (which baked delivery into
            # total_cost_cents) and agent-composed orders (which did not), with no
            # delivery double-count. GST is applied once at the boundary per the
            # caterer's treatment. Reconciles to the weekly summary TOTAL DUE.
            cur.execute(
                """
                SELECT ss.school_id, date_trunc('week', o.session_date)::date,
                       o.caterer_id, sum(o.total_items)::int, count(*)::int
                FROM orders o
                JOIN session_slots ss ON ss.id = o.session_slot_id
                GROUP BY 1, 2, 3
                ORDER BY 1, 2
                """
            )
            school_cost_rows = cur.fetchall()

            # Flat per-item price per caterer (all menu items share one price).
            cur.execute(
                "SELECT caterer_id, min(price_cents)::int FROM menu_items GROUP BY 1"
            )
            unit_price = {cid: price for cid, price in cur.fetchall()}

            # Weeks the agent actually closed with a consolidated summary, read
            # from structured step input (robust to film-time live re-runs).
            cur.execute(
                """SELECT tool_input FROM agent_steps
                   WHERE tool_name = 'generate_weekly_summary'"""
            )
            summary_step_rows = cur.fetchall()

            # Inputs for the per-bar "N absent · M excluded" labels.
            # Roster = enrolled students per slot (the full expected headcount).
            cur.execute(
                "SELECT session_slot_id, count(*)::int "
                "FROM enrolment_session_slots GROUP BY 1"
            )
            roster_by_slot = {s: n for s, n in cur.fetchall()}
            # School + weekday for each slot, to map an exclusion date to a slot.
            cur.execute("SELECT id, school_id, day_of_week FROM session_slots")
            slot_meta = {sid: (sch, dow) for sid, sch, dow in cur.fetchall()}
            # Meals actually ordered per (slot, week).
            cur.execute(
                """SELECT o.session_slot_id,
                          date_trunc('week', o.session_date)::date,
                          o.total_items
                   FROM orders o"""
            )
            items_by_slot_week = {
                (sid, wk.isoformat()): items for sid, wk, items in cur.fetchall()
            }
            # Whole-session exclusions (no year-level restriction) → cancelled
            # sessions whose roster counts as "excluded" that week.
            cur.execute(
                """SELECT school_id, start_date
                   FROM exclusions
                   WHERE school_id IS NOT NULL
                     AND COALESCE(array_length(year_levels_excluded, 1), 0) = 0"""
            )
            whole_exclusions = {(sch, d) for sch, d in cur.fetchall()}

    caterer_params = {
        cid: {
            "name": name,
            "price_includes_gst": gst_incl,
            "gst_rate": float(rate),
            "delivery_fee_cents": delivery,
        }
        for cid, name, gst_incl, rate, delivery in cat_rows
    }

    # Allowed cost-chart weeks per caterer: operational baseline (feedback weeks)
    # plus any week the agent summarised. Both keep bars to full, comparable weeks.
    allowed_weeks: dict[int, set[str]] = {cid: set() for cid in caterer_params}
    for cid, wk, _mean, _n in sat_rows:
        allowed_weeks.setdefault(cid, set()).add(wk.isoformat())
    for (ti,) in summary_step_rows:
        if not isinstance(ti, dict):
            continue
        cid, wof = ti.get("caterer_id"), ti.get("week_of")
        if cid is None or not wof:
            continue
        try:
            d = date.fromisoformat(wof)
        except (TypeError, ValueError):
            continue
        monday = d - timedelta(days=d.weekday())
        allowed_weeks.setdefault(cid, set()).add(monday.isoformat())

    caterers: dict[int, dict] = {
        cid: {"name": p["name"], "satisfaction": [], "cost": []}
        for cid, p in caterer_params.items()
    }
    for cid, wk, mean, n in sat_rows:
        caterers[cid]["satisfaction"].append(
            {"week": wk.isoformat(), "mean": round(mean, 2), "n": n}
        )
    for cid, wk, meals_cents, n_orders in cost_rows:
        wk_iso = wk.isoformat()
        if wk_iso not in allowed_weeks.get(cid, set()):
            continue  # stray single-session / un-summarised test week
        p = caterer_params[cid]
        ex_subtotal = (meals_cents or 0) + p["delivery_fee_cents"] * n_orders
        if p["price_includes_gst"]:
            grand = ex_subtotal
        else:
            grand = round(ex_subtotal * (1 + p["gst_rate"] / 100))
        caterers[cid]["cost"].append(
            {"week": wk_iso, "dollars": round(grand / 100, 2), "sessions": n_orders}
        )

    # Per-school weekly satisfaction series, keyed by school_id.
    school_satisfaction: dict[int, list[dict]] = {}
    for sid, wk, mean, n, is_student in school_sat_rows:
        school_satisfaction.setdefault(sid, []).append(
            {
                "week": wk.isoformat(),
                "mean": round(mean, 2),
                "n": n,
                "is_student": bool(is_student),
            }
        )

    # Per-school weekly cost series, keyed by school_id. Clean basis: meal count x
    # flat unit price + delivery x sessions, GST-normalised, restricted to the same
    # full/summarised weeks as the satisfaction baseline.
    # Slots grouped by school, for the per-bar absence/exclusion tally.
    slots_by_school: dict[int, list[int]] = {}
    for slot_id, (sch, _dow) in slot_meta.items():
        slots_by_school.setdefault(sch, []).append(slot_id)

    def _absence_tally(sid: int, wk_iso: str) -> tuple[int, int]:
        """For one (school, week): students absent from sessions that ran, plus
        students cut by a whole-session exclusion (no order that week)."""
        wk_start = date.fromisoformat(wk_iso)  # Monday of the ISO week
        absent = excluded = 0
        for slot_id in slots_by_school.get(sid, []):
            roster = roster_by_slot.get(slot_id, 0)
            items = items_by_slot_week.get((slot_id, wk_iso))
            if items is not None:
                absent += max(0, roster - items)
            else:
                _sch, dow = slot_meta[slot_id]
                session_date = wk_start + timedelta(days=dow - 1)
                if (sid, session_date) in whole_exclusions:
                    excluded += roster
        return absent, excluded

    school_cost: dict[int, list[dict]] = {}
    for sid, wk, cid, items_sum, n_orders in school_cost_rows:
        wk_iso = wk.isoformat()
        if wk_iso not in allowed_weeks.get(cid, set()):
            continue  # stray single-session / un-summarised test week
        p = caterer_params[cid]
        ex_subtotal = (items_sum or 0) * unit_price.get(cid, 0) \
            + p["delivery_fee_cents"] * n_orders
        if p["price_includes_gst"]:
            grand = ex_subtotal
        else:
            grand = round(ex_subtotal * (1 + p["gst_rate"] / 100))
        absent, excluded = _absence_tally(sid, wk_iso)
        school_cost.setdefault(sid, []).append(
            {"week": wk_iso, "dollars": round(grand / 100, 2),
             "sessions": n_orders, "absent": absent, "excluded": excluded}
        )

    schools = [
        {
            "id": r[0],
            "name": r[1],
            "caterer_id": r[2],
            "satisfaction": school_satisfaction.get(r[0], []),
            "cost": school_cost.get(r[0], []),
        }
        for r in schools_raw
    ]
    terrific_id = next(
        (cid for cid, p in caterer_params.items() if p["name"] == "Terrific Noodles"),
        None,
    )
    default_school_id = next(
        (s["id"] for s in schools if s["caterer_id"] == terrific_id),
        schools[0]["id"] if schools else None,
    )
    return {
        "schools": schools,
        "caterers": caterers,
        "quality_floor": float(settings.quality_floor),
        "default_school_id": default_school_id,
    }


# =============================================================================
# HELPERS
# =============================================================================

def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def fmt_ts(ts: datetime | None) -> str:
    """Precise Brisbane timestamp for the secondary meta line."""
    if ts is None:
        return "—"
    return ts.astimezone(_TZ_BNE).strftime("%Y-%m-%d %H:%M") + " AEST"


def fmt_run_label(ts: datetime | None) -> str:
    """Human, non-technical Brisbane date/time, e.g. 'Monday 1 June 2026, 3:30 PM'."""
    if ts is None:
        return "(no start time recorded)"
    b = ts.astimezone(_TZ_BNE)
    hour12 = b.hour % 12 or 12
    ampm = "AM" if b.hour < 12 else "PM"
    return (
        f"{_WEEKDAY[b.weekday()]} {b.day} {_MONTH[b.month]} {b.year}, "
        f"{hour12}:{b.minute:02d} {ampm}"
    )


def jsonify(value: object) -> str:
    """Pretty-print a jsonb value (dict/list/scalar) for display."""
    if value is None:
        return "null"
    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def urgency_counts(steps: list[dict]) -> dict[str, int]:
    counts = {u: 0 for u in _URGENCY_ORDER}
    for s in steps:
        counts[s["urgency"]] = counts.get(s["urgency"], 0) + 1
    return counts


def sort_steps(steps: list[dict]) -> list[dict]:
    """Urgent first, then notable, informational, none; then by step_index."""
    return sorted(
        steps,
        key=lambda s: (_URGENCY_RANK.get(s["urgency"], 99), s["step_index"]),
    )


_EMAIL_TOOLS = {"gmail_send", "queue_email_for_approval"}


def email_id_for_step(step: dict) -> int | None:
    """The outbound_emails id a send/queue step produced, from {"value": id}."""
    if step["tool_name"] not in _EMAIL_TOOLS:
        return None
    out = step["tool_output_full"]
    if isinstance(out, dict) and isinstance(out.get("value"), int):
        return out["value"]
    return None


# =============================================================================
# HTML RENDERING
# =============================================================================

_SENT_TYPES_LABEL = {
    "session_order": "Per-session order",
    "weekly_consolidated_summary": "Weekly consolidated summary",
    "warning": "Quality warning",
}


def render_email_card(email: dict) -> str:
    """Render an outbound email as a readable artifact, with status badge and
    (for queued_for_approval) a browser-only Approve & Send button."""
    status = email["status"]
    type_label = _SENT_TYPES_LABEL.get(email["email_type"], email["email_type"])

    parts = [f'<div class="email email--{esc(status)}">']
    parts.append('  <div class="email__head">')
    parts.append(
        f'    <span class="email__kind">EMAIL ARTIFACT — {esc(type_label)}</span>'
    )
    if status == "sent":
        parts.append('    <span class="email__badge email__badge--sent">&#10003; SENT</span>')
    elif status == "queued_for_approval":
        parts.append(
            '    <span class="email__badge email__badge--queued">'
            '&#9208; QUEUED &mdash; AWAITING OPERATOR APPROVAL</span>'
        )
    else:
        parts.append(f'    <span class="email__badge">{esc(status)}</span>')
    parts.append('  </div>')

    parts.append(f'  <div class="email__subject">{esc(email["subject"])}</div>')
    parts.append(
        f'  <div class="email__to">To: {esc(email["intended_to_address"])}</div>'
    )
    parts.append(f'  <pre class="email__body">{esc(email["rendered_body"])}</pre>')

    if status == "queued_for_approval":
        parts.append('  <div class="email__approve">')
        parts.append(
            '    <button type="button" class="approve-btn" '
            'onclick="approveEmail(this)">Approve &amp; Send</button>'
        )
        parts.append(
            '    <span class="demo-note" title="This button only changes the page in '
            'your browser. It does not write to the database and resets on reload.">'
            'demo action &mdash; no DB write, resets on reload</span>'
        )
        parts.append('  </div>')

    parts.append('</div>')
    return "\n".join(parts)


def render_step_card(step: dict, emails: dict[int, dict]) -> str:
    urg = step["urgency"]
    parts = [f'<div class="step step--{esc(urg)}">']
    parts.append('  <div class="step__head">')
    parts.append(f'    <span class="step__idx">{esc(step["step_index"])}</span>')
    parts.append(f'    <span class="step__title">{esc(humanize_tool(step["tool_name"]))}</span>')
    parts.append(f'    <span class="badge badge--{esc(urg)}">{esc(urg)}</span>')
    parts.append('  </div>')

    if step["reasoning"]:
        parts.append(f'  <div class="step__reasoning">{esc(step["reasoning"])}</div>')
    else:
        parts.append('  <div class="step__reasoning step__reasoning--empty">(no reasoning recorded)</div>')

    parts.append(f'  <div class="step__tool">{esc(step["tool_name"])}</div>')
    parts.append('  <details class="step__io">')
    parts.append('    <summary>Technical detail &mdash; inputs &amp; output</summary>')
    parts.append('    <div class="step__iolabel">tool_input</div>')
    parts.append(f'    <pre>{esc(jsonify(step["tool_input"]))}</pre>')
    parts.append('    <div class="step__iolabel">tool_output_full</div>')
    parts.append(f'    <pre>{esc(jsonify(step["tool_output_full"]))}</pre>')
    parts.append('  </details>')

    eid = email_id_for_step(step)
    if eid is not None and eid in emails:
        parts.append(render_email_card(emails[eid]))

    parts.append('</div>')
    return "\n".join(parts)


def render_run_section(run: dict, emails: dict[int, dict]) -> str:
    counts = urgency_counts(run["steps"])
    count_line = " · ".join(f"{counts[u]} {u}" for u in _URGENCY_ORDER)
    steps_sorted = sort_steps(run["steps"])

    parts = ['<section class="run">']
    parts.append('  <header class="run__head">')
    parts.append('    <div class="run__titlebar">')
    parts.append(f'      <h2 class="run__title">{esc(fmt_run_label(run["started_at"]))}</h2>')
    parts.append(f'      <span class="run__id">run {esc(run["id"])}</span>')
    parts.append('    </div>')
    parts.append(f'    <div class="run__trigger">{esc(trigger_kind(run["trigger_reason"]))}</div>')
    parts.append('    <div class="run__meta">')
    parts.append(f'      <span>Completed {esc(fmt_ts(run["completed_at"]))}</span>')
    parts.append(f'      <span class="run__rawtrigger">{esc(run["trigger_reason"])}</span>')
    parts.append('    </div>')
    parts.append(f'    <div class="run__counts">{esc(count_line)}</div>')
    parts.append('  </header>')

    if steps_sorted:
        parts.append('  <div class="run__steps">')
        for step in steps_sorted:
            parts.append(render_step_card(step, emails))
        parts.append('  </div>')
    else:
        parts.append('  <div class="run__steps run__steps--empty">No steps recorded.</div>')

    parts.append('</section>')
    return "\n".join(parts)


_CSS = """
:root {
  /* Semantic colours — these carry MEANING, do not restyle. */
  --urgent: #c0392b;
  --notable: #d68910;
  --informational: #1e8449;
  --none: #9aa0a6;
  /* Neutral chrome — PADEA black/white/grey, calm and considered. */
  --ink: #14161a;
  --ink-soft: #3a3f47;
  --muted: #6b7280;
  --faint: #9097a1;
  --line: #e7e9ec;
  --line-soft: #f0f1f3;
  --bg: #f7f7f8;
  --card: #ffffff;
}
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  margin: 0; color: var(--ink); background: var(--bg); line-height: 1.5;
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}
.wrap { max-width: 920px; margin: 0 auto; padding: 32px 24px 96px; }

.masthead {
  display: flex; align-items: center; gap: 16px;
  padding: 0 0 22px; margin: 0 0 28px; border-bottom: 1px solid var(--line);
}
.masthead__logo { height: 40px; width: auto; display: block; }
.masthead__titles { display: flex; flex-direction: column; }
.page-title {
  font-size: 24px; font-weight: 700; letter-spacing: -0.01em;
  margin: 0 0 3px; color: var(--ink);
}
.page-sub { color: var(--muted); font-size: 13px; margin: 0; max-width: 60ch; }

.run {
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  margin: 0 0 16px; padding: 22px 24px;
  box-shadow: 0 1px 2px rgba(20,22,26,.04);
}
.run__head { border-bottom: 1px solid var(--line-soft); padding-bottom: 14px; margin-bottom: 16px; }
.run__titlebar { display: flex; align-items: baseline; gap: 10px; }
.run__title { font-size: 17px; font-weight: 700; letter-spacing: -0.01em; margin: 0; }
.run__id {
  font-size: 11px; color: var(--faint); font-variant-numeric: tabular-nums;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  background: var(--line-soft); border-radius: 5px; padding: 1px 7px;
}
.run__trigger { font-size: 14px; color: var(--ink-soft); margin-top: 4px; font-weight: 500; }
.run__meta { font-size: 12px; color: var(--muted); margin-top: 6px; display: flex; gap: 14px; flex-wrap: wrap; align-items: baseline; }
.run__rawtrigger {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px;
  color: var(--faint); word-break: break-word;
}
.run__counts { font-size: 12px; color: var(--muted); margin-top: 8px; font-variant-numeric: tabular-nums; }

.run__steps { display: flex; flex-direction: column; gap: 10px; }
.run__steps--empty { color: var(--muted); font-size: 13px; }

.step {
  border: 1px solid var(--line); border-left-width: 3px; border-radius: 8px;
  padding: 14px 16px; background: var(--card);
}
.step--urgent { border-left-color: var(--urgent); }
.step--notable { border-left-color: var(--notable); }
.step--informational { border-left-color: var(--informational); }
.step--none { border-left-color: var(--none); }

.step__head { display: flex; align-items: center; gap: 10px; }
.step__idx {
  flex: 0 0 auto; min-width: 20px; height: 20px; padding: 0 5px;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--faint); font-size: 11px; font-variant-numeric: tabular-nums;
  background: var(--line-soft); border-radius: 5px;
}
.step__title { font-weight: 600; font-size: 15px; color: var(--ink); letter-spacing: -0.005em; }

.badge {
  margin-left: auto; font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .04em; padding: 3px 9px; border-radius: 999px; color: #fff;
}
.badge--urgent { background: var(--urgent); }
.badge--notable { background: var(--notable); }
.badge--informational { background: var(--informational); }
.badge--none { background: var(--none); }

/* Reasoning is the hero of each card. */
.step__reasoning {
  font-size: 14px; line-height: 1.55; color: var(--ink-soft);
  margin: 10px 0 0; white-space: pre-wrap;
}
.step__reasoning--empty { color: var(--faint); font-style: italic; }

/* Raw tool name — demoted to a quiet provenance sub-line. */
.step__tool {
  font-size: 11px; color: var(--faint); margin-top: 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.step__io { font-size: 12px; margin-top: 6px; }
.step__io summary { cursor: pointer; color: var(--muted); user-select: none; font-size: 12px; }
.step__iolabel {
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em;
  color: var(--faint); margin: 8px 0 2px;
}
.step__io pre {
  background: #fbfbfc; border: 1px solid var(--line); border-radius: 6px;
  padding: 8px 10px; overflow-x: auto; font-size: 12px; margin: 2px 0 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--ink-soft);
}

.section-label { font-size: 12px; font-weight: 700; color: var(--faint); text-transform: uppercase; letter-spacing: .08em; margin: 34px 0 14px; }
details.history > summary {
  cursor: pointer; font-size: 14px; font-weight: 600; padding: 14px 16px;
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  user-select: none; color: var(--ink-soft);
}
details.history > summary:hover { background: var(--line-soft); }
details.history[open] > summary { margin-bottom: 16px; }

/* Email artifacts — visually distinct from reasoning/tool cards */
.email {
  margin: 10px 0 2px; border: 1px solid #cfd6e4; border-radius: 6px;
  background: #fbfcfe; box-shadow: 0 1px 2px rgba(16,24,40,.06);
  border-left: 4px solid #7f8fa6; overflow: hidden;
}
.email--sent { border-left-color: var(--informational); }
.email--queued_for_approval { border-left-color: var(--notable); }
.email__head {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 8px 12px; background: #eef2f8; border-bottom: 1px solid #dde3ee;
}
.email__kind {
  font-size: 11px; font-weight: 700; letter-spacing: .04em; color: var(--muted);
  text-transform: uppercase;
}
.email__badge {
  margin-left: auto; font-size: 11px; font-weight: 700; letter-spacing: .02em;
  padding: 3px 9px; border-radius: 999px; color: #fff; white-space: nowrap;
}
.email__badge--sent { background: var(--informational); }
.email__badge--queued { background: var(--notable); }
.email__badge--approved { background: var(--informational); }
.email__subject { font-weight: 600; font-size: 14px; padding: 10px 12px 2px; }
.email__to { font-size: 12px; color: var(--muted); padding: 0 12px 8px; }
.email__body {
  margin: 0; padding: 12px 14px; background: #fff; border-top: 1px dashed #dde3ee;
  white-space: pre-wrap; word-break: break-word; font-size: 13px; line-height: 1.5;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--ink);
}
.email__approve {
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  padding: 14px 16px; background: #fff8ec; border-top: 1px solid #f0e2c4;
}
.approve-btn {
  font-size: 14px; font-weight: 700; color: #fff; background: var(--notable);
  border: none; border-radius: 8px; padding: 11px 22px; cursor: pointer;
  transition: background .15s ease; box-shadow: 0 1px 3px rgba(214,137,16,.35);
}
.approve-btn:hover { background: #b9770e; }
.approve-btn:disabled { background: var(--informational); cursor: default; opacity: .95; }
.demo-note { font-size: 11px; color: var(--muted); font-style: italic; }

/* Current-state panel — the operator's first surface (a hero region) */
.panel {
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 22px 24px; margin: 0 0 20px; box-shadow: 0 1px 3px rgba(20,22,26,.05);
}
.panel__title {
  font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em;
  color: var(--faint); margin-bottom: 18px;
}
.panel__block { margin-bottom: 24px; }
.panel__block:last-child { margin-bottom: 0; }
.panel__h { font-size: 15px; font-weight: 700; margin: 0 0 12px; letter-spacing: -0.005em; }
.panel__empty { font-size: 13px; color: var(--muted); font-style: italic; }

/* Escalations — the most important block, given quiet emphasis (no loud fills). */
.panel__block--escalations { padding: 16px 18px; margin: -4px -6px 24px; border-radius: 10px; background: var(--line-soft); }
.panel__block--escalations .panel__h { font-size: 16px; }

.esc {
  border: 1px solid var(--line); border-left-width: 4px; border-radius: 8px;
  padding: 11px 14px; margin-bottom: 9px; background: var(--card);
}
.esc:last-child { margin-bottom: 0; }
.esc--urgent { border-left-color: var(--urgent); }
.esc--notable, .esc--action { border-left-color: var(--notable); }
.esc--action { background: #fff8ec; }
.esc__row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.esc__what { font-weight: 600; font-size: 13px; }
.esc__when { margin-left: auto; font-size: 11px; color: var(--muted); font-variant-numeric: tabular-nums; }
.esc .badge { margin-left: 0; }
.esc__ctx { font-size: 12px; color: var(--muted); margin-top: 5px; line-height: 1.45; }

.recent {
  border-bottom: 1px solid var(--line); padding: 7px 0;
}
.recent:last-child { border-bottom: none; }
.recent__top { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.recent__date { font-weight: 600; font-size: 13px; }
.recent__kind { font-size: 12px; color: var(--muted); }
.recent__outcome { font-size: 13px; margin-top: 2px; }

.upcoming {
  display: flex; gap: 12px; flex-wrap: wrap; align-items: baseline;
  padding: 6px 0; border-bottom: 1px solid var(--line); font-size: 13px;
}
.upcoming:last-child { border-bottom: none; }
.upcoming__when { font-weight: 600; min-width: 230px; }
.upcoming__room { color: var(--muted); font-size: 12px; }
.upcoming__more { font-size: 12px; color: var(--faint); padding: 8px 0 0; font-style: italic; }

/* Charts (inline SVG, no external library) */
.charts {
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 22px 24px; margin: 0 0 20px; box-shadow: 0 1px 2px rgba(20,22,26,.04);
}
.charts__controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 6px; }
.charts__controls label { font-size: 13px; font-weight: 600; }
#schoolSelect {
  font-size: 13px; padding: 6px 10px; border: 1px solid var(--line);
  border-radius: 6px; background: #fff; color: var(--ink);
}
.charts__caterer { font-size: 13px; color: var(--muted); }
.chart-card { margin-top: 14px; }
.chart-host { width: 100%; }
.chartsvg { width: 100%; height: auto; display: block; }
.chart-note { font-size: 12px; color: var(--muted); margin-top: 4px; }
.chart-note--aside { font-style: italic; }
.chart-scope {
  font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
  color: #2563c9; background: #eaf1fc; border: 1px solid #cfe0fa;
  border-radius: 999px; padding: 1px 8px; margin-left: 6px; vertical-align: middle;
}
.chart-empty { font-size: 13px; color: var(--muted); font-style: italic; padding: 24px 0; }
.chart-pending { color: var(--ink-soft); font-style: normal; }

/* All-schools at-a-glance — operator's first read, every school at once */
.glance { margin: 4px 0 4px; }
.glance__rows { display: flex; flex-direction: column; gap: 7px; margin-top: 10px; }
.glance__row { display: flex; align-items: center; gap: 12px; }
.glance__name {
  flex: 0 0 168px; font-size: 13px; font-weight: 600; text-align: right;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.glance__track {
  position: relative; flex: 1 1 auto; height: 18px; background: #eef0f3;
  border: 1px solid var(--line); border-radius: 4px; overflow: hidden;
}
.glance__floor {
  position: absolute; top: -1px; bottom: -1px; width: 0;
  border-left: 2px dashed var(--urgent); opacity: .55; z-index: 1;
}
.glance__fill { height: 100%; border-radius: 3px 0 0 3px; }
.glance__fill--red { background: var(--urgent); }
.glance__fill--amber { background: var(--notable); }
.glance__fill--green { background: var(--informational); }
.glance__fill--none { background: var(--none); }
.glance__val {
  flex: 0 0 34px; font-size: 13px; font-weight: 700;
  font-variant-numeric: tabular-nums; text-align: left;
}
.glance__val--red { color: var(--urgent); }
.glance__val--amber { color: var(--notable); }
.glance__val--green { color: var(--informational); }
.glance__val--none { color: var(--muted); font-weight: 600; }

.grid { stroke: #eceef1; stroke-width: 1; }
.axislabel { fill: var(--muted); font-size: 11px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
.axistitle { fill: var(--muted); font-size: 12px; font-weight: 600; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
.ptlabel { fill: var(--ink); font-size: 10px; font-variant-numeric: tabular-nums; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.barabs { fill: var(--muted); font-size: 9px; font-variant-numeric: tabular-nums; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.dataline { fill: none; stroke: #2563c9; stroke-width: 2.5; stroke-linejoin: round; stroke-linecap: round; }
.datapt { fill: #2563c9; }
.datapt--bad { fill: var(--urgent); }
.floorline { stroke: var(--urgent); stroke-width: 1.5; stroke-dasharray: 5 4; }
.floorlabel { fill: var(--urgent); font-size: 11px; font-weight: 600; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
.bar { fill: #2f7d4f; }
"""

_APPROVE_JS = """
function approveEmail(btn) {
  var card = btn.closest('.email');
  if (!card) return;
  var badge = card.querySelector('.email__badge');
  if (badge) {
    var now = new Date();
    var t = now.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
    badge.classList.remove('email__badge--queued');
    badge.classList.add('email__badge--approved');
    badge.innerHTML = '\\u2713 APPROVED & SENT \\u2014 ' + t;
  }
  card.classList.remove('email--queued_for_approval');
  card.classList.add('email--sent');
  btn.disabled = true;
  btn.textContent = 'Approved';
}
"""


# =============================================================================
# CURRENT-STATE PANEL (Stage 3) — operator surface above the timeline
# =============================================================================

_TOOL_LABELS = {
    # data lookups
    "get_sessions_needing_orders": "Checked which sessions need orders",
    "get_session_slot": "Looked up the session details",
    "get_enrolments_for_session": "Looked up session enrolments",
    "get_exclusions": "Checked for exclusions",
    "get_year_level_exclusions": "Checked year-level exclusions",
    "get_absence": "Checked for absences",
    "get_meal_request": "Checked the meal request",
    "get_feedback_since": "Checked recent feedback",
    "compute_rolling_mean": "Computed the rolling quality average",
    "caterers_within_range": "Found caterers within range",
    "project_weekly_cost": "Projected weekly cost",
    "check_weekly_moq": "Checked minimum order quantity",
    "read_db": "Read from the database",
    # order composition + sending
    "compose_session_order": "Composed the order",
    "compose_order": "Composed the order",
    "compose_order_email": "Drafted the order email",
    "gmail_send": "Sent the email",
    "queue_email_for_approval": "Queued an email for approval",
    # weekly summary
    "generate_weekly_summary": "Generated the weekly summary",
    "compose_weekly_summary_email": "Drafted the summary email",
    "caterer_swap_analysis": "Analysed alternative caterers",
    # inbound
    "gmail_poll_inbox": "Checked the inbox",
    "classify_inbound_email": "Classified the inbound email",
    # decision / escalation markers
    "sustained_decline_detected": "Detected a sustained quality decline",
    "unclassified_inbound": "Flagged an unclassified email",
    "vo_variant_requested": "Requested a vegetarian option",
    "no_safe_meal": "No safe meal for a student",
    "moq_shortfall": "Flagged a minimum-order shortfall",
    "gmail_send_failure": "Email send failed",
    "max_calls_reached": "Reached the tool-call limit",
    # terminal / status markers
    "order_composed_successfully": "Order composed",
    "order_composed_and_sent": "Order composed and sent",
    "session_order_sent": "Order sent",
    "order_sent": "Order sent",
    "weekly_summary_complete": "Weekly summary complete",
    "run_wrap_up": "Wrapped up the run",
}


def humanize_tool(name: str) -> str:
    return _TOOL_LABELS.get(name, name.replace("_", " ").capitalize())


def step_context(step: dict) -> str:
    """One-line context: reasoning if present, else the decision step's body."""
    txt = (step.get("reasoning") or "").strip()
    if not txt:
        ti = step.get("tool_input")
        if isinstance(ti, dict):
            txt = (ti.get("body") or "").strip()
    txt = " ".join(txt.split())
    return (txt[:180] + "…") if len(txt) > 180 else txt


def trigger_kind(trigger_reason: str | None) -> str:
    tr = trigger_reason or ""
    if "monday_summary" in tr:
        return "Monday weekly consolidated summary"
    if "T-72h order" in tr or "order trigger" in tr:
        return "T-72h per-session order"
    if "inbound" in tr or "poll" in tr.lower():
        return "Scheduled inbound email poll"
    return (tr[:48] + "…") if len(tr) > 48 else (tr or "(no trigger recorded)")


def run_outcome(run: dict, emails: dict[int, dict]) -> str:
    tr = run["trigger_reason"] or ""
    tools = {s["tool_name"] for s in run["steps"]}
    run_emails = [e for e in emails.values() if e["related_run_id"] == run["id"]]
    sent_types = {e["email_type"] for e in run_emails if e["status"] == "sent"}
    queued_types = {e["email_type"] for e in run_emails if e["status"] == "queued_for_approval"}

    bits: list[str] = []
    if "T-72h order" in tr or "order trigger" in tr:
        bits.append(
            "per-session order sent"
            if ("session_order" in sent_types or "gmail_send" in tools)
            else "order composed"
        )
    elif "monday_summary" in tr:
        if "weekly_consolidated_summary" in sent_types or "gmail_send" in tools:
            bits.append("weekly summary sent")
        if "warning" in queued_types or "queue_email_for_approval" in tools:
            bits.append("quality warning queued for approval")
        if "caterer_swap_analysis" in tools:
            bits.append("caterer swap analysed (no change made)")
    elif "inbound" in tr or "poll" in tr.lower():
        if "unclassified_inbound" in tools or any(
            s["urgency"] == "urgent" for s in run["steps"]
        ):
            bits.append("inbound email escalated — operator action needed")
        else:
            bits.append("inbox polled, nothing new")

    if "no_safe_meal" in tools:
        bits.append("no-safe-meal escalation raised")
    if "gmail_send_failure" in tools:
        bits.append("email send failed")
    if "max_calls_reached" in tools:
        bits.append("hit tool-call cap — run aborted")
    if not bits:
        bits.append("completed, no issues")

    s = "; ".join(bits)
    return s[0].upper() + s[1:]


def render_panel(runs: list[dict], emails: dict[int, dict],
                 upcoming: list[dict], disruptions: list[dict]) -> str:
    by_id = {r["id"]: r for r in runs}
    demo_id_list = resolve_demo_run_ids(runs)
    demo_runs = [by_id[rid] for rid in demo_id_list if rid in by_id]

    # --- Part 1: escalations needing attention -------------------------------
    # Action required: queued-for-approval emails on demo runs.
    demo_ids = set(demo_id_list)
    queued = [
        e for e in emails.values()
        if e["status"] == "queued_for_approval" and e["related_run_id"] in demo_ids
    ]
    queued.sort(key=lambda e: e["id"], reverse=True)

    # Flagged: urgent + notable steps on demo runs, newest run first.
    esc_items: list[tuple] = []
    for run in demo_runs:
        for s in run["steps"]:
            if s["urgency"] in ("urgent", "notable"):
                esc_items.append((run, s))
    _epoch = datetime.min.replace(tzinfo=timezone.utc)
    esc_items.sort(
        key=lambda rs: (rs[0]["started_at"] or _epoch, -rs[1]["step_index"]),
        reverse=True,
    )

    p = ['<section class="panel">']
    p.append('  <div class="panel__title">Operator surface</div>')

    # 1. Escalations
    p.append('  <div class="panel__block panel__block--escalations">')
    p.append('    <h3 class="panel__h">Escalations needing attention</h3>')
    if not queued and not esc_items:
        p.append('    <div class="panel__empty">Nothing awaiting action.</div>')
    for e in queued:
        run = by_id.get(e["related_run_id"])
        when = fmt_run_label(run["started_at"]) if run else "—"
        p.append('    <div class="esc esc--action">')
        p.append('      <div class="esc__row">')
        p.append('        <span class="badge badge--notable">action required</span>')
        p.append(f'        <span class="esc__what">A {esc(e["email_type"])} email to '
                 f'{esc(e["intended_to_address"])} is awaiting your approval</span>')
        p.append('      </div>')
        p.append(f'      <div class="esc__ctx">{esc(e["subject"])} · '
                 f'run {esc(e["related_run_id"])} · {esc(when)} · '
                 f'see the Approve &amp; Send control in the timeline below</div>')
        p.append('    </div>')
    for run, s in esc_items:
        urg = s["urgency"]
        p.append(f'    <div class="esc esc--{esc(urg)}">')
        p.append('      <div class="esc__row">')
        p.append(f'        <span class="badge badge--{esc(urg)}">{esc(urg)}</span>')
        p.append(f'        <span class="esc__what">{esc(humanize_tool(s["tool_name"]))}</span>')
        p.append(f'        <span class="esc__when">run {esc(run["id"])} · '
                 f'{esc(fmt_run_label(run["started_at"]))}</span>')
        p.append('      </div>')
        ctx = step_context(s)
        if ctx:
            p.append(f'      <div class="esc__ctx">{esc(ctx)}</div>')
        p.append('    </div>')
    p.append('  </div>')

    # 2. Recent runs
    recent = sorted(runs, key=lambda r: r["started_at"] or _epoch, reverse=True)[:5]
    p.append('  <div class="panel__block">')
    p.append('    <h3 class="panel__h">Recent runs</h3>')
    for run in recent:
        p.append('    <div class="recent">')
        p.append(f'      <div class="recent__top"><span class="recent__date">'
                 f'{esc(fmt_run_label(run["started_at"]))}</span>'
                 f'<span class="recent__kind">{esc(trigger_kind(run["trigger_reason"]))}</span>'
                 f'<span class="run__id">run {esc(run["id"])}</span></div>')
        p.append(f'      <div class="recent__outcome">{esc(run_outcome(run, emails))}</div>')
        p.append('    </div>')
    p.append('  </div>')

    # 3. Recent & upcoming disruptions — cancelled / partially-excluded sessions
    #    in a window around now, so a school with no session this week is visible.
    p.append('  <div class="panel__block">')
    p.append('    <h3 class="panel__h">Recent &amp; upcoming disruptions</h3>')
    if not disruptions:
        p.append('    <div class="panel__empty">No session disruptions in this window.</div>')
    for d in disruptions:
        when = d["date"].strftime("%a %-d %b %Y")
        tag = "was off" if d["is_past"] else "scheduled off"
        scope = (f"Years {', '.join(str(y) for y in d['year_levels'])}"
                 if d["year_levels"] else "whole session")
        p.append('    <div class="upcoming">')
        p.append(f'      <span class="upcoming__when">{esc(when)} · {esc(tag)}</span>'
                 f'<span class="upcoming__school">{esc(d["school_name"])}</span>'
                 f'<span class="upcoming__room">{esc(scope)} &mdash; {esc(d["reason"])}</span>'
                 '</div>')
    p.append('  </div>')

    # 4. Upcoming sessions — next 5, so the panel stays scannable
    p.append('  <div class="panel__block">')
    shown = upcoming[:5]
    extra = len(upcoming) - len(shown)
    head = "Upcoming sessions" + (" (next 5)" if extra > 0 else " (next 7 days)")
    p.append(f'    <h3 class="panel__h">{esc(head)}</h3>')
    if not upcoming:
        p.append('    <div class="panel__empty">No sessions scheduled in the next 7 days.</div>')
    for u in shown:
        p.append('    <div class="upcoming">')
        p.append(f'      <span class="upcoming__when">{esc(fmt_run_label(u["session_dt"]))}</span>'
                 f'<span class="upcoming__school">{esc(u["school_name"])}</span>'
                 f'<span class="upcoming__room">{esc(u["room"])}</span></div>')
    if extra > 0:
        p.append(f'    <div class="upcoming__more">+{extra} more in the next 7 days</div>')
    p.append('  </div>')

    p.append('</section>')
    return "\n".join(p)


# =============================================================================
# CHARTS (Stage 4) — hand-rolled inline SVG, NO external library, NO CDN.
# The chart data is embedded as JSON and rendered client-side into SVG by the
# vanilla JS below, so the file renders fully offline.
# =============================================================================

_CHART_JS = """
(function () {
  var SVGNS = 'http://www.w3.org/2000/svg';
  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  function fmtWeek(iso) {
    var d = new Date(iso + 'T00:00:00');
    return d.getDate() + ' ' + MONTHS[d.getMonth()];
  }
  function el(tag, attrs, text) {
    var e = document.createElementNS(SVGNS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function emptyNote(container, msg) {
    container.innerHTML = '<div class="chart-empty">' + msg + '</div>';
  }
  function niceMax(v) {
    if (v <= 0) return 1;
    var p = Math.pow(10, Math.floor(Math.log10(v)));
    var n = v / p;
    var nice = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
    return nice * p;
  }

  function lineChart(container, series, opts) {
    container.innerHTML = '';
    if (!series || series.length === 0) { emptyNote(container, opts.emptyMsg); return; }
    var W = 660, H = 290, m = { t: 18, r: 20, b: 44, l: 48 };
    var iw = W - m.l - m.r, ih = H - m.t - m.b;
    var ymax = opts.ymax || 5, ymin = 0, n = series.length;
    var xOf = function (i) { return n > 1 ? m.l + i * (iw / (n - 1)) : m.l + iw / 2; };
    var yOf = function (v) { return m.t + ih - (v - ymin) / (ymax - ymin) * ih; };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'chartsvg' });
    for (var g = ymin; g <= ymax; g++) {
      var y = yOf(g);
      svg.appendChild(el('line', { x1: m.l, y1: y, x2: W - m.r, y2: y, class: 'grid' }));
      svg.appendChild(el('text', { x: m.l - 8, y: y + 4, class: 'axislabel', 'text-anchor': 'end' }, g.toFixed(0)));
    }
    if (opts.floor != null) {
      var fy = yOf(opts.floor);
      svg.appendChild(el('line', { x1: m.l, y1: fy, x2: W - m.r, y2: fy, class: 'floorline' }));
      svg.appendChild(el('text', { x: W - m.r, y: fy - 6, class: 'floorlabel', 'text-anchor': 'end' }, opts.floorLabel));
    }
    series.forEach(function (p, i) {
      svg.appendChild(el('text', { x: xOf(i), y: H - m.b + 18, class: 'axislabel', 'text-anchor': 'middle' }, fmtWeek(p.week)));
    });
    var pts = series.map(function (p, i) { return xOf(i) + ',' + yOf(p.value); }).join(' ');
    svg.appendChild(el('polyline', { points: pts, class: 'dataline' }));
    series.forEach(function (p, i) {
      var below = opts.floor != null && p.value < opts.floor;
      svg.appendChild(el('circle', { cx: xOf(i), cy: yOf(p.value), r: 4, class: 'datapt' + (below ? ' datapt--bad' : '') }));
      svg.appendChild(el('text', { x: xOf(i), y: yOf(p.value) - 9, class: 'ptlabel', 'text-anchor': 'middle' }, Number(p.value).toPrecision(3)));
    });
    svg.appendChild(el('text', { x: m.l + iw / 2, y: H - 6, class: 'axistitle', 'text-anchor': 'middle' }, opts.xtitle));
    var midy = m.t + ih / 2;
    svg.appendChild(el('text', { x: 13, y: midy, class: 'axistitle', 'text-anchor': 'middle', transform: 'rotate(-90 13 ' + midy + ')' }, opts.ytitle));
    container.appendChild(svg);
  }

  function barChart(container, series, opts) {
    container.innerHTML = '';
    if (!series || series.length === 0) { emptyNote(container, opts.emptyMsg); return; }
    var W = 660, H = 304, m = { t: 36, r: 20, b: 44, l: 64 };
    var iw = W - m.l - m.r, ih = H - m.t - m.b;
    var maxv = Math.max.apply(null, series.map(function (p) { return p.value; }));
    var ymax = niceMax(maxv), n = series.length;
    var band = iw / n, bw = Math.min(46, band * 0.6);
    var yOf = function (v) { return m.t + ih - v / ymax * ih; };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'chartsvg' });
    var steps = 5;
    for (var s = 0; s <= steps; s++) {
      var val = ymax * s / steps, y = yOf(val);
      svg.appendChild(el('line', { x1: m.l, y1: y, x2: W - m.r, y2: y, class: 'grid' }));
      svg.appendChild(el('text', { x: m.l - 8, y: y + 4, class: 'axislabel', 'text-anchor': 'end' }, '$' + Math.round(val).toLocaleString()));
    }
    series.forEach(function (p, i) {
      var cx = m.l + band * i + band / 2;
      var y = yOf(p.value), h = m.t + ih - y;
      svg.appendChild(el('rect', { x: cx - bw / 2, y: y, width: bw, height: h, class: 'bar' }));
      svg.appendChild(el('text', { x: cx, y: y - 6, class: 'ptlabel', 'text-anchor': 'middle' }, '$' + Math.round(p.value).toLocaleString()));
      // Attendance context above the dollar figure: absences in sessions that ran,
      // plus any whole-session exclusion that week.
      var absParts = [];
      if (p.absent != null) absParts.push(p.absent + ' absent');
      if (p.excluded) absParts.push(p.excluded + ' excluded');
      if (absParts.length) {
        svg.appendChild(el('text', { x: cx, y: y - 19, class: 'barabs', 'text-anchor': 'middle' }, absParts.join(' \\u00B7 ')));
      }
      svg.appendChild(el('text', { x: cx, y: H - m.b + 18, class: 'axislabel', 'text-anchor': 'middle' }, fmtWeek(p.week)));
    });
    svg.appendChild(el('text', { x: m.l + iw / 2, y: H - 6, class: 'axistitle', 'text-anchor': 'middle' }, opts.xtitle));
    var midy = m.t + ih / 2;
    svg.appendChild(el('text', { x: 13, y: midy, class: 'axistitle', 'text-anchor': 'middle', transform: 'rotate(-90 13 ' + midy + ')' }, opts.ytitle));
    container.appendChild(svg);
  }

  var sel = document.getElementById('schoolSelect');
  if (!sel) return;
  CHART_DATA.schools.forEach(function (s) {
    var o = document.createElement('option');
    o.value = s.id; o.textContent = s.name;
    sel.appendChild(o);
  });

  function renderFor(schoolId) {
    var school = CHART_DATA.schools.filter(function (s) { return String(s.id) === String(schoolId); })[0];
    var cat = school ? CHART_DATA.caterers[school.caterer_id] : null;
    document.getElementById('catererLabel').textContent =
      cat ? ('Current caterer: ' + cat.name) : 'No caterer assigned';
    var floor = CHART_DATA.quality_floor;

    // Satisfaction is now this SCHOOL's own ratings, not the caterer average.
    var satSeries = school ? school.satisfaction : [];
    var sat = satSeries.map(function (p) { return { week: p.week, value: p.mean }; });
    lineChart(document.getElementById('satChart'), sat, {
      ymax: 5, floor: floor, floorLabel: floor.toFixed(1) + ' quality floor',
      ytitle: 'Mean score (0-5)', xtitle: 'Week beginning',
      emptyMsg: 'Limited data \\u2014 no feedback recorded for this school yet.'
    });

    // n-aware caution for thin per-school data (e.g. one rating per week).
    var maxN = satSeries.reduce(function (m, p) { return Math.max(m, p.n); }, 0);
    var note = document.getElementById('satCountNote');
    if (satSeries.length === 0) {
      note.textContent = '';
    } else if (maxN <= 1) {
      note.textContent = 'Based on a single rating per week \\u2014 read short-term '
        + 'movement with care.';
    } else {
      note.textContent = 'Up to ' + maxN + ' ratings per week for this school.';
    }

    var costSeries = school ? (school.cost || []) : [];
    var cost = costSeries.map(function (p) {
      return { week: p.week, value: p.dollars, absent: p.absent, excluded: p.excluded };
    });
    barChart(document.getElementById('costChart'), cost, {
      ytitle: 'Amount payable (A$)', xtitle: 'Week beginning',
      emptyMsg: 'Limited data \\u2014 no orders recorded for this school yet.'
    });

    // Awaiting-feedback marker: a week is ordered (so it has a cost bar) before
    // its sessions run and get rated, so the satisfaction line intentionally
    // stops one week short. Make that explicit, not a truncation bug.
    var pend = document.getElementById('satPendingNote');
    var lastSat = satSeries.length ? satSeries[satSeries.length - 1].week : null;
    var lastCost = costSeries.length ? costSeries[costSeries.length - 1].week : null;
    if (lastSat && lastCost && lastCost > lastSat) {
      pend.innerHTML = '\\u25CB Week of ' + fmtWeek(lastCost) + ' is ordered (see the '
        + 'cost chart) but its sessions have not run yet \\u2014 it will get a '
        + 'satisfaction score once feedback is collected.';
      pend.style.display = '';
    } else {
      pend.style.display = 'none';
    }
  }

  sel.value = CHART_DATA.default_school_id;
  renderFor(sel.value);
  sel.addEventListener('change', function () { renderFor(this.value); });
})();
"""


def _glance_band(mean: float, floor: float) -> str:
    """Traffic-light band for a school's score against the quality floor.
    Below floor -> red; at/near floor (within 0.5) -> amber; healthy -> green.
    A school sitting exactly on the floor reads amber (a warning), not red."""
    if mean < floor:
        return "red"
    if mean < floor + 0.5:
        return "amber"
    return "green"


def render_glance(chart_data: dict) -> str:
    """All-schools at-a-glance: each school's most-recent rated week as a
    colour-coded horizontal bar against the 3.0 floor. Worst first, so the
    operator sees who is unhappy at the top. Read-only (reuses CHART_DATA)."""
    floor = chart_data["quality_floor"]
    floor_pct = floor / 5.0 * 100.0

    rows = []
    for s in chart_data["schools"]:
        series = s.get("satisfaction") or []
        latest = series[-1] if series else None
        if latest is None:
            rows.append({"name": s["name"], "mean": None, "week": None,
                         "n": None, "band": "none"})
        else:
            rows.append({
                "name": s["name"], "mean": latest["mean"], "week": latest["week"],
                "n": latest["n"], "band": _glance_band(latest["mean"], floor),
            })

    # Worst (lowest mean) first; no-data rows sink to the bottom.
    rows.sort(key=lambda r: (r["mean"] is None, r["mean"] if r["mean"] is not None else 0))

    p = ['  <div class="glance">']
    p.append('    <h3 class="panel__h">All schools, most recent week '
             '<span class="chart-scope">at a glance</span></h3>')
    p.append('    <div class="glance__rows">')
    for r in rows:
        band = r["band"]
        if r["mean"] is None:
            title = f'{r["name"]} — no feedback recorded yet'
            p.append('      <div class="glance__row" title="%s">' % esc(title))
            p.append(f'        <span class="glance__name">{esc(r["name"])}</span>')
            p.append('        <div class="glance__track">'
                     f'<div class="glance__floor" style="left:{floor_pct:.1f}%"></div>'
                     '</div>')
            p.append('        <span class="glance__val glance__val--none">—</span>')
            p.append('      </div>')
            continue
        width = max(0.0, min(100.0, r["mean"] / 5.0 * 100.0))
        wk = date.fromisoformat(r["week"])
        title = (f'{r["name"]} — {r["mean"]:.3g} mean from {r["n"]} rating(s), '
                 f'week of {wk.strftime("%-d %b %Y")}')
        p.append('      <div class="glance__row" title="%s">' % esc(title))
        p.append(f'        <span class="glance__name">{esc(r["name"])}</span>')
        p.append('        <div class="glance__track">')
        p.append(f'          <div class="glance__floor" style="left:{floor_pct:.1f}%"></div>')
        p.append(f'          <div class="glance__fill glance__fill--{band}" '
                 f'style="width:{width:.1f}%"></div>')
        p.append('        </div>')
        p.append(f'        <span class="glance__val glance__val--{band}">{r["mean"]:.3g}</span>')
        p.append('      </div>')
    p.append('    </div>')
    p.append(f'    <div class="chart-note">Each school&rsquo;s mean score for its most '
             f'recent rated week, against the {floor:.1f} quality floor (dashed). '
             f'<span style="color:var(--urgent);font-weight:600">Red</span> = below floor, '
             f'<span style="color:var(--notable);font-weight:600">amber</span> = at or near '
             f'the floor, <span style="color:var(--informational);font-weight:600">green</span> '
             f'= healthy. Worst first.</div>')
    p.append('  </div>')
    return "\n".join(p)


def render_charts_section(chart_data: dict) -> str:
    data_json = json.dumps(chart_data, default=str)
    p = ['<section class="charts">']
    p.append('  <div class="panel__title">Quality &amp; cost trends</div>')
    p.append(render_glance(chart_data))
    p.append('  <div class="charts__controls">')
    p.append('    <label for="schoolSelect">School:</label>')
    p.append('    <select id="schoolSelect"></select>')
    p.append('    <span id="catererLabel" class="charts__caterer"></span>')
    p.append('  </div>')
    p.append('  <div class="chart-card">')
    p.append('    <h3 class="panel__h">Satisfaction over time '
             '<span class="chart-scope">this school</span></h3>')
    p.append('    <div id="satChart" class="chart-host"></div>')
    p.append('    <div class="chart-note">Student rating average (n students per '
             'week); session-manager rating shown where students didn&rsquo;t rate. '
             'The dashed line is the 3.0 quality floor. Schools that share a caterer '
             'can diverge &mdash; this shows each school&rsquo;s actual experience, '
             'not the caterer average.</div>')
    p.append('    <div id="satCountNote" class="chart-note"></div>')
    p.append('    <div id="satPendingNote" class="chart-note chart-pending" style="display:none"></div>')
    p.append('    <div class="chart-note chart-note--aside">The decline &rarr; '
             'warning decision is made at <strong>caterer</strong> level (the '
             'caterer&rsquo;s combined rolling mean), not per school &mdash; this '
             'chart surfaces per-school experience, it does not itself trigger the '
             'warning.</div>')
    p.append('  </div>')
    p.append('  <div class="chart-card">')
    p.append('    <h3 class="panel__h">Cost over time</h3>')
    p.append('    <div id="costChart" class="chart-host"></div>')
    p.append('    <div class="chart-note">Weekly spend on this school &mdash; meals '
             '(count &times; the caterer&rsquo;s per-item price) plus delivery, '
             'GST-inclusive. Only full, summarised operational weeks are shown.</div>')
    p.append('  </div>')
    p.append('  <script>')
    p.append('  const CHART_DATA = ' + data_json + ';')
    p.append(_CHART_JS)
    p.append('  </script>')
    p.append('</section>')
    return "\n".join(p)


def render_page(runs: list[dict], emails: dict[int, dict],
                upcoming: list[dict], disruptions: list[dict],
                chart_data: dict) -> str:
    by_id = {r["id"]: r for r in runs}

    # Demo runs in the resolved order (explicit DEMO_RUN_IDS, or all runs live).
    demo_id_list = resolve_demo_run_ids(runs)
    demo_runs = [by_id[rid] for rid in demo_id_list if rid in by_id]
    demo_ids = set(demo_id_list)
    # Full history = everything not in the demo view, reverse-chronological
    # (newest first) by started_at; runs with no start time sort to the end.
    _epoch = datetime.min.replace(tzinfo=timezone.utc)
    history_runs = [r for r in runs if r["id"] not in demo_ids]
    history_runs.sort(
        key=lambda r: r["started_at"] if r["started_at"] is not None else _epoch,
        reverse=True,
    )

    generated = datetime.now(tz=_TZ_BNE).strftime("%Y-%m-%d %H:%M") + " AEST"

    out = ['<!DOCTYPE html>', '<html lang="en">', '<head>',
           '<meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           '<title>Padea Operations Agent — Decision Log</title>',
           f'<style>{_CSS}</style>',
           '</head>', '<body>', '<div class="wrap">']

    logo = load_logo_data_uri()
    out.append('<header class="masthead">')
    if logo:
        out.append(f'  <img class="masthead__logo" src="{logo}" alt="Padea">')
    out.append('  <div class="masthead__titles">')
    out.append('    <h1 class="page-title">Operations Agent</h1>')
    out.append('    <p class="page-sub">Decision log &mdash; every run the agent took, '
               'what it decided, and why. '
               f'Generated {esc(generated)}.</p>')
    out.append('  </div>')
    out.append('</header>')

    out.append(render_panel(runs, emails, upcoming, disruptions))
    out.append(render_charts_section(chart_data))

    out.append('<div class="section-label">Run timeline</div>')
    for run in demo_runs:
        out.append(render_run_section(run, emails))

    if history_runs:
        out.append(
            f'<details class="history">'
            f'<summary>Full run history ({len(history_runs)} more runs, newest first)</summary>'
        )
        for run in history_runs:
            out.append(render_run_section(run, emails))
        out.append('</details>')

    out.append('</div>')
    out.append(f'<script>{_APPROVE_JS}</script>')
    out.append('</body></html>')
    return "\n".join(out)


def main() -> None:
    runs = fetch_runs()
    emails = fetch_emails()
    upcoming = fetch_upcoming_sessions()
    disruptions = fetch_recent_disruptions()
    chart_data = fetch_chart_data()
    _OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUT_PATH.write_text(
        render_page(runs, emails, upcoming, disruptions, chart_data),
        encoding="utf-8",
    )

    print(f"Wrote {_OUT_PATH}")
    print(f"  total runs: {len(runs)}")
    if DEMO_RUN_IDS:
        demo_present = [rid for rid in DEMO_RUN_IDS if any(r["id"] == rid for r in runs)]
        print(f"  mode: CURATED — demo runs present: {demo_present}")
        missing = [rid for rid in DEMO_RUN_IDS if rid not in demo_present]
        if missing:
            print(f"  WARNING — demo runs missing from DB: {missing}")
    else:
        print(f"  mode: LIVE — showing all {len(runs)} run(s), oldest first")


if __name__ == "__main__":
    main()
