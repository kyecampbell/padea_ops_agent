"""
src/agent/loop.py

Claude tool-calling agent loop for the Padea Operations Agent.

Responsibilities:
  - TOOL_SCHEMAS:  27 JSON schemas exposed to the Claude API.
  - TOOL_REGISTRY: tool name → Python callable (26 entries; add_note excluded).
  - _PARAM_TYPES:  coercion map for date/datetime parameters (15 entries).
  - _serialise():  recursive JSON-safe serialiser.
  - dispatch():    coerce → call → serialise → return (result, is_error).
  - run():         full agent loop (STEP 3 — not yet implemented).
"""

from __future__ import annotations

import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import anthropic

from config.settings import settings
from src.tools.infrastructure import (
    create_agent_run,
    complete_agent_run,
    log_agent_step,
    check_and_resolve_crashed_runs,
)
from src.tools.sessions import get_sessions_needing_orders, get_session_slot
from src.tools.enrolments import get_enrolments_for_session, get_enrolment_dietary_tags
from src.tools.meals import (
    item_is_safe_for_enrolment,
    auto_pick_dietary_meal,
    get_meal_request,
    get_next_rotation_meal,
)
from src.tools.orders import compose_session_order, compose_order_email
from src.tools.absences import (
    get_absence,
    upsert_absence,
    get_exclusions,
    get_year_level_exclusions,
)
from src.tools.quality import get_feedback_for_session, compute_rolling_mean, get_feedback_since
from src.tools.caterers import caterers_within_range, project_weekly_cost, check_weekly_moq
from src.tools.weekly_summary import generate_weekly_summary, compose_weekly_summary_email
from src.tools.gmail import gmail_send, queue_email_for_approval
from src.tools.inbound import gmail_poll_inbox, classify_inbound_email

BRISBANE = ZoneInfo("Australia/Brisbane")

_SYSTEM_PROMPT_PATH = Path(__file__).parent.parent.parent / "agent_context" / "system_prompt.md"


def _load_system_prompt() -> str:
    text = _SYSTEM_PROMPT_PATH.read_text()
    sep_idx = text.find("\n---\n")
    if sep_idx != -1:
        return text[sep_idx + 5:].strip()
    return text.strip()


# =============================================================================
# TOOL SCHEMAS — 27 JSON schemas exposed to the Claude API
# =============================================================================

TOOL_SCHEMAS: list[dict] = [

    # ── SESSIONS ──────────────────────────────────────────────────────────────

    {
        "name": "get_sessions_needing_orders",
        "description": (
            "Return session slots whose T-72h ordering mark falls within "
            "[as_of - window_hours, as_of + window_hours] and that have no order yet. "
            "Returns list of {session_slot_id, session_date, school_id, caterer_id, "
            "session_start_datetime}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "as_of": {
                    "type": "string",
                    "description": (
                        "ISO datetime string (e.g. '2026-08-01T15:00:00+10:00'). "
                        "Defaults to now() Brisbane if omitted."
                    ),
                },
                "window_hours": {
                    "type": "number",
                    "description": "Half-window in hours either side of as_of. Default 1.0.",
                },
            },
            "required": [],
        },
    },

    {
        "name": "get_session_slot",
        "description": (
            "Return the full session_slots row for a session_slot_id: "
            "{id, school_id, day_of_week, start_time, dinner_time, end_time, room, active}. "
            "Raises ValueError if not found."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_slot_id": {
                    "type": "integer",
                    "description": "Primary key of the session_slots row.",
                },
            },
            "required": ["session_slot_id"],
        },
    },

    # ── ENROLMENTS ────────────────────────────────────────────────────────────

    {
        "name": "get_enrolments_for_session",
        "description": (
            "Return active, opted-in students needing a meal for (session_slot, date). "
            "Applies absences, whole-school exclusions, year-level exclusions, and the "
            "dietary override (dietary students always get a meal unless school is "
            "physically closed). "
            "Returns list of {enrolment_id, student_name, student_year_level, "
            "parent_email, dietary_tag_names, other_allergy_notes}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_slot_id": {
                    "type": "integer",
                    "description": "Primary key of the session_slots row.",
                },
                "session_date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD. Always explicit — never 'today'.",
                },
            },
            "required": ["session_slot_id", "session_date"],
        },
    },

    {
        "name": "get_enrolment_dietary_tags",
        "description": (
            "Return list of dietary tag names for an enrolment "
            "(e.g. ['halal', 'vegetarian']). Empty list = no restrictions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "enrolment_id": {
                    "type": "integer",
                    "description": "Primary key of the enrolments row.",
                },
            },
            "required": ["enrolment_id"],
        },
    },

    # ── MEALS ─────────────────────────────────────────────────────────────────

    {
        "name": "item_is_safe_for_enrolment",
        "description": (
            "Return true if item.tags ⊇ student.tags (set containment). "
            "Students with no dietary tags: always true (vacuously safe). "
            "Use to verify any meal selection, not just auto-picks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "menu_item_id": {
                    "type": "integer",
                    "description": "Primary key of the menu_items row.",
                },
                "enrolment_id": {
                    "type": "integer",
                    "description": "Primary key of the enrolments row.",
                },
            },
            "required": ["menu_item_id", "enrolment_id"],
        },
    },

    {
        "name": "auto_pick_dietary_meal",
        "description": (
            "Return any active menu item for this caterer that passes all of the "
            "student's dietary tags. Returns null if none exists — caller must raise "
            "an urgent escalation in that case. Result: {menu_item_id, name, price_cents}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "enrolment_id": {
                    "type": "integer",
                    "description": "Primary key of the enrolments row.",
                },
                "caterer_id": {
                    "type": "integer",
                    "description": "Primary key of the caterers row.",
                },
            },
            "required": ["enrolment_id", "caterer_id"],
        },
    },

    {
        "name": "get_meal_request",
        "description": (
            "Return the unconsumed meal_request for (enrolment, session_slot, date) "
            "if one exists, else null. Null = no request filed; use rotation instead. "
            "Result: {request_id, menu_item_id, name, price_cents}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "enrolment_id": {
                    "type": "integer",
                    "description": "Primary key of the enrolments row.",
                },
                "session_slot_id": {
                    "type": "integer",
                    "description": "Primary key of the session_slots row.",
                },
                "session_date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD.",
                },
            },
            "required": ["enrolment_id", "session_slot_id", "session_date"],
        },
    },

    {
        "name": "get_next_rotation_meal",
        "description": (
            "Return the next menu item in the student's rotation for this caterer: "
            "the item from their approved set (canonical popularity order) served "
            "least recently. Returns null if no approved set exists for this caterer. "
            "Result: {menu_item_id, name, price_cents}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "enrolment_id": {
                    "type": "integer",
                    "description": "Primary key of the enrolments row.",
                },
                "caterer_id": {
                    "type": "integer",
                    "description": "Primary key of the caterers row.",
                },
            },
            "required": ["enrolment_id", "caterer_id"],
        },
    },

    # ── ORDERS ────────────────────────────────────────────────────────────────

    {
        "name": "compose_session_order",
        "description": (
            "Full order composition pipeline for one (session_slot, date): build cohort, "
            "select meals (request → rotation → dietary_auto_pick), persist order and "
            "order_lines. "
            "Returns {order_id, caterer_id, total_students, total_cost_cents, "
            "order_lines, safety_records, escalations}. "
            "safety_records has one entry per student with safe=true/false and "
            "other_allergy_notes — the loop processes these unconditionally after dispatch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_slot_id": {
                    "type": "integer",
                    "description": "Primary key of the session_slots row.",
                },
                "session_date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD.",
                },
            },
            "required": ["session_slot_id", "session_date"],
        },
    },

    {
        "name": "compose_order_email",
        "description": (
            "Render the per-session order email body for a composed order: session "
            "details, deliver-by time, per-student meal list with dietary safety flags "
            "(⚠ UNSAFE MATCH when item.tags ⊄ student.tags; ⚠ ALLERGY NOTE (unverified) "
            "for free-text other_allergy_notes), and per-meal count summary. "
            "No costs appear on per-session order emails. "
            "Demo mode prepends [DEMO — Intended for: caterer_email]. "
            "Returns rendered string."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "Primary key of the orders row.",
                },
            },
            "required": ["order_id"],
        },
    },

    # ── ABSENCES ──────────────────────────────────────────────────────────────

    {
        "name": "get_absence",
        "description": (
            "Return the absence row for (enrolment_id, absence_date) if one exists, "
            "else null. Null = no absence filed — the normal state, not an error. "
            "Walk-backs are row deletions, so a returned row is always an active "
            "absence. Result: {id, enrolment_id, absence_date, received_at, notes, ...}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "enrolment_id": {
                    "type": "integer",
                    "description": "Primary key of the enrolments row.",
                },
                "absence_date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD.",
                },
            },
            "required": ["enrolment_id", "absence_date"],
        },
    },

    {
        "name": "upsert_absence",
        "description": (
            "Insert an absence for (enrolment_id, absence_date). Idempotent — "
            "ON CONFLICT DO NOTHING (original received_at preserved). Returns "
            "absence_id (int). Use when processing an inbound absence notification email."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "enrolment_id": {
                    "type": "integer",
                    "description": "Primary key of the enrolments row.",
                },
                "absence_date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD.",
                },
                "source_email_message_id": {
                    "type": "string",
                    "description": "Gmail message ID of the source email (optional).",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional free-text note about the absence.",
                },
            },
            "required": ["enrolment_id", "absence_date"],
        },
    },

    {
        "name": "get_exclusions",
        "description": (
            "Return all exclusion rows covering this school on session_date. "
            "Each row: {id, school_id, enrolment_id, reason, start_date, end_date, "
            "year_levels_excluded}. "
            "year_levels_excluded=[] means whole-school (all year levels excluded). "
            "enrolment_id=null means school-wide scope. "
            "Parameter is session_date, not as_of."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "school_id": {
                    "type": "integer",
                    "description": "Primary key of the schools row.",
                },
                "session_date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD.",
                },
            },
            "required": ["school_id", "session_date"],
        },
    },

    {
        "name": "get_year_level_exclusions",
        "description": (
            "Return school-level exclusions that target specific year levels on "
            "session_date (enrolment_id IS NULL and year_levels_excluded != []). "
            "Returns list of {id, reason, excluded_year_levels: list[int]}. "
            "Parameter is session_date, not as_of."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "school_id": {
                    "type": "integer",
                    "description": "Primary key of the schools row.",
                },
                "session_date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD.",
                },
            },
            "required": ["school_id", "session_date"],
        },
    },

    # ── QUALITY ───────────────────────────────────────────────────────────────

    {
        "name": "get_feedback_for_session",
        "description": (
            "Return feedback summary for (session_slot, date): "
            "manager_rating (1-5 or null), manager_comments, five checklist booleans "
            "(food_on_time, correct_count_received, correct_dietary_delivered, "
            "food_temperature_ok, visibly_wrong), meals_left, kids_who_didnt_eat, "
            "tutor_ratings list, student_avg. All null/empty if no order exists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_slot_id": {
                    "type": "integer",
                    "description": "Primary key of the session_slots row.",
                },
                "session_date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD.",
                },
            },
            "required": ["session_slot_id", "session_date"],
        },
    },

    {
        "name": "compute_rolling_mean",
        "description": (
            "Unweighted mean of all non-null feedback ratings (tutor + manager) for "
            "this caterer in the weeks-week window ending at as_of. "
            "Returns null if fewer than 3 ratings exist (insufficient data). "
            "V4-OPT-04: direct filter on feedback.caterer_id — no joins needed. "
            "Parameter is 'weeks' (not 'window'), default 4."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "caterer_id": {
                    "type": "integer",
                    "description": "Primary key of the caterers row.",
                },
                "weeks": {
                    "type": "integer",
                    "description": "Window size in weeks. Default 4.",
                },
                "as_of": {
                    "type": "string",
                    "description": "ISO datetime string. Defaults to now() Brisbane if omitted.",
                },
            },
            "required": ["caterer_id"],
        },
    },

    {
        "name": "get_feedback_since",
        "description": (
            "Return all feedback rows submitted strictly after since_timestamp, "
            "joined with session_slot_id and session_date. "
            "Takes ONE parameter (since_timestamp: datetime) — not caterer_id. "
            "Use compute_rolling_mean for per-caterer aggregation. "
            "Returns list of {id, source, caterer_id, rating, submitted_at, "
            "session_slot_id, session_date}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "since_timestamp": {
                    "type": "string",
                    "description": (
                        "ISO datetime string (e.g. '2026-05-20T00:00:00+10:00'). "
                        "Only feedback submitted strictly after this timestamp is returned."
                    ),
                },
            },
            "required": ["since_timestamp"],
        },
    },

    # ── CATERERS ──────────────────────────────────────────────────────────────

    {
        "name": "caterers_within_range",
        "description": (
            "Return caterers whose home_postcode centroid is within their own "
            "max_delivery_km radius of the school's postcode centroid. "
            "Each caterer's range is their own declared max_delivery_km — "
            "there is no global radius_km parameter. "
            "exclude_caterer_id omits a specific caterer (e.g. the incumbent "
            "when building an RFP candidate list). "
            "Returns list of {caterer_id, name, contact_email, home_postcode, "
            "max_delivery_km, delivery_fee_cents, distance_km}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "school_id": {
                    "type": "integer",
                    "description": "Primary key of the schools row.",
                },
                "exclude_caterer_id": {
                    "type": "integer",
                    "description": "Caterer ID to exclude from results (typically the incumbent). Optional.",
                },
            },
            "required": ["school_id"],
        },
    },

    {
        "name": "project_weekly_cost",
        "description": (
            "Project the weekly catering cost for a caterer at a school. "
            "All amounts GST-inclusive, integer cents. MOQ: moq_5 tier assumed. "
            "Uses current cohort size and current active menu prices. "
            "No as_of parameter. "
            "Returns {cohort_size, per_meal_price_cents, delivery_fee_cents, "
            "moq_floor_cents (null if no shortfall), projected_total_cents}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "caterer_id": {
                    "type": "integer",
                    "description": "Primary key of the caterers row.",
                },
                "school_id": {
                    "type": "integer",
                    "description": "Primary key of the schools row.",
                },
            },
            "required": ["caterer_id", "school_id"],
        },
    },

    {
        "name": "check_weekly_moq",
        "description": (
            "Check MOQ compliance for ONE caterer in the ISO week containing week_of. "
            "moq_applicable = min-items threshold for the week's variety count "
            "(null if variety count is outside {4,5,6}). "
            "shortfall and shortfall_cents are always ints (0 if no shortfall). "
            "Call once per caterer to scope the check correctly. "
            "Parameter is 'week_of: date' — no school_id, no as_of. "
            "Returns {total_items, moq_applicable, shortfall, shortfall_cents}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "caterer_id": {
                    "type": "integer",
                    "description": "Primary key of the caterers row.",
                },
                "week_of": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD — any date within the target week.",
                },
            },
            "required": ["caterer_id", "week_of"],
        },
    },

    # ── MONDAY CONSOLIDATED SUMMARY ───────────────────────────────────────────

    {
        "name": "generate_weekly_summary",
        "description": (
            "Generate the Monday consolidated summary for ONE caterer for the ISO "
            "week containing week_of (normalised Mon-Sun). Aggregates the week's "
            "orders into one payable figure: meals + delivery×sessions, GST "
            "normalised to an inclusive total. Computes MOQ floor if the week ran "
            "short, and quality rolling means (4w, 12w) pinned to as_of. "
            "If a weekly_consolidated_summary email already exists for this caterer "
            "this week, returns {already_completed: True} with no mutations. "
            "Returns a dict with caterer_name, caterer_email, week_start, week_end, "
            "total_items, total_cost_cents, grand_total_cents, gst_amount_cents, "
            "delivery_fee_cents, total_delivery_cents, sessions_count, moq_applicable, "
            "moq_floor_applied, moq_variance_cents, mean_4w, mean_12w, "
            "sustained_decline, session_breakdown, already_completed. "
            "Pass this whole dict to compose_weekly_summary_email."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "caterer_id": {
                    "type": "integer",
                    "description": "Primary key of the caterers row. One caterer per run.",
                },
                "week_of": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD — any date within the target week.",
                },
                "as_of": {
                    "type": "string",
                    "description": (
                        "ISO datetime string (e.g. '2026-06-01T15:30:00+10:00') used to "
                        "pin the quality rolling means. Defaults to now() Brisbane."
                    ),
                },
            },
            "required": ["caterer_id", "week_of"],
        },
    },

    {
        "name": "compose_weekly_summary_email",
        "description": (
            "Render the Monday consolidated summary email body from the dict "
            "returned by generate_weekly_summary. Read-only — no DB writes. "
            "Do NOT call with the {already_completed: True} early-return form. "
            "Returns the rendered email body string (demo-prefixed in demo mode)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "caterer_id": {
                    "type": "integer",
                    "description": "Primary key of the caterers row.",
                },
                "summary": {
                    "type": "object",
                    "description": (
                        "The full dict returned by generate_weekly_summary. Pass it "
                        "back unchanged."
                    ),
                },
            },
            "required": ["caterer_id", "summary"],
        },
    },

    # ── EMAIL DISPATCH ────────────────────────────────────────────────────────

    {
        "name": "gmail_send",
        "description": (
            "Send a ROUTINE email and record it in outbound_emails (status='sent'). "
            "Use ONLY for email_type 'session_order' and "
            "'weekly_consolidated_summary'. Commercial-relationship emails "
            "(warning, rfp, cancellation, rfp_loser_courtesy) must go through "
            "queue_email_for_approval instead — never gmail_send. "
            "Demo mode keeps intended_to_address as the real recipient and prefixes "
            "the stored body with a demo marker. Returns the outbound_email_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address."},
                "subject": {"type": "string", "description": "Email subject line."},
                "body": {"type": "string", "description": "Full email body text."},
                "email_type": {
                    "type": "string",
                    "enum": ["session_order", "weekly_consolidated_summary"],
                    "description": "Routine email type only.",
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional CC addresses.",
                },
                "related_order_id":   {"type": "integer", "description": "FK to the related order, if any."},
                "related_caterer_id": {"type": "integer", "description": "FK to the related caterer, if any."},
                "related_step_id":    {"type": "integer", "description": "FK to the agent_step, if any."},
            },
            "required": ["to", "subject", "body", "email_type"],
        },
    },

    {
        "name": "queue_email_for_approval",
        "description": (
            "Queue a COMMERCIAL-RELATIONSHIP email for manager approval "
            "(status='queued_for_approval'). Never sends and never auto-advances. "
            "Use for email_type 'warning', 'rfp', 'cancellation', "
            "'rfp_loser_courtesy'. Demo mode keeps intended_to_address as the real "
            "recipient and prefixes the stored body with a demo marker. "
            "Returns the outbound_email_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email_type": {
                    "type": "string",
                    "enum": ["warning", "rfp", "cancellation", "rfp_loser_courtesy"],
                    "description": "Commercial-relationship email type.",
                },
                "to": {"type": "string", "description": "Intended recipient email address."},
                "subject": {"type": "string", "description": "Email subject line."},
                "body": {"type": "string", "description": "Full email body text."},
                "related_step_id":    {"type": "integer", "description": "FK to the agent_step, if any."},
                "related_order_id":   {"type": "integer", "description": "FK to the related order, if any."},
                "related_caterer_id": {"type": "integer", "description": "FK to the related caterer, if any."},
            },
            "required": ["email_type", "to", "subject", "body"],
        },
    },

    # ── INBOUND EMAIL ─────────────────────────────────────────────────────────

    {
        "name": "gmail_poll_inbox",
        "description": (
            "Read UNREAD messages from the Padea Gmail inbox and return only those "
            "not yet recorded in inbound_email_records (deduped by gmail_message_id, "
            "so re-polling never double-processes). Returns a list of "
            "{gmail_message_id, from_address, subject, received_at, body}. "
            "Optionally pass since_last_run_timestamp (ISO) to only fetch messages "
            "received after that time. Call this at the start of every run."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "since_last_run_timestamp": {
                    "type": "string",
                    "description": (
                        "Optional ISO datetime. Only return messages received after "
                        "this time. Dedup still applies regardless."
                    ),
                },
            },
            "required": [],
        },
    },

    {
        "name": "classify_inbound_email",
        "description": (
            "Classify ONE inbound message into exactly one inbound type: 'absence', "
            "'caterer_order_confirmation', 'caterer_price_change_notification', "
            "'parent_enrolment_response', or 'unclassified'. Also writes the "
            "inbound_email_records dedup row. Pass the fields returned by "
            "gmail_poll_inbox for this message. Returns "
            "{gmail_message_id, classification}. After classifying, route the "
            "message per the Inbound email processing section."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gmail_message_id": {"type": "string", "description": "The Gmail message id from gmail_poll_inbox."},
                "from_address":     {"type": "string", "description": "Sender address from gmail_poll_inbox."},
                "subject":          {"type": "string", "description": "Subject from gmail_poll_inbox."},
                "body":             {"type": "string", "description": "Body text from gmail_poll_inbox."},
                "received_at":      {"type": "string", "description": "ISO datetime the message was received (from gmail_poll_inbox)."},
            },
            "required": ["gmail_message_id", "from_address", "subject", "body", "received_at"],
        },
    },

    # ── META-TOOL ─────────────────────────────────────────────────────────────

    {
        "name": "add_note",
        "description": (
            "Record an observation, decision, or escalation in the agent_steps audit "
            "log. Use for: flagging quality patterns, noting branch decisions, "
            "surfacing anything requiring operator attention. "
            "The label becomes tool_name in agent_steps "
            "(e.g. 'sustained_decline_detected', 'moq_shortfall_noted'); "
            "urgency controls rendering in the HTML decision log."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": (
                        "Short snake_case label — becomes tool_name in agent_steps. "
                        "E.g. 'sustained_decline_detected', 'moq_shortfall_noted', "
                        "'unclassified_inbound'."
                    ),
                },
                "body": {
                    "type": "string",
                    "description": "Full text of the observation or escalation. Operator reads this in the decision log.",
                },
                "urgency": {
                    "type": "string",
                    "enum": ["urgent", "notable", "informational", "none"],
                    "description": (
                        "Urgency tier: urgent=blocking something until operator acts; "
                        "notable=pattern worth attention; informational=audit trail; "
                        "none=routine tool call."
                    ),
                },
            },
            "required": ["label", "body", "urgency"],
        },
    },
]


# =============================================================================
# TOOL REGISTRY — name → Python callable (26 entries; add_note excluded)
# =============================================================================
# add_note is NOT registered here. dispatch() special-cases it before the
# registry lookup and logs via log_agent_step directly.

TOOL_REGISTRY: dict[str, Any] = {
    "get_sessions_needing_orders": get_sessions_needing_orders,
    "get_session_slot":            get_session_slot,
    "get_enrolments_for_session":  get_enrolments_for_session,
    "get_enrolment_dietary_tags":  get_enrolment_dietary_tags,
    "item_is_safe_for_enrolment":  item_is_safe_for_enrolment,
    "auto_pick_dietary_meal":      auto_pick_dietary_meal,
    "get_meal_request":            get_meal_request,
    "get_next_rotation_meal":      get_next_rotation_meal,
    "compose_session_order":       compose_session_order,
    "compose_order_email":         compose_order_email,
    "get_absence":                 get_absence,
    "upsert_absence":              upsert_absence,
    "get_exclusions":              get_exclusions,
    "get_year_level_exclusions":   get_year_level_exclusions,
    "get_feedback_for_session":    get_feedback_for_session,
    "compute_rolling_mean":        compute_rolling_mean,
    "get_feedback_since":          get_feedback_since,
    "caterers_within_range":       caterers_within_range,
    "project_weekly_cost":         project_weekly_cost,
    "check_weekly_moq":            check_weekly_moq,
    "generate_weekly_summary":     generate_weekly_summary,
    "compose_weekly_summary_email": compose_weekly_summary_email,
    "gmail_send":                  gmail_send,
    "queue_email_for_approval":    queue_email_for_approval,
    "gmail_poll_inbox":            gmail_poll_inbox,
    "classify_inbound_email":      classify_inbound_email,
}


# =============================================================================
# PARAMETER TYPE COERCION MAP — 15 entries
# date/datetime params arrive from the Claude API as JSON strings and must be
# coerced before calling the real Python functions.
#
# Corrections from locked design (session 013):
#   get_exclusions:          "as_of"         → "session_date": date
#   get_year_level_exclusions: "as_of"       → "session_date": date
#   get_feedback_since:      "since_date"    → "since_timestamp": datetime
#   check_weekly_moq:        "as_of": datetime → "week_of": date
#   project_weekly_cost:     "as_of" REMOVED — no such param in real signature
# =============================================================================

_PARAM_TYPES: dict[tuple[str, str], type] = {
    # Sessions
    ("get_sessions_needing_orders", "as_of"):           datetime,

    # Enrolments
    ("get_enrolments_for_session",  "session_date"):    date,

    # Meals
    ("get_meal_request",            "session_date"):    date,

    # Orders
    ("compose_session_order",       "session_date"):    date,

    # Absences
    ("get_absence",                 "absence_date"):    date,
    ("upsert_absence",              "absence_date"):    date,
    ("get_exclusions",              "session_date"):    date,
    ("get_year_level_exclusions",   "session_date"):    date,

    # Quality
    ("get_feedback_for_session",    "session_date"):    date,
    ("get_feedback_since",          "since_timestamp"): datetime,
    ("compute_rolling_mean",        "as_of"):           datetime,

    # Caterers
    ("check_weekly_moq",            "week_of"):         date,

    # Monday consolidated summary
    ("generate_weekly_summary",     "week_of"):         date,
    ("generate_weekly_summary",     "as_of"):           datetime,

    # Inbound email
    ("classify_inbound_email",      "received_at"):     datetime,
}


# =============================================================================
# SERIALISER
# =============================================================================

def _serialise(obj: Any) -> Any:
    """
    Recursively convert non-JSON-serialisable types to JSON-safe equivalents.

    Ordering matters: datetime before date (datetime is a subclass of date).
    bool is a subclass of int but requires no special handling (passes through).
    """
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, time):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialise(v) for v in obj]
    return obj


# =============================================================================
# DISPATCH
# =============================================================================

def dispatch(
    tool_name: str,
    tool_input: dict,
    run_id: int,
    step_index: int,
) -> tuple[Any, bool]:
    """
    Execute a tool call and return (result, is_error).

    Observation shapes:
      (a) success:         (_serialise(result), False)   tool returned data
      (b) business empty:  (None, False)                  tool returned None (no row, no request, etc.)
          business signal: (shortfall_dict, False)        tool returned meaningful signal dict
      (c) system error:    ({"error": True, ...}, True)   tool raised an exception

    is_error=True ONLY for shape (c). Shapes (a) and (b) both yield is_error=False.
    The Anthropic API uses is_error to route the model's response: False = normal
    result (even null); True = tool failure the model should reason about.

    add_note special case:
      Calls log_agent_step internally (label → tool_name in agent_steps).
      Returns (None, False). The outer loop MUST skip its own log_agent_step call
      when tool_name == "add_note" to avoid double-logging the same step_index.
    """
    # ── add_note: loop-backed meta-tool ──────────────────────────────────────
    if tool_name == "add_note":
        label = tool_input.get("label", "note")
        body = tool_input.get("body", "")
        urgency = tool_input.get("urgency", "none")
        log_agent_step(
            run_id=run_id,
            step_index=step_index,
            tool_name=label,
            tool_input={"body": body},
            tool_output_full=None,
            reasoning=None,
            urgency=urgency,
        )
        return None, False

    # ── registry lookup ───────────────────────────────────────────────────────
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        return (
            {
                "error": True,
                "type": "UnknownTool",
                "message": f"No tool named {tool_name!r} in registry",
            },
            True,
        )

    # ── type coercion ─────────────────────────────────────────────────────────
    coerced: dict[str, Any] = {}
    for k, v in tool_input.items():
        target_type = _PARAM_TYPES.get((tool_name, k))
        if target_type is date and isinstance(v, str):
            coerced[k] = date.fromisoformat(v)
        elif target_type is datetime and isinstance(v, str):
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=BRISBANE)
            coerced[k] = dt
        else:
            coerced[k] = v

    # Inject as_of = now(BRISBANE) when Claude omits it for get_sessions_needing_orders.
    # The real Python function requires as_of (not optional). Other as_of params
    # (compute_rolling_mean) handle None internally; no injection needed.
    if tool_name == "get_sessions_needing_orders" and "as_of" not in coerced:
        coerced["as_of"] = datetime.now(tz=BRISBANE)

    # The loop owns run_id; the model never sees it (not in the system prompt or
    # the trigger message). Inject it for the email tools so related_run_id is
    # always the correct FK — never model-guessed, omitted, or hard-failed. This
    # overwrites any model-supplied value, so it is authoritative.
    if tool_name in ("gmail_send", "queue_email_for_approval"):
        coerced["related_run_id"] = run_id

    # ── call ──────────────────────────────────────────────────────────────────
    try:
        result = fn(**coerced)
    except Exception as e:
        return (
            {"error": True, "type": type(e).__name__, "message": str(e)},
            True,
        )

    # ── serialise and return ──────────────────────────────────────────────────
    return _serialise(result), False


# =============================================================================
# AGENT LOOP — STEP 3 (not yet implemented)
# =============================================================================

def run(trigger_reason: str) -> None:
    """
    Main agent entry point. Called by the scheduler or directly in tests.

    STEP 3a: bare loop skeleton (create_agent_run, model call, dispatch, log,
             feed-back cycle, clean end_turn termination, exception handler).
    STEP 3b: hard-cap logic (checked before each dispatch; one urgent
             max_calls_reached step; is_error to all remaining blocks; one
             uncounted final summarising call; [CAP HIT at N/N] completion note).
    STEP 3c (next): safety_records unconditional logging.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    run_id = create_agent_run(trigger_reason=trigger_reason)
    system_prompt = _load_system_prompt()
    messages: list[dict] = [{"role": "user", "content": trigger_reason}]
    step_index = 0
    call_count = 0
    MAX = settings.max_tool_calls_per_run

    try:
        while True:
            response = client.messages.create(
                model=settings.agent_model,
                max_tokens=4096,
                system=system_prompt,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                text = next(
                    (b.text for b in response.content if b.type == "text"), ""
                )
                complete_agent_run(run_id, text)
                return

            tool_results: list[dict] = []
            cap_hit = False

            # Capture the model's text block from this turn — that is the
            # reasoning for every tool_use block in the same response.
            # None when the model goes straight to tool calls with no preamble.
            turn_reasoning: str | None = next(
                (b.text for b in response.content if b.type == "text"), None
            )

            for block in tool_use_blocks:
                tool_name = block.name
                tool_input = block.input  # dict from the Anthropic SDK

                # ── HARD CAP CHECK — before dispatch ─────────────────────────
                # call_count is the number already dispatched this run (across
                # all turns). When the cap is reached, no more dispatches are
                # made. The first block that trips the cap gets a logged urgent
                # step (max_calls_reached); all subsequent cap-tripped blocks in
                # the same response get is_error'd silently — one log entry is
                # enough. continue (not break) so the API receives a tool_result
                # for every tool_use block it emitted.
                if call_count >= MAX:
                    if not cap_hit:
                        log_agent_step(
                            run_id=run_id,
                            step_index=step_index,
                            tool_name="max_calls_reached",
                            tool_input={
                                "blocked_tool": tool_name,
                                "call_count": call_count,
                                "max": MAX,
                            },
                            tool_output_full=None,
                            reasoning=(
                                f"Hard cap {MAX} reached; aborting remaining "
                                f"tool calls in this response"
                            ),
                            urgency="urgent",
                        )
                        step_index += 1
                        cap_hit = True
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({
                            "error": True,
                            "type": "HardCap",
                            "message": f"Max tool calls ({MAX}) reached",
                        }),
                        "is_error": True,
                    })
                    continue

                # ── dispatch ──────────────────────────────────────────────────
                result, is_error = dispatch(tool_name, tool_input, run_id, step_index)
                call_count += 1

                # Serialise to JSON string BEFORE logging so is_error reflects
                # any serialisation miss. dispatch._serialise handles the known
                # DB types (date/datetime/time/Decimal/nested). This catch stops
                # an unforeseen type from propagating to the exception handler
                # and killing the entire run.
                try:
                    content_str = json.dumps(result)
                except (TypeError, ValueError) as exc:
                    content_str = json.dumps({
                        "error": True,
                        "type": "SerialiseError",
                        "message": f"Result not JSON-serialisable after _serialise: {exc}",
                    })
                    is_error = True

                # add_note: dispatch already logged the step internally; skip here.
                # All other tools: loop owns the log_agent_step call.
                #
                # Urgency policy:
                #   urgent:        is_error=True  — system error or serialise miss
                #   informational: is_error=False — all non-error results (audit trail)
                # Business-signal escalation (MOQ shortfall, declining quality, etc.)
                # is the MODEL's responsibility via add_note. 3c safety_records steps
                # have their own loop-owned urgency rules independent of this line.
                if tool_name != "add_note":
                    log_agent_step(
                        run_id=run_id,
                        step_index=step_index,
                        tool_name=tool_name,
                        tool_input=tool_input,
                        tool_output_full=(
                            result if isinstance(result, dict) else {"value": result}
                        ),
                        reasoning=turn_reasoning,
                        urgency="urgent" if is_error else "informational",
                    )

                # Always increment — one step_index slot consumed per tool_use
                # block, regardless of whether the block was add_note or a real
                # tool. The cap-log step above also increments, so cap-tripped
                # blocks that come after the first one don't consume a slot.
                step_index += 1

                # ── STEP 3c: safety_records unconditional logging ─────────────
                # After compose_session_order succeeds, iterate safety_records
                # and log loop-owned urgent steps — never at model discretion.
                # call_count is NOT incremented (these are audit rows, not
                # tool dispatches; they must not consume the 15-call cap).
                # Two independent checks per record: a record that is BOTH
                # safe=False AND has other_allergy_notes → two distinct rows.
                if (
                    tool_name == "compose_session_order"
                    and not is_error
                    and isinstance(result, dict)
                    and "safety_records" in result
                ):
                    for record in result["safety_records"]:
                        if not record.get("safe", True):
                            log_agent_step(
                                run_id=run_id,
                                step_index=step_index,
                                tool_name="dietary_safety_violation",
                                tool_input={
                                    "enrolment_id": record.get("enrolment_id"),
                                    "student_name": record.get("student_name"),
                                    "menu_item_id": record.get("menu_item_id"),
                                },
                                tool_output_full=record,
                                reasoning=(
                                    f"confirmed dietary violation: student "
                                    f"{record.get('student_name')} "
                                    f"(enrolment {record.get('enrolment_id')}) "
                                    f"assigned {record.get('meal_name')!r} "
                                    f"(item {record.get('menu_item_id')}) — "
                                    f"item tags do not cover student requirements "
                                    f"{record.get('dietary_tags')} "
                                    f"(source: {record.get('source')}). "
                                    f"Operator verification required before order email sends."
                                ),
                                urgency="urgent",
                            )
                            step_index += 1
                        if record.get("other_allergy_notes"):
                            log_agent_step(
                                run_id=run_id,
                                step_index=step_index,
                                tool_name="allergy_note_unverified",
                                tool_input={
                                    "enrolment_id": record.get("enrolment_id"),
                                    "student_name": record.get("student_name"),
                                },
                                tool_output_full=record,
                                reasoning=(
                                    f"requires human verification (free-text, not "
                                    f"machine-checkable): student "
                                    f"{record.get('student_name')} "
                                    f"(enrolment {record.get('enrolment_id')}) "
                                    f"note: {record.get('other_allergy_notes')!r}. "
                                    f"Caterer must confirm which menu items are safe."
                                ),
                                urgency="urgent",
                            )
                            step_index += 1
                        if record.get("variant") == "vegetarian_option":
                            log_agent_step(
                                run_id=run_id,
                                step_index=step_index,
                                tool_name="vo_variant_requested",
                                tool_input={
                                    "enrolment_id": record.get("enrolment_id"),
                                    "student_name": record.get("student_name"),
                                    "menu_item_id": record.get("menu_item_id"),
                                },
                                tool_output_full=record,
                                reasoning=(
                                    f"vegetarian-option preparation requested for "
                                    f"{record.get('student_name')} "
                                    f"(enrolment {record.get('enrolment_id')}) — "
                                    f"{record.get('meal_name')!r} (item {record.get('menu_item_id')}). "
                                    f"Caterer must prepare vegetarian version."
                                ),
                                urgency="informational",
                            )
                            step_index += 1

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content_str,
                    "is_error": is_error,
                })

            # Append this turn's assistant content + all tool_results before
            # either the final-summary call or the next loop iteration.
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            if cap_hit:
                # One UNCOUNTED final call — no tools so the model is forced to
                # respond with text only (it cannot recurse into more tool calls).
                # This call is not counted toward call_count and does not loop.
                final = client.messages.create(
                    model=settings.agent_model,
                    max_tokens=1024,
                    system=system_prompt,
                    messages=messages,
                )
                final_text = next(
                    (b.text for b in final.content if b.type == "text"), ""
                )
                complete_agent_run(
                    run_id, f"[CAP HIT at {call_count}/{MAX}] {final_text}"
                )
                return

    except Exception as e:
        complete_agent_run(run_id, f"[EXCEPTION: {type(e).__name__}] {e}")
        raise
