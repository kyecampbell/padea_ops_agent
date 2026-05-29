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
            # Scope is read from the structured year_levels_excluded column:
            # an empty array means the whole school is closed; a non-empty array
            # lists the excluded year levels. (Matches get_exclusions /
            # get_year_level_exclusions — no text-parsing of reason.)
            cur.execute(
                """
                SELECT year_levels_excluded
                FROM exclusions
                WHERE school_id = %s
                  AND enrolment_id IS NULL
                  AND start_date <= %s
                  AND end_date   >= %s
                """,
                (school_id, session_date, session_date),
            )
            exclusion_scopes = [r[0] for r in cur.fetchall()]

            whole_school_excluded = any(not scope for scope in exclusion_scopes)
            excluded_year_levels: set[int] = set()
            for scope in exclusion_scopes:
                excluded_year_levels.update(scope or [])

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


def find_session_for_absence(
    student_name: str,
    session_date: date,
    parent_email: str | None = None,
) -> list[dict]:
    """
    Resolve an inbound absence email to the concrete enrolment + session it
    refers to, and report whether that session's order has already gone out.

    An absence email gives a student name and a date — not an enrolment_id. This
    tool bridges that gap deterministically:
      1. Match active enrolments by case-insensitive student_name (trimmed).
         Active = current_period covers session_date and not opted out.
      2. For each match, find the session_slot(s) the student attends
         (left_date IS NULL) whose day_of_week equals session_date's weekday.
      3. For each (enrolment, slot), report the order status for that date:
         order_exists, order_id, and order_sent (a session_order email was sent
         for that order).

    parent_email, when supplied, is matched leniently: rows whose parent_email
    equals it are preferred, but since the demo dataset shares one parent address
    it is NOT used to exclude matches. Pass the raw From address; an embedded
    "Name <addr>" form is handled.

    The caller (agent) then ALWAYS records the absence via upsert_absence, and
    skips any order amendment when order_exists is true — the caterer brief is
    locked at T-72h (zero operational margin; walk-backs are an accepted gap).

    Returns a list of candidate dicts (empty if no name/day match):
        enrolment_id, student_name, parent_email, school_id, session_slot_id,
        session_date, day_of_week, order_exists, order_id, order_sent
    Multiple rows mean an ambiguous match — the agent should escalate.
    """
    weekday = session_date.isoweekday()  # 1=Mon .. 7=Sun, matches session_slots.day_of_week
    email_addr = _extract_email_address(parent_email) if parent_email else None

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    e.id, e.student_name, e.parent_email,
                    ss.school_id, ss.id, ss.day_of_week
                FROM enrolments e
                JOIN enrolment_session_slots ess
                    ON ess.enrolment_id = e.id
                   AND ess.left_date IS NULL
                JOIN session_slots ss
                    ON ss.id = ess.session_slot_id
                   AND ss.active = true
                   AND ss.day_of_week = %s
                WHERE lower(btrim(e.student_name)) = lower(btrim(%s))
                  AND e.opted_out_of_catering = false
                  AND e.current_period_start_date <= %s
                  AND (e.current_period_end_date IS NULL OR e.current_period_end_date > %s)
                ORDER BY e.id, ss.id
                """,
                (weekday, student_name, session_date, session_date),
            )
            matches = cur.fetchall()

            result: list[dict] = []
            for enr_id, name, p_email, school_id, slot_id, dow in matches:
                cur.execute(
                    "SELECT id FROM orders WHERE session_slot_id = %s AND session_date = %s",
                    (slot_id, session_date),
                )
                order_row = cur.fetchone()
                order_id = order_row[0] if order_row else None

                order_sent = False
                if order_id is not None:
                    cur.execute(
                        """
                        SELECT 1 FROM outbound_emails
                        WHERE email_type = 'session_order'
                          AND status = 'sent'
                          AND related_order_id = %s
                        LIMIT 1
                        """,
                        (order_id,),
                    )
                    order_sent = cur.fetchone() is not None

                result.append({
                    "enrolment_id":    enr_id,
                    "student_name":    name,
                    "parent_email":    p_email,
                    "school_id":       school_id,
                    "session_slot_id": slot_id,
                    "session_date":    session_date,
                    "day_of_week":     dow,
                    "order_exists":    order_id is not None,
                    "order_id":        order_id,
                    "order_sent":      order_sent,
                })

    if email_addr:
        preferred = [r for r in result if (r["parent_email"] or "").lower() == email_addr]
        if preferred:
            return preferred
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

_EMAIL_RE = re.compile(r'[\w.+-]+@[\w.-]+\.\w+')


def _extract_email_address(raw: str) -> str | None:
    """Pull a bare lowercased address out of a From header ("Name <a@b.com>" → a@b.com)."""
    m = _EMAIL_RE.search(raw or "")
    return m.group(0).lower() if m else None
