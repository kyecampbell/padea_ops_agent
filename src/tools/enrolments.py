"""
src/tools/enrolments.py
Enrolment-related tools for the Padea operations agent.
"""
from __future__ import annotations

import re
from datetime import date

from src.ingest.db import get_conn


def get_enrolments_for_session(session_slot_id: int, session_date: date) -> list[dict]:
    """
    Return the list of students who need a meal for a given session.

    Business rules applied here (non-negotiable):
    - Whole-school exclusion (school physically closed): exclude everyone,
      including dietary students.
    - Year-level exclusion: exclude students in that year level UNLESS they
      have dietary requirements (dietary students always get a meal).
    - Absence: exclude absent students UNLESS they have dietary requirements.
    - opted_out_of_catering=True: always excluded.
    - Enrolment lifecycle: only students active on session_date are included.

    Returns list of dicts with keys:
        enrolment_id, student_name, student_year_level, parent_email,
        dietary_tag_names (list[str])
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # ── 1. Resolve school for this session_slot ───────────────────────
            cur.execute(
                "SELECT school_id FROM session_slots WHERE id = %s",
                (session_slot_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"session_slot_id {session_slot_id} not found")
            school_id: int = row[0]

            # ── 2. Fetch exclusions covering session_date for this school ─────
            cur.execute(
                """
                SELECT reason
                FROM exclusions
                WHERE school_id = %s
                  AND enrolment_id IS NULL
                  AND start_date <= %s
                  AND end_date   >= %s
                """,
                (school_id, session_date, session_date),
            )
            exclusion_reasons = [r[0] for r in cur.fetchall()]

            whole_school_excluded = any(
                not _is_year_level_exclusion(r) for r in exclusion_reasons
            )
            excluded_year_levels: set[int] = set()
            for reason in exclusion_reasons:
                yl = _extract_year_level(reason)
                if yl is not None:
                    excluded_year_levels.add(yl)

            # ── 3. Fetch active cohort with dietary tags and absence flag ─────
            cur.execute(
                """
                SELECT
                    e.id,
                    e.student_name,
                    e.student_year_level,
                    e.parent_email,
                    e.other_allergy_notes,
                    COALESCE(
                        ARRAY_AGG(dt.name ORDER BY dt.name)
                        FILTER (WHERE dt.name IS NOT NULL),
                        '{}'::text[]
                    ) AS dietary_tag_names,
                    COUNT(a.id) > 0 AS is_absent
                FROM enrolments e
                JOIN enrolment_session_slots ess
                    ON ess.enrolment_id = e.id
                   AND ess.session_slot_id = %s
                   AND ess.left_date IS NULL
                LEFT JOIN enrolment_dietary_tags edt ON edt.enrolment_id = e.id
                LEFT JOIN dietary_tags dt ON dt.id = edt.dietary_tag_id
                LEFT JOIN absences a
                    ON a.enrolment_id = e.id
                   AND a.absence_date = %s
                WHERE e.opted_out_of_catering = false
                  AND e.current_period_start_date <= %s
                  AND (e.current_period_end_date IS NULL OR e.current_period_end_date > %s)
                GROUP BY e.id, e.student_name, e.student_year_level, e.parent_email
                ORDER BY e.student_name
                """,
                (session_slot_id, session_date, session_date, session_date),
            )
            rows = cur.fetchall()

    # ── 4. Apply business rules ───────────────────────────────────────────────
    result: list[dict] = []
    for enrolment_id, student_name, year_level, parent_email, allergy_notes, dietary_tags, is_absent in rows:
        has_dietary = bool(dietary_tags)

        # Whole-school closure: no override, everyone excluded
        if whole_school_excluded:
            continue

        # Absence: dietary students still get a meal
        if is_absent and not has_dietary:
            continue

        # Year-level exclusion: dietary students still get a meal
        if year_level in excluded_year_levels and not has_dietary:
            continue

        result.append({
            "enrolment_id":        enrolment_id,
            "student_name":        student_name,
            "student_year_level":  year_level,
            "parent_email":        parent_email,
            "dietary_tag_names":   list(dietary_tags),
            "other_allergy_notes": allergy_notes,
        })

    return result


def get_enrolment_dietary_tags(enrolment_id: int) -> list[str]:
    """Return list of dietary tag name strings for an enrolment."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT dt.name
                FROM enrolment_dietary_tags edt
                JOIN dietary_tags dt ON dt.id = edt.dietary_tag_id
                WHERE edt.enrolment_id = %s
                ORDER BY dt.name
                """,
                (enrolment_id,),
            )
            return [r[0] for r in cur.fetchall()]


# ── helpers ───────────────────────────────────────────────────────────────────

_YEAR_LEVEL_RE = re.compile(r'[Yy]ear\s+(\d+)\s+excluded', re.IGNORECASE)


def _is_year_level_exclusion(reason: str) -> bool:
    return bool(_YEAR_LEVEL_RE.search(reason))


def _extract_year_level(reason: str) -> int | None:
    m = _YEAR_LEVEL_RE.search(reason)
    return int(m.group(1)) if m else None
