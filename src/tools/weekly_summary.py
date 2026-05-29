"""
src/tools/weekly_summary.py
Monday consolidated-summary tools for the Padea operations agent.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from config.settings import settings
from src.ingest.db import get_conn
from src.tools.quality import compute_rolling_mean

TZ = ZoneInfo("Australia/Brisbane")

_MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}
_DAY_ABBR = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}


def _as_date(v: date | str) -> date:
    # The summary dict round-trips through the model as a tool arg, so its date
    # fields arrive back as ISO strings (the loop serialises date -> str). Accept
    # either form so compose_weekly_summary_email is robust at that boundary.
    return date.fromisoformat(v) if isinstance(v, str) else v


def _fmt_date(d: date | str) -> str:
    d = _as_date(d)
    return f"{_DAY_ABBR[d.weekday()]} {d.day} {_MONTH_ABBR[d.month]}"


def _fmt_money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def generate_weekly_summary(
    caterer_id: int,
    week_of: date,
    as_of: datetime | None = None,
) -> dict:
    """
    Generate the Monday consolidated summary for one caterer for the ISO week
    containing week_of (normalised to Monday–Sunday).

    already_completed: if outbound_emails already has a weekly_consolidated_summary
    row for this caterer in this ISO week, returns {"already_completed": True} with
    no DB mutations.

    GST normalisation (one round at the boundary, on the combined ex-GST subtotal):
      total_delivery_cents = delivery_fee_cents × sessions_count
      ex_subtotal          = total_cost_cents + total_delivery_cents
      price_includes_gst=False → grand_total_cents = round(ex_subtotal × (1 + rate/100))
      price_includes_gst=True  → grand_total_cents = ex_subtotal
    gst_amount_cents = grand_total_cents − ex_subtotal
    The caterer invoices the whole week together, so delivery is part of the total.

    MOQ: if the week's variety_count falls in {4, 5, 6} and total_items < moq_applicable,
    moq_variance_cents is computed (cheapest ordered item × shortfall, GST-normalised) and
    written to the LAST order by session_date (absolute SET — idempotent re-run safe).
    The shortfall top-up is priced at the cheapest item because it is a minimum-volume
    floor, so the operator-favourable price is correct. The shortfall is computed on the
    MEAL subtotal only — delivery is never part of the MOQ math. Skipped when
    already_completed=True.

    Quality: compute_rolling_mean pinned to as_of (default: datetime.now Brisbane).
    sustained_decline = mean_4w < quality_floor AND (mean_12w − mean_4w) >= decline_threshold.

    Returns dict with keys:
        caterer_id, caterer_name, caterer_email,
        week_start (date), week_end (date),
        total_items, total_cost_cents, grand_total_cents, gst_amount_cents,
        delivery_fee_cents (per delivery), total_delivery_cents (× sessions, ex-GST),
        sessions_count,
        moq_applicable (int | None), moq_floor_applied (bool), moq_variance_cents,
        mean_4w (float | None), mean_12w (float | None), sustained_decline (bool),
        session_breakdown (list[dict] sorted by session_date ASC — keys: order_id,
            session_slot_id, session_date, school_id, school_name, items, cost_cents),
        already_completed (bool)
    """
    if as_of is None:
        as_of = datetime.now(tz=TZ)

    week_start = week_of - timedelta(days=week_of.weekday())
    week_end = week_start + timedelta(days=6)
    week_start_dt = datetime.combine(week_start, time.min, tzinfo=TZ)
    week_end_dt = datetime.combine(week_end + timedelta(days=1), time.min, tzinfo=TZ)

    with get_conn() as conn:
        with conn.cursor() as cur:
            # already_completed guard
            cur.execute(
                """
                SELECT id FROM outbound_emails
                WHERE email_type = 'weekly_consolidated_summary'
                  AND related_caterer_id = %s
                  AND composed_at >= %s
                  AND composed_at < %s
                LIMIT 1
                """,
                (caterer_id, week_start_dt, week_end_dt),
            )
            if cur.fetchone():
                return {"already_completed": True}

            cur.execute(
                """
                SELECT name, contact_email, price_includes_gst, gst_rate_percent,
                       delivery_fee_cents, moq_4_items, moq_5_items, moq_6_items
                FROM caterers WHERE id = %s
                """,
                (caterer_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"caterer_id {caterer_id} not found")
            (caterer_name, caterer_email, price_includes_gst, gst_rate_percent,
             delivery_fee_cents, moq_4, moq_5, moq_6) = row

            cur.execute(
                """
                SELECT o.id, o.session_slot_id, o.session_date,
                       o.total_items, o.total_cost_cents,
                       ss.school_id, sc.name
                FROM orders o
                JOIN session_slots ss ON ss.id = o.session_slot_id
                JOIN schools sc ON sc.id = ss.school_id
                WHERE o.caterer_id = %s
                  AND o.session_date >= %s
                  AND o.session_date <= %s
                ORDER BY o.session_date ASC
                """,
                (caterer_id, week_start, week_end),
            )
            order_rows = cur.fetchall()

            cur.execute(
                """
                SELECT count(DISTINCT ol.menu_item_id)
                FROM order_lines ol
                JOIN orders o ON o.id = ol.order_id
                WHERE o.caterer_id = %s
                  AND o.session_date >= %s
                  AND o.session_date <= %s
                """,
                (caterer_id, week_start, week_end),
            )
            variety_count: int = cur.fetchone()[0]

    session_breakdown = [
        {
            "order_id":        r[0],
            "session_slot_id": r[1],
            "session_date":    r[2],
            "items":           r[3],
            "cost_cents":      r[4],
            "school_id":       r[5],
            "school_name":     r[6],
        }
        for r in order_rows
    ]

    total_items = sum(s["items"] for s in session_breakdown)
    total_cost_cents = sum(s["cost_cents"] for s in session_breakdown)
    sessions_count = len(session_breakdown)

    # Delivery is invoiced with the week — fold it into the total before GST.
    total_delivery_cents = delivery_fee_cents * sessions_count
    ex_subtotal = total_cost_cents + total_delivery_cents

    if price_includes_gst:
        grand_total_cents = ex_subtotal
    else:
        grand_total_cents = round(ex_subtotal * (1 + gst_rate_percent / 100))
    gst_amount_cents = grand_total_cents - ex_subtotal

    # MOQ tier selection and shortfall
    moq_map: dict[int, int | None] = {4: moq_4, 5: moq_5, 6: moq_6}
    moq_applicable: int | None = moq_map.get(variety_count)
    shortfall = max(0, moq_applicable - total_items) if moq_applicable is not None else 0
    moq_floor_applied = shortfall > 0
    moq_variance_cents = 0

    if shortfall > 0 and order_rows:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT min(mi.price_cents)::int
                    FROM order_lines ol
                    JOIN orders o ON o.id = ol.order_id
                    JOIN menu_items mi ON mi.id = ol.menu_item_id
                    WHERE o.caterer_id = %s
                      AND o.session_date >= %s
                      AND o.session_date <= %s
                    """,
                    (caterer_id, week_start, week_end),
                )
                cheapest_price_cents: int = cur.fetchone()[0] or 0

        if not price_includes_gst:
            cheapest_price_cents = round(cheapest_price_cents * (1 + gst_rate_percent / 100))
        moq_variance_cents = shortfall * cheapest_price_cents

        # Absolute SET to the last order — safe to re-run (never increments)
        last_order_id: int = order_rows[-1][0]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE orders
                    SET moq_floor_applied = true,
                        moq_variance_cents = %s
                    WHERE id = %s
                    """,
                    (moq_variance_cents, last_order_id),
                )
            conn.commit()

    mean_4w = compute_rolling_mean(caterer_id, 4, as_of)
    mean_12w = compute_rolling_mean(caterer_id, 12, as_of)
    sustained_decline = (
        mean_4w is not None
        and mean_12w is not None
        and mean_4w < settings.quality_floor
        and (mean_12w - mean_4w) >= settings.quality_decline_threshold
    )

    return {
        "caterer_id":         caterer_id,
        "caterer_name":       caterer_name,
        "caterer_email":      caterer_email,
        "week_start":         week_start,
        "week_end":           week_end,
        "total_items":        total_items,
        "total_cost_cents":   total_cost_cents,
        "grand_total_cents":  grand_total_cents,
        "gst_amount_cents":   gst_amount_cents,
        "delivery_fee_cents": delivery_fee_cents,
        "total_delivery_cents": total_delivery_cents,
        "sessions_count":     sessions_count,
        "moq_applicable":     moq_applicable,
        "moq_floor_applied":  moq_floor_applied,
        "moq_variance_cents": moq_variance_cents,
        "mean_4w":            mean_4w,
        "mean_12w":           mean_12w,
        "sustained_decline":  sustained_decline,
        "session_breakdown":  session_breakdown,
        "already_completed":  False,
    }


def compose_weekly_summary_email(caterer_id: int, summary: dict) -> str:
    """
    Render the Monday consolidated summary email body.

    summary: the dict returned by generate_weekly_summary (must not be the
    early-return {"already_completed": True} form).

    Body sections: week header, per-session breakdown, cost block (meals +
    delivery + GST + TOTAL DUE), MOQ floor note if applied. This is a PAYMENT
    DOCUMENT ONLY — no quality ratings, no decline alert, no "warning queued"
    text ever reaches the caterer (that is operator-facing decision-log content).

    Demo mode: prepends [DEMO — Intended for: {caterer_email}] when
    settings.email_mode == 'demo'.

    Read-only — no DB writes.
    """
    week_start: date      = _as_date(summary["week_start"])
    week_end: date        = _as_date(summary["week_end"])
    caterer_name: str     = summary["caterer_name"]
    caterer_email: str    = summary["caterer_email"]
    total_items: int      = summary["total_items"]
    total_cost_cents: int = summary["total_cost_cents"]
    grand_total_cents: int = summary["grand_total_cents"]
    gst_amount_cents: int = summary["gst_amount_cents"]
    delivery_fee_cents: int = summary["delivery_fee_cents"]
    sessions_count: int   = summary["sessions_count"]
    moq_floor_applied: bool  = summary["moq_floor_applied"]
    moq_variance_cents: int  = summary["moq_variance_cents"]
    moq_applicable: int | None = summary["moq_applicable"]
    session_breakdown: list[dict] = summary["session_breakdown"]

    week_range = (
        f"{_fmt_date(week_start)} to {_fmt_date(week_end)} {week_end.year}"
    )

    session_lines = "\n".join(
        f"  {_fmt_date(s['session_date'])} — {s['school_name']} — "
        f"{s['items']} meals — {_fmt_money(s['cost_cents'])}"
        for s in session_breakdown
    ) or "  (no sessions this week)"

    # Cost block — delivery is invoiced with the week, so it is part of the total
    total_delivery = delivery_fee_cents * sessions_count
    session_word = "session" if sessions_count == 1 else "sessions"
    delivery_detail = (
        f"({_fmt_money(delivery_fee_cents)} × {sessions_count} {session_word})"
    )
    ex_subtotal = total_cost_cents + total_delivery
    if gst_amount_cents > 0:
        cost_block = (
            f"Meals subtotal (ex-GST): {_fmt_money(total_cost_cents)}\n"
            f"Delivery (ex-GST):       {_fmt_money(total_delivery)} {delivery_detail}\n"
            f"Subtotal (ex-GST):       {_fmt_money(ex_subtotal)}\n"
            f"GST (10%):               {_fmt_money(gst_amount_cents)}\n"
            f"TOTAL DUE:               {_fmt_money(grand_total_cents)}"
        )
    else:
        cost_block = (
            f"Meals subtotal: {_fmt_money(total_cost_cents)}\n"
            f"Delivery:       {_fmt_money(total_delivery)} {delivery_detail}\n"
            f"TOTAL DUE:      {_fmt_money(grand_total_cents)} (GST included)"
        )

    # MOQ floor note
    moq_note = ""
    if moq_floor_applied and moq_applicable is not None:
        moq_note = (
            f"\nMOQ floor applied: weekly total fell below minimum of {moq_applicable} items. "
            f"Variance of {_fmt_money(moq_variance_cents)} added to final session invoice.\n"
        )

    # Payment document ONLY. Quality ratings, sustained-decline detection, and the
    # "warning queued" fact are operator-facing — they live in the agent_steps
    # decision log, never in the caterer's email. The caterer hears about quality
    # solely via the warning email, and only once the operator approves and sends it.
    body = (
        f"WEEKLY SUMMARY: {caterer_name} — {week_range}\n"
        f"\n"
        f"Sessions this week ({total_items} meals total):\n"
        f"{session_lines}\n"
        f"\n"
        f"{cost_block}\n"
        f"{moq_note}"
    )

    if settings.email_mode == "demo":
        body = f"[DEMO — Intended for: {caterer_email}]\n\n{body}"

    return body
