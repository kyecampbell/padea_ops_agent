#!/usr/bin/env python3
"""
seed_term_meal_preferences.py — DUMMY DATA
Generates plausible term meal preference sets for all 320 students.

Every student gets 3–5 approved menu items from their caterer, subject to
dietary safety (item.tags ⊇ student.tags).  After inserting preferences,
each caterer's canonical_menu_order is updated (most-popular item first).

FAKE DATA: There is no real parent-preference source.  These preferences
simulate a completed term-start parent enrolment email flow.
captured_by = 'parent', captured_at = 2026-04-25 (day 4 of Term 2).
"""
import json
import random
from datetime import datetime, timezone

from src.ingest.db import get_conn

SEED = 42
CAPTURED_AT = datetime(2026, 4, 25, 9, 0, 0, tzinfo=timezone.utc)


def run() -> None:
    rng = random.Random(SEED)

    with get_conn() as conn:
        with conn.cursor() as cur:
            # school → current_caterer_id
            cur.execute("SELECT id, current_caterer_id FROM schools")
            school_caterer: dict[int, int] = dict(cur.fetchall())

            # item_tags: menu_item_id → set of dietary_tag_ids
            cur.execute("SELECT menu_item_id, dietary_tag_id FROM menu_item_dietary_tags")
            item_tags: dict[int, set[int]] = {}
            for mid, tid in cur.fetchall():
                item_tags.setdefault(mid, set()).add(tid)

            # caterer → sorted list of active menu_item_ids
            cur.execute(
                "SELECT caterer_id, id FROM menu_items WHERE active = true ORDER BY caterer_id, id"
            )
            caterer_items: dict[int, list[int]] = {}
            for cid, mid in cur.fetchall():
                caterer_items.setdefault(cid, []).append(mid)

            # enrolments with their dietary tag_ids
            cur.execute(
                """
                SELECT e.id, e.school_id,
                       COALESCE(
                           array_agg(edt.dietary_tag_id)
                           FILTER (WHERE edt.dietary_tag_id IS NOT NULL),
                           ARRAY[]::bigint[]
                       )
                FROM enrolments e
                LEFT JOIN enrolment_dietary_tags edt ON edt.enrolment_id = e.id
                WHERE e.opted_out_of_catering = false
                GROUP BY e.id, e.school_id
                ORDER BY e.id
                """
            )
            enrolments = cur.fetchall()

            item_votes: dict[int, int] = {}
            pref_count = 0
            item_count = 0

            for enrolment_id, school_id, tag_ids in enrolments:
                caterer_id = school_caterer.get(school_id)
                if not caterer_id:
                    continue

                # Idempotency: skip if an active preference already exists
                cur.execute(
                    """
                    SELECT id FROM term_meal_preferences
                    WHERE enrolment_id = %s AND caterer_id = %s AND superseded_at IS NULL
                    """,
                    (enrolment_id, caterer_id),
                )
                if cur.fetchone():
                    continue

                student_tags = set(tag_ids)
                # Safe items: item.tags ⊇ student.tags (V4-OPT-06 rule)
                safe = [
                    mid for mid in caterer_items.get(caterer_id, [])
                    if student_tags <= item_tags.get(mid, set())
                ]
                if not safe:
                    continue  # no safe items — auto_pick handles this at order time

                n = rng.randint(min(3, len(safe)), min(5, len(safe)))
                chosen = rng.sample(safe, n)

                cur.execute(
                    """
                    INSERT INTO term_meal_preferences
                        (enrolment_id, caterer_id, captured_at, captured_by)
                    VALUES (%s, %s, %s, 'parent')
                    RETURNING id
                    """,
                    (enrolment_id, caterer_id, CAPTURED_AT),
                )
                pref_id = cur.fetchone()[0]
                pref_count += 1

                for mid in chosen:
                    cur.execute(
                        "INSERT INTO term_meal_preference_items (preference_id, menu_item_id) VALUES (%s, %s)",
                        (pref_id, mid),
                    )
                    item_count += 1
                    item_votes[mid] = item_votes.get(mid, 0) + 1

            conn.commit()
            print(f"term_meal_preferences:      {pref_count} rows")
            print(f"term_meal_preference_items: {item_count} rows")

            # Update canonical_menu_order per caterer (most-voted item first)
            for caterer_id, items in caterer_items.items():
                ranked = sorted(items, key=lambda m: item_votes.get(m, 0), reverse=True)
                cur.execute(
                    """
                    UPDATE caterers
                    SET canonical_menu_order = %s::jsonb,
                        canonical_order_set_at = %s
                    WHERE id = %s
                    """,
                    (json.dumps(ranked), CAPTURED_AT, caterer_id),
                )
            conn.commit()
            print("canonical_menu_order:       updated on all 4 caterers")


if __name__ == "__main__":
    run()
