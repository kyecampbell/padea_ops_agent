#!/usr/bin/env python3
"""
run_all.py
Master ingest runner. Executes all seed scripts in dependency order.

Run from project root:
    uv run python -m src.ingest.run_all
or:
    source .venv/bin/activate && python -m src.ingest.run_all

Dependency order:
  1.  seed_dietary_tags               — reference data (no FK deps)
  2.  seed_schools                    — no FK deps at insert time
  3.  seed_caterers                   — needs schools (sets current_caterer_id)
  4.  seed_tutors                     — no FK deps
  5.  seed_menu_items                 — needs caterers + dietary_tags
  6.  seed_sessions                   — needs schools + tutors
  7.  seed_enrolments                 — needs schools + dietary_tags
  8.  seed_absences                   — needs enrolments
  9.  seed_exclusions                 — needs schools
  10. seed_enrolment_session_slots    — needs enrolments + session_slots

Dummy data for demo (run after core data is seeded):
  11. seed_term_meal_preferences      — DUMMY: parent meal preferences + canonical_menu_order
  12. seed_feedback_history           — DUMMY: 5 weeks of historical orders + feedback
  13. seed_upcoming_exclusions        — DUMMY: school camp (ISHS Yr10) + Term 2 holidays
  14. seed_upcoming_absences          — DUMMY: ~11 upcoming student absences
  15. seed_meal_requests              — DUMMY: ~40% of students file a dietary-safe meal request
"""
import sys

def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")

def main() -> None:
    from src.ingest import seed_dietary_tags
    from src.ingest import seed_schools
    from src.ingest import seed_caterers
    from src.ingest import seed_tutors
    from src.ingest import seed_menu_items
    from src.ingest import seed_sessions
    from src.ingest import seed_enrolments
    from src.ingest import seed_absences
    from src.ingest import seed_exclusions
    from src.ingest import seed_enrolment_session_slots
    from src.ingest import seed_term_meal_preferences
    from src.ingest import seed_feedback_history
    from src.ingest import seed_upcoming_exclusions
    from src.ingest import seed_upcoming_absences
    from src.ingest import seed_meal_requests

    steps = [
        ("1/15  dietary_tags",                 seed_dietary_tags.run),
        ("2/15  schools",                      seed_schools.run),
        ("3/15  caterers",                     seed_caterers.run),
        ("4/15  tutors",                       seed_tutors.run),
        ("5/15  menu_items",                   seed_menu_items.run),
        ("6/15  sessions",                     seed_sessions.run),
        ("7/15  enrolments",                   seed_enrolments.run),
        ("8/15  absences",                     seed_absences.run),
        ("9/15  exclusions",                   seed_exclusions.run),
        ("10/15 enrolment_session_slots",      seed_enrolment_session_slots.run),
        ("11/15 term_meal_preferences [DEMO]", seed_term_meal_preferences.run),
        ("12/15 feedback_history [DEMO]",      seed_feedback_history.run),
        ("13/15 upcoming_exclusions [DEMO]",   seed_upcoming_exclusions.run),
        ("14/15 upcoming_absences [DEMO]",     seed_upcoming_absences.run),
        ("15/15 meal_requests [DEMO]",         seed_meal_requests.run),
    ]

    for label, fn in steps:
        section(label)
        try:
            fn()
        except Exception as exc:
            print(f"\n  ❌ FAILED: {exc}", file=sys.stderr)
            raise

    print(f"\n{'═' * 60}")
    print("  ✅  All seed scripts completed successfully.")
    print(f"{'═' * 60}\n")


if __name__ == "__main__":
    main()
