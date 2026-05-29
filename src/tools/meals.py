"""
src/tools/meals.py
Meal selection tools for the Padea operations agent.
"""
from __future__ import annotations

from datetime import date

from src.ingest.db import get_conn


def item_is_safe_for_enrolment(menu_item_id: int, enrolment_id: int) -> bool:
    """
    Return True if the menu item satisfies all of the student's dietary tags.

    Safety rule (V4-OPT-06): item.tags ⊇ student.tags.
    Students with no dietary tags: every item is safe (vacuously true).
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT NOT EXISTS (
                    SELECT 1
                    FROM enrolment_dietary_tags edt
                    WHERE edt.enrolment_id = %s
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


def auto_pick_dietary_meal(enrolment_id: int, caterer_id: int) -> dict | None:
    """
    Return any active menu item for this caterer that passes all of the
    student's dietary restrictions.

    Returns None if no safe item exists (caller should raise urgent escalation).
    Result dict: {menu_item_id, name, price_cents}
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mi.id, mi.name, mi.price_cents
                FROM menu_items mi
                WHERE mi.caterer_id = %s
                  AND mi.active = true
                  AND NOT EXISTS (
                      SELECT 1
                      FROM enrolment_dietary_tags edt
                      WHERE edt.enrolment_id = %s
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


def get_meal_request(
    enrolment_id: int,
    session_slot_id: int,
    session_date: date,
) -> dict | None:
    """
    Return the unconsumed meal_request for this (enrolment, session, date) if one exists.

    Result dict: {request_id, menu_item_id, name, price_cents}
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mr.id, mr.menu_item_id, mi.name, mi.price_cents
                FROM meal_requests mr
                JOIN menu_items mi ON mi.id = mr.menu_item_id
                WHERE mr.enrolment_id = %s
                  AND mr.session_slot_id = %s
                  AND mr.session_date = %s
                  AND mr.consumed_at IS NULL
                LIMIT 1
                """,
                (enrolment_id, session_slot_id, session_date),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "request_id":   row[0],
                "menu_item_id": row[1],
                "name":         row[2],
                "price_cents":  row[3],
            }


def consume_meal_request(request_id: int) -> None:
    """Mark a meal_request as consumed (used in order composition)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE meal_requests SET consumed_at = now() WHERE id = %s",
                (request_id,),
            )
        conn.commit()


def get_next_rotation_meal(enrolment_id: int, caterer_id: int) -> dict | None:
    """
    Return the next meal in the student's rotation for this caterer.

    Algorithm:
    1. Fetch the current approved set (term_meal_preferences, superseded_at IS NULL).
    2. Filter to active items in canonical_menu_order for this caterer.
    3. Return the item with the oldest appearance in order_lines (least recently served).
       Items never served rank ahead of items that were served.

    Returns None if no approved set exists (no preferences seeded yet).
    Result dict: {menu_item_id, name, price_cents}
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Fetch current approved set for this (enrolment, caterer)
            cur.execute(
                """
                SELECT tmpi.menu_item_id
                FROM term_meal_preferences tmp
                JOIN term_meal_preference_items tmpi ON tmpi.preference_id = tmp.id
                WHERE tmp.enrolment_id = %s
                  AND tmp.caterer_id = %s
                  AND tmp.superseded_at IS NULL
                """,
                (enrolment_id, caterer_id),
            )
            approved_ids = [r[0] for r in cur.fetchall()]
            if not approved_ids:
                return None

            # Canonical menu order for this caterer
            cur.execute(
                "SELECT canonical_menu_order FROM caterers WHERE id = %s",
                (caterer_id,),
            )
            row = cur.fetchone()
            canonical: list[int] = row[0] if (row and row[0]) else []

            # Build ordered list: canonical order filtered to approved set
            approved_set = set(approved_ids)
            ordered = [mid for mid in canonical if mid in approved_set]
            # Append any approved items not in canonical (shouldn't happen in practice)
            for mid in approved_ids:
                if mid not in ordered:
                    ordered.append(mid)

            if not ordered:
                return None

            # Find the item served least recently — use session_date from orders
            # (order_lines has no created_at; session_date is the correct proxy).
            cur.execute(
                """
                SELECT ol.menu_item_id, MAX(o.session_date) AS last_served
                FROM order_lines ol
                JOIN orders o ON o.id = ol.order_id
                WHERE ol.enrolment_id = %s
                  AND ol.menu_item_id = ANY(%s::bigint[])
                GROUP BY ol.menu_item_id
                """,
                (enrolment_id, ordered),
            )
            served = {r[0]: r[1] for r in cur.fetchall()}

            # Sort: never-served first (None < any timestamp), then oldest-served
            def sort_key(mid: int):
                ts = served.get(mid)
                return (0 if ts is None else 1, ts)

            ordered.sort(key=sort_key)
            picked_id = ordered[0]

            cur.execute(
                "SELECT id, name, price_cents FROM menu_items WHERE id = %s",
                (picked_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {"menu_item_id": row[0], "name": row[1], "price_cents": row[2]}
