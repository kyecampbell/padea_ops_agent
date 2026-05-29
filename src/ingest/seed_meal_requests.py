#!/usr/bin/env python3
"""
seed_meal_requests.py — DUMMY DATA

Simulates the tutor-app per-session meal request feature (V3-FB-01): each week a
subset of students ask for a specific meal at their next session, overriding the
normal canonical-order rotation. Roughly 40% of active students file a request.

FAKE DATA: the tutor app that captures these is outside this build's scope. We
assume it works and, critically, that it only ever offers a student meals they
can safely eat — so every request seeded here is dietary-safe
(item.tags ⊇ student.tags, the V4-OPT-06 rule). Requests draw from the full
dietary-safe menu, not just the student's parent-approved set (per the schema
comment on meal_requests).

Each request targets the student's next un-ordered, non-excluded session for
their slot, so a future T-72h order composition will actually consume it via
compose_session_order's request → rotation → dietary-fallback priority.

Idempotent: re-running skips (enrolment, slot, date) rows that already exist.
"""
import random
from datetime import date, datetime, time, timedelta, timezone

from src.ingest.db import get_conn

SEED = 42
REQUEST_PROBABILITY = 0.40
# First session week we consider "upcoming" relative to the demo clock
# (Monday 2026-06-01). The per-slot picker advances by whole weeks from here,
# skipping dates that already have an order or fall in an exclusion.
BASE_DATE = date(2026, 6, 8)
_MAX_WEEKS = 20  # safety cap on the per-slot date search


def _next_session_date(
    day_of_week: int,
    ordered_dates: set[date],
    exclusion_ranges: list[tuple[date, date]],
    base: date,
) -> date | None:
    """
    First date >= base whose ISO weekday matches day_of_week (1=Mon..7=Sun),
    that has no existing order for the slot and falls in no exclusion range.
    Advances a whole week at a time so the weekday is preserved.
    """
    # Align base to the target weekday.
    delta = (day_of_week - base.isoweekday()) % 7
    candidate = base + timedelta(days=delta)
    for _ in range(_MAX_WEEKS):
        in_exclusion = any(start <= candidate <= end for start, end in exclusion_ranges)
        if candidate not in ordered_dates and not in_exclusion:
            return candidate
        candidate += timedelta(days=7)
    return None


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

            # caterer → list of active menu_item_ids
            cur.execute(
                "SELECT caterer_id, id FROM menu_items WHERE active = true ORDER BY caterer_id, id"
            )
            caterer_items: dict[int, list[int]] = {}
            for cid, mid in cur.fetchall():
                caterer_items.setdefault(cid, []).append(mid)

            # session_slots: id → (school_id, day_of_week)
            cur.execute("SELECT id, school_id, day_of_week FROM session_slots")
            slot_meta: dict[int, tuple[int, int]] = {
                r[0]: (r[1], r[2]) for r in cur.fetchall()
            }

            # existing order dates per slot (so requests don't target an already-composed session)
            cur.execute("SELECT session_slot_id, session_date FROM orders")
            slot_ordered: dict[int, set[date]] = {}
            for slot_id, sdate in cur.fetchall():
                slot_ordered.setdefault(slot_id, set()).add(sdate)

            # exclusion ranges per school
            cur.execute("SELECT school_id, start_date, end_date FROM exclusions")
            school_exclusions: dict[int, list[tuple[date, date]]] = {}
            for sid, start, end in cur.fetchall():
                school_exclusions.setdefault(sid, []).append((start, end))

            # Resolve one target session date per slot, once.
            slot_target: dict[int, date | None] = {}
            for slot_id, (school_id, dow) in slot_meta.items():
                slot_target[slot_id] = _next_session_date(
                    dow,
                    slot_ordered.get(slot_id, set()),
                    school_exclusions.get(school_id, []),
                    BASE_DATE,
                )

            # active enrolments + their slot + dietary tag_ids
            cur.execute(
                """
                SELECT e.id, e.school_id, ess.session_slot_id,
                       COALESCE(
                           array_agg(edt.dietary_tag_id)
                           FILTER (WHERE edt.dietary_tag_id IS NOT NULL),
                           ARRAY[]::bigint[]
                       )
                FROM enrolments e
                JOIN enrolment_session_slots ess ON ess.enrolment_id = e.id
                LEFT JOIN enrolment_dietary_tags edt ON edt.enrolment_id = e.id
                WHERE e.opted_out_of_catering = false
                GROUP BY e.id, e.school_id, ess.session_slot_id
                ORDER BY e.id
                """
            )
            enrolments = cur.fetchall()

            inserted = 0
            skipped_existing = 0
            no_safe_item = 0
            no_target = 0

            for enrolment_id, school_id, slot_id, tag_ids in enrolments:
                # Draw the dice for EVERY eligible student first so selection is
                # stable regardless of downstream skips.
                selected = rng.random() < REQUEST_PROBABILITY
                if not selected:
                    continue

                caterer_id = school_caterer.get(school_id)
                if not caterer_id:
                    continue

                target_date = slot_target.get(slot_id)
                if target_date is None:
                    no_target += 1
                    continue

                student_tags = set(tag_ids)
                safe = [
                    mid for mid in caterer_items.get(caterer_id, [])
                    if student_tags <= item_tags.get(mid, set())
                ]
                if not safe:
                    no_safe_item += 1
                    continue

                menu_item_id = rng.choice(safe)
                requested_at = datetime.combine(
                    target_date - timedelta(days=5), time(9, 0), tzinfo=timezone.utc
                )

                cur.execute(
                    """
                    INSERT INTO meal_requests
                        (enrolment_id, session_slot_id, session_date, menu_item_id, requested_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (enrolment_id, session_slot_id, session_date) DO NOTHING
                    RETURNING id
                    """,
                    (enrolment_id, slot_id, target_date, menu_item_id, requested_at),
                )
                if cur.fetchone():
                    inserted += 1
                else:
                    skipped_existing += 1

        conn.commit()

    print(f"meal_requests inserted:        {inserted} rows")
    print(f"  skipped (already existed):   {skipped_existing}")
    print(f"  skipped (no safe menu item): {no_safe_item}")
    print(f"  skipped (no target session): {no_target}")
    print(f"  target dates per slot:       "
          f"{ {k: str(v) for k, v in sorted(slot_target.items())} }")


if __name__ == "__main__":
    run()
