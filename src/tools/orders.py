"""
src/tools/orders.py
Order composition and persistence tools for the Padea operations agent.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from config.settings import settings
from src.ingest.db import get_conn
from src.tools.enrolments import get_enrolments_for_session
from src.tools.meals import (
    auto_pick_dietary_meal,
    consume_meal_request,
    get_meal_request,
    get_next_rotation_meal,
    item_is_safe_for_enrolment,
)


def _auto_pick_vo_meal(enrolment_id: int, caterer_id: int) -> dict | None:
    """
    VO safety fallback: find an active VO item for this caterer whose tags cover
    (student_tags − {'vegetarian'}). Called only when auto_pick_dietary_meal returns
    None. Non-restricted students never reach this.

    Returns {menu_item_id, name, price_cents} or None.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mi.id, mi.name, mi.price_cents
                FROM menu_items mi
                WHERE mi.caterer_id = %s
                  AND mi.active = true
                  AND mi.has_vegetarian_option = true
                  AND NOT EXISTS (
                      SELECT 1
                      FROM enrolment_dietary_tags edt
                      JOIN dietary_tags dt ON dt.id = edt.dietary_tag_id
                      WHERE edt.enrolment_id = %s
                        AND dt.name != 'vegetarian'
                        AND edt.dietary_tag_id NOT IN (
                            SELECT midt.dietary_tag_id
                            FROM menu_item_dietary_tags midt
                            WHERE midt.menu_item_id = mi.id
                        )
                  )
                ORDER BY mi.id
                LIMIT 1
                """,
                (caterer_id, enrolment_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {"menu_item_id": row[0], "name": row[1], "price_cents": row[2]}


def _vo_safe_for_enrolment(menu_item_id: int, enrolment_id: int) -> bool:
    """
    VO safety check: item_tags ⊇ (student_tags − {'vegetarian'}).
    Defense-in-depth mirror of the _auto_pick_vo_meal selection predicate.
    Any uncovered tag other than vegetarian returns False.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT NOT EXISTS (
                    SELECT 1
                    FROM enrolment_dietary_tags edt
                    JOIN dietary_tags dt ON dt.id = edt.dietary_tag_id
                    WHERE edt.enrolment_id = %s
                      AND dt.name != 'vegetarian'
                      AND edt.dietary_tag_id NOT IN (
                          SELECT midt.dietary_tag_id
                          FROM menu_item_dietary_tags midt
                          WHERE midt.menu_item_id = %s
                      )
                )
                """,
                (enrolment_id, menu_item_id),
            )
            return bool(cur.fetchone()[0])


def compose_session_order(session_slot_id: int, session_date: date) -> dict:
    """
    Full order composition pipeline for one (session_slot, date).

    Steps:
      2. Active cohort   — get_enrolments_for_session (applies absences +
                           whole-school/year-level exclusions + dietary override)
      3. Meal selection  — request → rotation → dietary auto-pick
      4. MOQ check       — not run here; caller handles across a full week
      5. Persist         — create_order

    Zero operational margin: no buffer meals. Walk-backs are an accepted gap.

    Returns dict with:
      order_id, caterer_id, total_students, total_cost_cents, order_lines,
      safety_records (one per student: enrolment_id, student_name, menu_item_id,
        meal_name, source, dietary_tags, safe, other_allergy_notes),
      escalations (list of urgent escalation strings — only for no-safe-meal failures)
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ss.school_id, sc.current_caterer_id, c.gst_rate_percent
                FROM session_slots ss
                JOIN schools sc ON sc.id = ss.school_id
                JOIN caterers c ON c.id = sc.current_caterer_id
                WHERE ss.id = %s
                """,
                (session_slot_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"session_slot_id {session_slot_id} not found")
            _school_id, caterer_id, gst_rate = row

    cohort = get_enrolments_for_session(session_slot_id, session_date)

    order_lines: list[dict] = []
    safety_records: list[dict] = []
    escalations: list[str] = []

    for student in cohort:
        enrolment_id = student["enrolment_id"]
        meal = None
        source = None
        safe = None
        variant = None

        request = get_meal_request(enrolment_id, session_slot_id, session_date)
        if request:
            meal = request
            source = "request"
            consume_meal_request(request["request_id"])
            # Tutor-filed requests name any item on the menu; machine double-check
            # required because the tutor app cannot enforce dietary safety at entry time.
            safe = item_is_safe_for_enrolment(meal["menu_item_id"], enrolment_id)

        if meal is None:
            rotation = get_next_rotation_meal(enrolment_id, caterer_id)
            if rotation:
                rotation_safe = item_is_safe_for_enrolment(rotation["menu_item_id"], enrolment_id)
                if rotation_safe:
                    meal = rotation
                    source = "rotation"
                    safe = rotation_safe  # True; explicit rather than hardcoded — defense in depth

        if meal is None:
            meal = auto_pick_dietary_meal(enrolment_id, caterer_id)
            if meal:
                source = "dietary_auto_pick"
                # auto_pick filters by safety in SQL; re-run check in Python for defense in depth.
                safe = item_is_safe_for_enrolment(meal["menu_item_id"], enrolment_id)
            else:
                # VO fallback: try items where has_vegetarian_option=true and
                # item_tags ⊇ (student_tags − {'vegetarian'}).
                vo_meal = _auto_pick_vo_meal(enrolment_id, caterer_id)
                if vo_meal:
                    meal = vo_meal
                    source = "dietary_auto_pick"
                    variant = "vegetarian_option"
                    safe = _vo_safe_for_enrolment(vo_meal["menu_item_id"], enrolment_id)
                else:
                    escalations.append(
                        f"URGENT: no safe meal for {student['student_name']} "
                        f"(enrolment {enrolment_id}) — dietary tags "
                        f"{student['dietary_tag_names']} — no matching item from caterer {caterer_id}"
                    )
                    continue

        order_lines.append({
            "enrolment_id": enrolment_id,
            "menu_item_id": meal["menu_item_id"],
            "source":       source,
            "variant":      variant,
            "price_cents":  meal["price_cents"],
            "student_name": student["student_name"],
        })
        safety_records.append({
            "enrolment_id":        enrolment_id,
            "student_name":        student["student_name"],
            "menu_item_id":        meal["menu_item_id"],
            "meal_name":           meal["name"],
            "source":              source,
            "variant":             variant,
            "dietary_tags":        student["dietary_tag_names"],
            "safe":                safe,
            "other_allergy_notes": student.get("other_allergy_notes"),
        })

    total_cost_cents = sum(line["price_cents"] for line in order_lines)

    order_id = create_order(
        session_slot_id=session_slot_id,
        session_date=session_date,
        caterer_id=caterer_id,
        order_lines=order_lines,
        total_cost_cents=total_cost_cents,
        gst_rate_percent=float(gst_rate),
    )

    return {
        "order_id":         order_id,
        "caterer_id":       caterer_id,
        "total_students":   len(order_lines),
        "total_cost_cents": total_cost_cents,
        "order_lines":      order_lines,
        "safety_records":   safety_records,
        "escalations":      escalations,
    }


def create_order(
    session_slot_id: int,
    session_date: date,
    caterer_id: int,
    order_lines: list[dict],
    total_cost_cents: int,
    gst_rate_percent: float = 10.0,
    moq_floor_applied: bool = False,
    moq_variance_cents: int = 0,
) -> int:
    """
    Persist a composed order to the database. Returns the new order_id.

    Raises ValueError if an order already exists for (session_slot_id, session_date).
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM orders WHERE session_slot_id = %s AND session_date = %s",
                (session_slot_id, session_date),
            )
            if cur.fetchone():
                raise ValueError(
                    f"Order already exists for session_slot {session_slot_id} on {session_date}"
                )

            cur.execute(
                """
                INSERT INTO orders (
                    session_slot_id, caterer_id, session_date,
                    total_items, total_cost_cents, gst_rate_percent,
                    moq_floor_applied, moq_variance_cents
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    session_slot_id, caterer_id, session_date,
                    len(order_lines), total_cost_cents, gst_rate_percent,
                    moq_floor_applied, moq_variance_cents,
                ),
            )
            order_id: int = cur.fetchone()[0]

            for line in order_lines:
                cur.execute(
                    """
                    INSERT INTO order_lines (order_id, enrolment_id, menu_item_id, source, variant)
                    VALUES (%s, %s, %s, %s::order_line_source, %s)
                    """,
                    (order_id, line["enrolment_id"], line["menu_item_id"], line["source"], line.get("variant")),
                )

        conn.commit()

    return order_id


_DAY_NAMES = {
    1: "Monday", 2: "Tuesday", 3: "Wednesday",
    4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday",
}


def _format_order_line(
    meal_name: str,
    student_name: str,
    allergy_notes: str | None,
    variant: str | None,
    student_tags: list | None,
    meal_tags: list | None,
) -> str:
    """
    Render one per-student line in the order email body.

    VO lines (variant='vegetarian_option'): annotate with ⚑ VEGETARIAN OPTION and
    suppress ⚠ UNSAFE MATCH only for the Vegetarian label gap — any other uncovered
    tag still fires. Non-VO lines use the standard full-coverage check.
    """
    student_set = set(student_tags or [])
    meal_set = set(meal_tags or [])

    if variant == "vegetarian_option":
        uncovered = (student_set - {"Vegetarian"}) - meal_set
    else:
        uncovered = student_set - meal_set

    line = f"  {meal_name} — {student_name}"
    if student_set:
        line += f"  [{', '.join(sorted(student_set))}]"
    if variant == "vegetarian_option":
        line += "  ⚑ VEGETARIAN OPTION"
    if uncovered:
        line += "  ⚠ UNSAFE MATCH"
    if allergy_notes:
        line += f"  ⚠ ALLERGY NOTE (unverified): {allergy_notes}"
    return line


def compose_order_email(order_id: int) -> str:
    """
    Render the per-session order email body.

    V4 ruling: no costs on the per-session order — costs (orders.total_cost_cents)
    live in the Monday consolidated summary. Body = delivery brief: session details,
    room, per-student meal list with dietary safety check, per-meal quantity summary.

    Safety: each line shows the student's dietary requirements. If the assigned
    meal's tags do not fully cover the student's tags (menu_item_dietary_tags ⊇
    enrolment_dietary_tags), the line is flagged ⚠ UNSAFE MATCH. Free-text
    other_allergy_notes cannot be auto-verified and are surfaced as
    ⚠ ALLERGY NOTE (unverified).

    Demo mode: prepend [DEMO — Intended for: {caterer_email}] when
    settings.email_mode == 'demo'.

    Read-only — no conn.commit().

    Tables read: orders, caterers, session_slots, schools, order_lines,
                 menu_items, enrolments, enrolment_dietary_tags,
                 menu_item_dietary_tags, dietary_tags.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT o.session_date, o.total_items,
                       c.name, c.contact_email,
                       ss.day_of_week, ss.dinner_time, ss.room,
                       sc.name, sc.building
                FROM orders o
                JOIN caterers c  ON c.id  = o.caterer_id
                JOIN session_slots ss ON ss.id = o.session_slot_id
                JOIN schools sc  ON sc.id = ss.school_id
                WHERE o.id = %s
                """,
                (order_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"order_id {order_id} not found")
            (session_date, total_items, caterer_name, caterer_email,
             day_of_week, dinner_time, room,
             school_name, building) = row

            # Subqueries avoid a Cartesian product when joining two tag sets.
            cur.execute(
                """
                SELECT mi.name, e.student_name, e.other_allergy_notes, ol.variant,
                       (SELECT array_agg(dt2.label ORDER BY dt2.label)
                        FROM enrolment_dietary_tags edt2
                        JOIN dietary_tags dt2 ON dt2.id = edt2.dietary_tag_id
                        WHERE edt2.enrolment_id = e.id
                       ) AS student_tag_labels,
                       (SELECT array_agg(dt3.label ORDER BY dt3.label)
                        FROM menu_item_dietary_tags mit2
                        JOIN dietary_tags dt3 ON dt3.id = mit2.dietary_tag_id
                        WHERE mit2.menu_item_id = mi.id
                       ) AS meal_tag_labels
                FROM order_lines ol
                JOIN menu_items mi ON mi.id = ol.menu_item_id
                JOIN enrolments e  ON e.id  = ol.enrolment_id
                WHERE ol.order_id = %s
                ORDER BY mi.name, e.student_name
                """,
                (order_id,),
            )
            lines = cur.fetchall()

    # Location: building and room are separate schema fields.
    # When they hold the same value (common in seed data), render once.
    if building and room and building != room:
        location = f"{school_name} — {building}, {room}"
    elif room:
        location = f"{school_name} — {room}"
    elif building:
        location = f"{school_name} — {building}"
    else:
        location = school_name

    meal_counts: dict[str, int] = {}
    for meal_name, _, _, _, _, _ in lines:
        meal_counts[meal_name] = meal_counts.get(meal_name, 0) + 1

    day_name = _DAY_NAMES.get(day_of_week, str(day_of_week))
    date_str = f"{session_date.day} {session_date.strftime('%B %Y')}"

    if dinner_time:
        deliver_by = (datetime.combine(date.min, dinner_time) - timedelta(minutes=10)).time()
        time_line = f"Deliver by: {deliver_by.strftime('%H:%M')} (dinner at {dinner_time.strftime('%H:%M')})"
    else:
        time_line = "Deliver by: —"

    lines_block = "\n".join(
        _format_order_line(meal, student, allergy, variant, student_tags, meal_tags)
        for meal, student, allergy, variant, student_tags, meal_tags in lines
    )
    summary_block = "\n".join(
        f"  {meal} × {count}" for meal, count in sorted(meal_counts.items())
    )

    body = (
        f"ORDER: {caterer_name} — {school_name}\n"
        f"Session: {day_name}, {date_str}\n"
        f"Delivery to: {location}\n"
        f"{time_line}\n"
        f"\n"
        f"Meal allocations ({total_items} students):\n"
        f"\n"
        f"{lines_block}\n"
        f"\n"
        f"Summary:\n"
        f"{summary_block}\n"
    )

    if settings.email_mode == "demo":
        body = f"[DEMO — Intended for: {caterer_email}]\n\n{body}"

    return body
