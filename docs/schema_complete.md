# Padea Operations Agent — Complete Schema Reference

**Status:** Design complete. All 13 relationships locked. Ready for implementation.
**Compiled:** 23 May 2026
**Sources:** Day 1 log (requirements and scaffold), Day 2 log (schema design relationships 1–10), Day 2 continuation (relationships 11–13).

---

## How to read this document

This is the single source-of-truth schema reference for the Padea Operations Agent v1 build. It covers every table, every column, every design decision, every operational rule, and every assumption documented during design.

The document is structured in three layers:

1. **Foundations** — design principles, conventions, and patterns that apply across the whole schema. Read this first; everything else makes more sense in this context.
2. **Relationships** — the 13 relationships designed, each presented in the format used during design: what's happening in the world, where the data lives, the decisions made and their reasoning, edge cases and trade-offs, what's out of scope for v1.
3. **References** — full table list with all columns, cross-cutting patterns, the running assumptions list (61 entries), and deferred decisions.

When implementing, work from the **References** section for column-level accuracy and from the **Relationships** section for context and reasoning. The **Foundations** section is the design philosophy — it determines how to extend the schema when v1 meets v2 cases not yet anticipated.

---

# Part 1: Foundations

## Core design principles

These principles apply throughout the schema. When choosing between alternatives, defer to these.

**Event-storing as default.** The database records *events* (orders placed, feedback submitted, prices charged, emails received, absences notified) rather than *state* (current rating, current caterer, current absence count). State that downstream code needs is derived from events on demand. This costs slightly more query complexity but pays back in auditability, history preservation, and modular agent compatibility. Override only when derivation cost becomes genuinely expensive, with documentation. Documented exceptions in this schema: `feedback_extracted_signals` (LLM-cost cache), `escalations.state` (lifecycle entity by nature), `escalations.last_observed_at` (mutable to support dedup).

**Student IDs auto-incrementing integers.** Generated at ingest. UUIDs rejected as overkill. Composed keys rejected as brittle to lifecycle changes (year level, school). This applies to all primary keys throughout the schema — every table uses an auto-incrementing integer as its primary key.

**Ingest interpretations are documented assumptions.** Any time source data is messy or implicit and ingest has to make a call, the interpretation is documented in three places: ingest code comments, schema notes file, and the memo (running assumptions list). The 61-entry assumptions list in this document is the canonical version.

**Ingest is a one-time bootstrap.** Translates messy source files into the structured schema once. Subsequent data enters through the agent, forms, or escalations — not through re-ingest. The exception is re-parsing stored raw emails when intake logic improves; this re-runs interpretation but doesn't re-ingest source files.

**Schema is general, not catering-specific.** Tables and tools designed so future agentic modules (sick-tutor replacement, attendance, hiring) can build on the same data layer without renegotiating the contract. The `agent_runs`, `decision_logs`, `escalations`, and `incoming_emails` tables are explicitly module-agnostic — they support any agent activity, not just catering.

**Plain-English first, then the database.** Schema decisions are evaluated against operational reality first. Where catering reality conflicts with database elegance, catering reality wins.

## Conventions used throughout

**Primary keys.** Auto-incrementing integers. Column name follows the pattern `<table_singular>_id` (e.g. `student_id`, `caterer_id`).

**Foreign keys.** Same naming convention as the referenced primary key. Where a table has multiple references to the same target (e.g. `sessions.expected_manager_id` and `sessions.actual_manager_id`), the column name is qualified.

**Timestamps.** Stored as ISO 8601 timestamps with timezone. Conventionally:
- `created_at` — when the row was written to the database
- `received_at` — when an event reached us (e.g. an email arriving)
- `sent_at` — when an outbound action was performed
- `<verb>_at` — generic pattern for any single lifecycle moment

**Soft-state via nullable timestamps.** Lifecycle stages tracked by nullable timestamp columns rather than a status enum where possible. Example: `walked_back_at` null = absence still stands; non-null = absence was reversed at that time. Status enums used when there are more than 2-3 meaningful states (e.g. `escalations.state`, `agent_runs.status`).

**JSON columns for flexible references.** When a row references 0-N entities of varying types, the references are stored as a JSON array of `{"type": "...", "id": ...}` objects in a column conventionally named `referenced_entities`. SQLite's JSON1 extension makes this queryable. Used in `decision_logs` and `escalations`.

**Enum-like text columns.** Text columns with documented vocabularies, validated by application code rather than database constraints. Allows the vocabulary to grow without schema migrations. Examples: `decision_logs.decision_type`, `escalations.escalation_type`, `incoming_emails.classification`.

**Forward references explicitly noted.** When a table is designed before another it depends on, the FK is declared and the dependency noted. Three forward references existed during design:
- `absences.source_email_id` → `incoming_emails.email_id` (designed in 13)
- `exclusions.source_email_id` → `incoming_emails.email_id` (designed in 13)
- `walkup_events.escalation_id` → `escalations.escalation_id` (designed in 13)
All forward references resolved in relationship 13.

**Dedup at write time, audit preserved.** When duplicates are possible (multiple parent emails about the same absence, multiple agent runs detecting the same MOQ shortfall), the schema rejects duplicate rows at write time but preserves the source events in their originating tables. Example: a second parent email about the same absence is discarded from `absences` but the email itself is still stored in `incoming_emails`.

## Operational architecture context

The schema lives inside a single shared SQLite database. The database is the source of truth. A shared Python tool layer reads and writes the database; swappable agents sit on top of the tool layer.

The first demo is the catering agent. Subsequent modules (sick tutor cover, attendance, hiring) will share the same database, the same tool layer, and the same operational tables (`agent_runs`, `decision_logs`, `escalations`, `incoming_emails`).

The agent uses Claude API tool-calling for genuinely agentic behaviour: Haiku for routing, Sonnet for harder reasoning. Agent loops are capped at ~15 tool calls per run.

The demo surface is an HTML decision-log file regenerated after each agent run. Decisions render as cards in a timeline with timestamps, tool calls, reasoning, results, flags, and colour coding. This file is generated from queries against `agent_runs` × `decision_logs`.

Email I/O in v1 is simulated via text files in `emails/incoming/` and `emails/outgoing/` directories — not real IMAP/SMTP. The `incoming_emails` table stores parsed simulated emails as if they were real.

---

# Part 2: Relationships

## Relationship 1: Schools and sessions

### Pattern
One-to-many. One school has many sessions; one session belongs to exactly one school.

### Tables

`schools`:
- `school_id` (PK)
- `name` — text
- `short_code` — text (e.g. "ISHS", "MBBC")

`sessions`:
- `session_id` (PK)
- `school_id` (FK)
- `date` — date
- `day_of_week` — text
- `session_start` — timestamp
- `session_end` — timestamp
- `dinner_start` — timestamp
- `dinner_end` — timestamp
- `building` — text
- `room` — text
- `expected_manager_id` (FK to tutors, nullable; added in relationship 7)
- `actual_manager_id` (FK to tutors, nullable; added in relationship 7)

### Decisions

Each session is its own row per occurrence — no session-template abstraction. Mid-term changes to dinner times, room assignments, or buildings are handled by the new session having different values, not by editing a template.

Building, room, and dinner times live on the session, not on the school. This handles real operational changes (a school moves Tuesday sessions from the science block to the library mid-term) without schema gymnastics.

Manager assignment lives on the session via the expected/actual manager fields. See relationship 7.

### Out of scope for v1
- Session templates or recurrence rules (each session is materialised as its own row)
- School attributes beyond name and short code (deferred until needed)

---

## Relationship 2: Students and their connection to schools

### Pattern
Students have *no direct connection to schools*. The school relationship is captured through the `enrolments` table linking students to specific sessions. School is derived through enrolments → sessions → schools.

### Tables

`students`:
- `student_id` (PK)
- `full_name` — text
- `parent_contact_info` — text or structured (TBD; parent table structure deferred)

`enrolments`:
- `enrolment_id` (PK)
- `student_id` (FK)
- `session_id` (FK)
- `start_date` — date
- `end_date` — date, nullable (null = currently enrolled)
- `year_level` — text
- `opted_out` — boolean

### Decisions

Enrolments link students to sessions, not schools. This handles "student attends Mon but not Tue" cleanly and supports cross-school cases if they ever arise.

Year level lives on the enrolment, not the student. Year level is contextual to a time period (a student moves from Year 11 to Year 12 mid-year if they repeat or accelerate). Putting it on enrolment captures the per-period truth.

Opt-out is a boolean on enrolment, not a dietary tag. It's a different kind of fact (whether the student is a catering customer, not what they can eat). Placing it on enrolment handles per-term opt-in/out cleanly — a new enrolment row can flip the opt-out status without losing history.

Default ingest rule: same name at different schools = different students unless explicit evidence to the contrary. Documented as assumption 1.

Withdrawal: set `end_date`, don't delete. Re-enrolment creates a new row.

### Out of scope for v1
- Parent table as a first-class entity (deferred; structure decided when designing feedback intake)
- Sibling relationships between students
- Historical enrolment migration tracking beyond start/end dates

---

## Relationship 3: Students and dietary tags

### Pattern
Many-to-many via pure junction table.

### Tables

`dietary_tags`:
- `tag_id` (PK)
- `tag_name` — text (controlled vocabulary)

`student_dietary_tags`:
- `student_id` (FK)
- `tag_id` (FK)
- (no other attributes)

### Decisions

Junction table over a comma-separated string column on students. Enforces the controlled vocabulary, enables structured queries ("show me every halal student at CHAC"), and supports the same vocabulary being reused for tutors.

No tag categories in v1. All dietary tags treated as hard constraints. Soft preferences and dislikes deferred.

The same `dietary_tags` table is reused for tutors via `tutor_dietary_tags` (added in relationship 7).

### Controlled vocabulary (initial set)

Descriptor tags (apply to menu items and/or students): `gluten_free`, `dairy_free`, `nut_free`, `vegetarian`, `contains_pork`.

Student-only tags: `halal`, `no_seafood`, `no_shellfish`, `no_beef`, `no_red_meat`, `no_fish`.

Note: `no_seafood` ≠ `no_shellfish`. Different restrictions; don't collapse.

### Out of scope for v1
- Soft preferences ("dislikes mushrooms")
- Tag categories or hierarchies
- Effective-date versioning on a student's dietary tags (current state only; if a student's restrictions change, the junction rows change)

---

## Relationship 4: Menu items and dietary tags

### Pattern
Many-to-many via pure junction table, with two interpretation rules baked into ingest.

### Tables

`menu_items`:
- `menu_item_id` (PK)
- `caterer_id` (FK)
- `name` — text
- `base_price` — money
- `gst_treatment` — text
- `vegetarian_swap_available` — boolean
- `effective_from` — date
- `effective_to` — date, nullable

`menu_item_dietary_tags`:
- `menu_item_id` (FK)
- `tag_id` (FK)
- (no other attributes)

### Decisions

**VO ("vegetarian option") handling.** Modelled as a `vegetarian_swap_available` boolean column on menu_items, not as a dietary tag. VO is a *capability* of the item, not a property — the item itself isn't vegetarian; the caterer can swap it for one that is. Treating VO as a tag would create safety bugs (a vegetarian student matched to a chicken dish "because it has VO available" is wrong).

Matching logic: vegetarian students match items tagged `vegetarian` OR items with `vegetarian_swap_available = TRUE`. Order lines record the menu_item_id plus an `is_vegetarian_variant` flag for unambiguous caterer communication.

**Halal handling.** Modelled via the `contains_pork` tag at ingest. Keyword detection on item names ("pork", "bacon", "ham") flags items at ingest; ambiguous cases get manual review. Halal-matching is done as an exclusion query: items NOT tagged `contains_pork`. This matches the source rule "non-pork = halal" structurally, requires less data entry than tagging halal directly, and future-proofs to other pork-avoiding frames (kosher, Adventist).

**Menu item versioning.** Items are versioned with effective dates rather than mutated. When a caterer changes their menu, the old item gets an `effective_to` date and a new row is created. Consistent with event-storing — past orders still reference the menu state that was active at order time.

### Out of scope for v1
- Item-level dietary tag versioning (versioning happens at the item level via new rows)
- Modifier/option pricing (no "add cheese for $1" mechanic)
- Multi-language menu items

---

## Relationship 5: Caterers, schools, and day-of-week

### Pattern
Many-to-many at the (caterer × school × day-of-week) level, via associative table.

### Tables

`caterers`:
- `caterer_id` (PK)
- Standard caterer fields: name, delivery_fee, gst_treatment, etc.

`caterer_school_capabilities`:
- `capability_id` (PK)
- `caterer_id` (FK)
- `school_id` (FK)
- `day_of_week` — text
- `effective_from` — date
- `effective_to` — date, nullable
- `preference_rank` — integer (lower = more preferred)

### Decisions

Capability ("can serve") stored explicitly; current assignment ("does serve") derived from most recent orders.

Day-of-week granularity. A caterer can serve School X on Mondays but not Wednesdays. Capability rows specify the day. Schools adding new session days require explicit capability confirmation — they don't silently inherit Monday capability into the new day.

`preference_rank` populated at ingest as a prior (lower = more preferred, inferred from current "currently serves" data), updated by operational signal over time.

### Operational constraints (enforced in agent logic, not data)

- One caterer can serve at most one school per day. Simplest reading; covers all conflict cases without time-window calculations.
- Capability is conditional on current operating conditions. Significant changes (enrolment growth, schedule shifts, MOQ pressure) trigger a re-confirmation escalation rather than silent continuation.

### Out of scope for v1
- Delivery distance / feasibility as first-class data
- Kitchen capacity modelling
- Caterer-specific time windows

All three captured implicitly in the capability matrix; could be modelled if operations expand.

---

## Relationship 6: Contacts and caterers

### Pattern
One-to-many. One caterer has many contacts. Contact roles modelled as four independent booleans.

### Tables

`contacts`:
- `contact_id` (PK)
- `caterer_id` (FK)
- `name` — text
- `email` — text
- `mobile` — text, nullable
- `is_order_taker` — boolean
- `is_chef` — boolean
- `is_primary_contact` — boolean
- `cc_on_orders` — boolean

### Decisions

Four orthogonal booleans rather than a single role field. Allows any combination of responsibilities and supports lifecycle changes (primary contact rotation, dual roles).

Source data preserved as-is at ingest, including apparently-swapped email/name pairings. Caterer emails are Padea-controlled placeholders Dylan uses to monitor the system during judging.

### Operational rules (enforced in agent logic)

- Every caterer must have exactly one contact with `is_primary_contact = TRUE`.
- Every caterer must have at least one contact with `is_order_taker = TRUE`.
- When primary contact changes, system escalates: "Should previous primary remain cc'd on orders?"

### Out of scope for v1
- Contact-level dietary tags (not relevant; tutors get them via `tutor_dietary_tags`)
- Contact effective dating (current state only; lifecycle changes via boolean flips)

---

## Relationship 7: Managers as a tutor role on sessions

### Pattern
Managers are not a separate population from tutors. Manager is a property of (session × tutor), not a person-type.

### Tables

`tutors`:
- `tutor_id` (PK)
- `name` — text
- `mobile` — text, nullable
- (other fields deferred to future tutor module)

`tutor_dietary_tags`:
- `tutor_id` (FK)
- `tag_id` (FK, reuses shared `dietary_tags` table)

`sessions` (extended from relationship 1):
- `expected_manager_id` (FK to tutors, nullable)
- `actual_manager_id` (FK to tutors, nullable)

`session_tutor_assignments`:
- `assignment_id` (PK)
- `session_id` (FK)
- `tutor_id` (FK)
- (no extra attributes — subject specifics rejected as too fluid to model usefully)

### Decisions

Two manager fields on sessions: expected (pre-session, used for caterer logistics) and actual (post-session, from app data, source of truth). The difference between them implicitly captures cover events — no separate `tutor_absences` table needed.

Subject and role specifics not modelled. Tutor-student-subject relationships are too fluid in reality — swaps happen, students rotate subjects, tutors help outside their formal expertise. Modelling subject assignments would create stale data faster than it would create operational value.

### Operational rules
- A tutor cannot be `actual_manager_id` or appear in `session_tutor_assignments` for two sessions on the same day.
- Pre-session communications use `expected_manager_id` for caterer-to-manager phone routing. If null, system escalates.

### Out of scope for v1
- Tutor-student-subject assignments
- Tutor performance / rating tracking (deferred to tutor module)
- Tutor availability / preferences (deferred to tutor module)
- Tutor pay / hours (out of catering scope entirely)

---

## Relationship 8: Orders and order_lines

### Pattern
Per-session orders. One order per (caterer × session). Order contains many order_lines.

### Tables

`orders`:
- `order_id` (PK)
- `caterer_id` (FK)
- `session_id` (FK)
- `status` — text (`draft` / `review_required` / `sent` / `confirmed` / `amended` / `delivered` / `cancelled`)
- `generated_at` — timestamp
- `sent_at` — timestamp, nullable
- `confirmed_at` — timestamp, nullable
- `delivered_at` — timestamp, nullable
- `total_estimated_cost` — money (Layer 2)
- `actual_paid_cost` — money, nullable (Layer 3, populated with fabricated demo data)
- `notes` — text

`order_lines`:
- `line_id` (PK)
- `order_id` (FK)
- `session_id` (FK, denormalised but kept for query convenience)
- `menu_item_id` (FK)
- `student_id` (FK, nullable — null = buffer or contingency)
- `line_purpose` — text (`student_meal` / `tutor_meal` / `contingency`)
- `is_vegetarian_variant` — boolean
- `unit_price_at_order_time` — money (Layer 2)
- `status` — text (`active` / `cancelled` / `delivered`)
- `notes` — text

`caterer_moq_rules`:
- `rule_id` (PK)
- `caterer_id` (FK)
- `menu_variety_count` — integer (e.g. 4, 5, 6)
- `min_weekly_meals` — integer

### Decisions

**Order granularity.** One order per (caterer × session), not per (caterer × week). Reasoning: enables per-session caterer rotation (rotation can happen at single-session granularity rather than swapping whole-school assignments); matches how caterers actually work (one delivery at a time); enables a clean one-order-one-delivery mental model. Trade-off accepted: more emails to caterers per week (11 vs 4 across the operation), but each email is simpler and matches their per-delivery operations.

**Order sending rule.** Orders sent 3 days before session *start* time (not dinner time). Standardised across all sessions: Mon session → Fri send. Tue session → Sat send. Wed session → Sun send. Thu session → Mon send.

**Per-student meal labelling.** Each `order_line` represents one meal for one specific student (or one buffer/contingency meal). No `quantity` column — implicitly always 1 per line. Order line records the menu_item AND the vegetarian variant flag for unambiguous caterer communication.

**Buffer meal model.** For each session order: one student_meal line per enrolled non-opted-out student + one tutor_meal line per tutor working that session + 2 contingency lines per session. Buffer meals (tutor + contingency) drawn from a "common, broadly-appealing" pool — menu items with no major exclusions, common base proteins. Dietary-restricted student meals are *always made* even on likely absence (no substitute exists). Common student meals can flex. `line_purpose` enum captures the distinction for reporting/analysis.

**Manifest organisation.** v1 organises caterer-facing manifest per-session per-student. Tutor-group organisation deferred to future tutor module (would require modelling tutor-student assignments within sessions). Physical sorting at delivery is the manager's responsibility, not the caterer's.

**Order status lifecycle.** Text field with documented vocabulary. Could be promoted to enum table later. v1 leaves it as text for flexibility.

**Cross-order weekly aggregates.** Tracked as queries over `orders` filtered by caterer + week — not as a stored table. Used for MOQ verification, cost reporting, anomaly detection.

**MOQ verification at order generation.** When generating an early-week order, agent forecasts remaining week's demand at the same caterer (using current enrolment minus known absences). If projected weekly total falls below MOQ, escalate.

**Day-of-week capability constraint.** Caterer capability is per (caterer × school × day-of-week). Schools adding new session days require new capability rows.

**Caterer rotation (v1).** Human-in-the-loop. Agent detects performance issues, identifies eligible alternatives, drafts communications (email to new caterer offering shift; email to original caterer if accepted), escalates to Dylan with full context. Dylan approves before any emails are sent.

### Out of scope for v1
- Service-agreement MOQ floors (would soften MOQ pressure but is a contract negotiation, not a system feature)
- Automated caterer rotation
- Per-tutor-group manifest organisation
- Multi-caterer single-session orders

---

## Relationship 9: Pricing (no new tables)

Pricing structure is fully accommodated by existing tables. No separate `pricing_rules` or `payments` table.

### Where pricing lives

- `menu_items.base_price` — Layer 1 (pricing rules, current state)
- `menu_items.effective_from` / `effective_to` — Layer 1 versioning (when prices change, new row created)
- `caterers.delivery_fee` and `caterers.gst_treatment` — Layer 1 delivery and tax structure
- `caterer_moq_rules` — Layer 1 MOQ rules (variety-dependent)
- `order_lines.unit_price_at_order_time` — Layer 2 (snapshot at order time)
- `orders.total_estimated_cost` — Layer 2 aggregate (sum of order_lines + delivery)
- `orders.actual_paid_cost` — Layer 3 (fabricated demo data, populated near end of build to show variance tracking)

### Payment workflow

Payment calculation derived from orders per (caterer × week) — query, not stored.

Monday EOD: agent sums committed orders per caterer, compares to MOQ rules, computes `max(committed_total, MOQ_floor)`.

If MOQ shortfall: escalation requests extras at the week's final session to make use of MOQ floor payment.

Recording actual payment events (post-banking integration) is a future concern; not modelled in v1.

---

## Relationship 10: Feedback

### Pattern
Multiple feedback row types (manager session feedback, tutor self-feedback, term surveys for parents and students) all live in one `feedback` table discriminated by `feedback_type`. Extension tables hold type-specific structured data. LLM-extracted structured signal lives in a related cache table. Walk-up student events get their own dedicated table because they drive operational escalations.

### Tables

`feedback`:
- `feedback_id` (PK)
- `feedback_type` — text enum: `manager_session`, `tutor_session`, `term_survey_parent`, `term_survey_student`
- `session_id` (FK, nullable for term surveys)
- `submitted_at` — timestamp
- `submitted_by_role` — text: `manager`, `tutor`, `parent`, `student`
- `submitter_id` — integer (tutor_id for tutor/manager feedback; pseudonymous ID for term surveys; nullable)
- `overall_rating` — integer 1-5, nullable
- `received_meal` — boolean, nullable (only meaningful for tutor feedback)
- `meal_not_received_reason` — text, nullable (free text; populated only when received_meal = FALSE)
- `comments` — text, nullable

`feedback_extracted_signals` (LLM-processed structured signal from comments, treated as a computed cache):
- `signal_id` (PK)
- `feedback_id` (FK)
- `signal_type` — text enum: `food_quality`, `dietary_handling`, `delivery`, `quantity`, `cutlery`, `menu_specific`, `walkup_mention`, `other`
- `sentiment` — text: `positive`, `negative`, `neutral`
- `referenced_menu_item_id` (FK, nullable — when comment mentions a specific dish)
- `raw_excerpt` — text (the portion of the comment this signal came from)
- `extracted_at` — timestamp
- `extracted_by` — text (model identifier for reproducibility)

`walkup_events`:
- `walkup_id` (PK)
- `feedback_id` (FK to the feedback row that captured this)
- `session_id` (FK)
- `walkup_student_name` — text (as reported by tutor)
- `resolved_student_id` (FK to students, nullable — populated by agent reconciliation)
- `resolution_status` — text enum: `pending`, `matched_to_enrolled`, `matched_to_absent`, `no_match_found`, `manually_resolved`
- `escalation_id` (FK to escalations, nullable — populated when escalation is generated)
- `created_at` — timestamp

`term_surveys` (extension table for term-survey type, avoiding NULL columns on the main feedback table):
- `term_survey_id` (PK)
- `feedback_id` (FK)
- `term_label` — text (e.g. "Term 2 2026")
- `food_taste_rating` — integer 1-5
- `food_quantity_rating` — integer 1-5
- `food_variety_rating` — integer 1-5
- `food_dietary_handling_rating` — integer 1-5
- `overall_term_rating` — integer 1-5
- (additional structured fields TBD when survey is built)

### Decisions

**Two-tier collection model plus a periodic check.**
- Manager session feedback — one row per session. Manager observes consensus among students and submits one overall rating with free-text comments capturing specific issues. Reduces response-rate degradation; trusted operationally.
- Tutor self-feedback — one row per tutor per session. Captures: did you eat your meal? if not, why? plus a 1-5 rating and free-text comment. Walk-up student names captured here when meals are redirected.
- Term survey — periodic (end-of-term) survey to parents and students separately. Mostly structured questions plus optional free text. Cross-checks manager reliability.

**Manager rates session-overall, not per-menu-item.** Per-item rating is too much work and asks the manager to decompose an inherently session-level judgement. Granularity recovered via comment processing — the agent extracts structured signals from comments, tagging mentions of specific menu items, dietary issues, delivery concerns, etc.

**Tutor feedback retains tutor_id (NOT anonymous).** Internal: identified, for outlier detection (consistent-5s rater, unusually low rater). External (aggregates shown to caterers): anonymised at presentation time. Manager training reinforces: feedback drives quality improvements; blind 5s degrade signal.

**Rating scale 1-5.** Avoids cognitive bias and mean-drift of 1-10 scales.

**Comments expected as default for all feedback, not just extremes.** Earlier "extreme rating requires comment" rule dropped. Comments are the default practice.

**Solicited only — unsolicited messages go through escalation path.** Parent complaints, caterer concerns, etc. become escalations to Dylan, not feedback rows. Keeps the feedback pipeline structured and the issue-handling pipeline separate.

**Term survey respondents pseudonymous.** Random consistent ID per respondent across terms. Honesty preserved; longitudinal tracking possible.

**Two separate term surveys (parents and students).** Parents emphasise overall satisfaction, value, communication. Students emphasise taste, quantity, variety. Distinguished by `feedback_type` enum value.

**Walk-up events as a first-class table.** Walk-up student names captured in tutor free text are post-processed into the `walkup_events` table. Drives two escalation patterns:
1. Walk-up name doesn't match any enrolled student in the school → immediate escalation.
2. Walk-up name matches a student marked absent at this session, and same student has 2+ such events → escalation: call parent.

**Comment extraction stored as a computed cache (deliberate exception to event-storing).** Justified because LLM extraction involves cost/latency, signals are queried frequently, and source comments are preserved (re-extraction possible if logic improves).

**`submission_delay_seconds` NOT stored.** Derived at query time from `submitted_at - sessions.session_end`. Cheap join; no denormalisation needed.

### Operational analyses (derived from feedback, computed by agent, not stored)

1. Caterer rolling rating — average over 4 weeks per (caterer × school), weighted by submission-timing reliability, normalised by rater baseline.
2. Rater baseline normalisation — per-manager average across historical ratings; individual ratings adjusted relative to baseline before aggregating.
3. Submission-timing reliability weighting — feedback weight decays with submission delay. Live submission gets full weight; delayed submissions weighted lower.
4. Per-tutor reliability — outlier detection on tutor ratings; tutors consistently rating 5s or rating unusually low get downweighted.
5. Per-student preference inference — derived from feedback patterns and consumption signals.
6. Rotation trigger — sustained low rolling rating for a (caterer × school × day) escalates rotation review to Dylan.
7. Walk-up escalation triggers — unmatched walk-up = immediate escalation; second false-absence walk-up for same student = parent call escalation.
8. Manager reliability cross-check — compare manager session-feedback averages to term-survey aggregates per (caterer × school); flag systematic over/under-rating.

### Out of scope for v1
- Per-meal student ratings (replaced by manager consensus model)
- Real-time sentiment analysis of unsolicited inbound messages (treated as escalations)
- Automatic rotation actions (rotation remains human-in-the-loop)

---

## Relationship 11: Absences

### What's happening in the world

A parent tells us their child isn't coming to a Padea session. Usually by email to a Padea inbox; sometimes Dylan takes a phone call or text and records it manually. The information landing on us is: which student, which session, why, and when we found out.

The "when we found out" is operationally critical. Orders go to the caterer three days before each session. Everything else flows from where the absence lands relative to that hinge.

**Before order send.** The agent factors the absence into what gets ordered. The student's meal is not made — unless the student has a dietary restriction, in which case the meal is made regardless. Two reasons: walk-up insurance (the common-meal buffer can't substitute for a restriction) and commercial guarantee (paying students must have a meal available, even after a late mind-change).

**After order send.** The meal is made and we pay for it. No amendment back to the caterer. Common meals get absorbed by tutors, walk-ups, or the manager; dietary meals likely waste. Operational cost we accept.

**Walk-backs.** Parents sometimes reverse a cancellation. Pre-send walk-backs cleanly undo the absence — the meal goes back into the order. Post-send walk-backs are covered by buffer meals (one per tutor + two contingency per session) for non-dietary students; dietary students' meals are already made, so they're covered automatically.

### Tables

`absences`:
- `absence_id` (PK)
- `student_id` (FK)
- `session_id` (FK)
- `received_at` — timestamp when we learned of the absence
- `reason` — text, nullable, free-form (parent-provided)
- `walked_back_at` — timestamp, nullable; set when the parent reverses the cancellation
- `source_email_id` (FK to `incoming_emails`, nullable; forward reference to relationship 13)
- `created_at` — timestamp

Uniqueness rule: at most one row per `(student_id, session_id)`. Database-enforced.

### Decisions

**Order construction logic.** Three days before each session, for each enrolled, non-opted-out student attached to the session: if the student has an active absence (`walked_back_at IS NULL`) for this session AND no dietary tag, skip the meal. Otherwise include it. Dietary tag overrides absence.

**Pre-send vs post-send is computed, not stored.** Comparison of `absences.received_at` against `orders.sent_at` at query time. Event-storing principle: record the event, derive the classification.

**Walk-backs as a column on the row, not a separate event log.** Walk-backs are rare and always refer to a specific prior absence. A nullable timestamp on the absence row captures everything operationally needed. Compound walk-backs (walk-back of a walk-back) handled by creating a fresh absence row, not by re-flipping the existing one.

**Duplicate intake handling.**
- Confirmation duplicate (second email saying the same thing as the first): discard. First notification wins. The duplicate email itself is preserved in `incoming_emails`; only the absence row is deduplicated.
- Walk-back arriving on an existing absence row: set `walked_back_at` to the new email's timestamp.
- Conflicting reason in a confirmation duplicate ("doctor's" then "dentist's"): keep first, discard second.
- Multi-parent notifications (separated households, both parents emailing): treated as duplicates at the absence level. Both source emails preserved in `incoming_emails`; the absence row reflects the first notification only.

**Multi-session intake.** "Sarah is away all next week" arrives as one email, expanded by the intake parser into N rows — one per affected session. The table itself never stores ranges.

### Edge cases and trade-offs

**Late walk-back of a non-dietary student.** Buffer meals absorb the walk-up. If walk-backs exceed the buffer on a given session, the agent flags it at runtime; the schema doesn't prevent it. Buffer-size tuning deferred to v2.

**Dietary meal waste from honoured cancellations.** Dietary student genuinely cancels and doesn't show — meal is made, paid for, wasted. Accepted cost in exchange for the walk-up and commercial guarantees. Rate is queryable (absences × dietary tags × walkup_events) so Dylan can monitor the trade.

**Silent no-shows.** Parent doesn't notify, child doesn't come, no walk-up surfaces it. No absence row exists. Schema can't detect this; longer-term attendance reconciliation closes the gap.

**Separated-households invisibility.** Both parents emailing independently is captured at the email level but not at the absence level. Acceptable for v1.

**Linkage to walk-ups.** A walk-up event for a student with an active absence on the same session is the "marked absent, showed up anyway" pattern. `walkup_events.resolution_status = matched_to_absent` captures it via a join. No new column on `absences`.

### Out of scope for v1
- Actual meal consumption tracking (who ate which meal)
- Silent no-show detection
- Walk-back of a walk-back as a single edit (handled by creating a new row)
- Stored "this student is absent a lot" counters (computed from the table at query time)
- SMS-to-inbox automation; phone/text intake remains manual

---

## Relationship 12: Exclusions

### What's happening in the world

A session is normally going ahead. Then something happens that means some or all of the students who'd normally be there aren't going to be — but it's not an individual-student decision. It's a session-level event imposed from outside the catering pipeline, usually by the school.

Three shapes in practice:

**Whole-session cancellation.** Public holiday, pupil-free day, weather event, burst pipe, power out. Nobody attends. Session itself is cancelled.

**Year-level cancellation within a session that still runs.** The CHAC case: Year 12s have an exam block or Year 10s are on camp, but Year 11 still has Padea on Tuesday afternoon. The session runs; a slice of the enrolled cohort is excluded for a defined reason. Schools typically send these as bloc statements ("Year 12s are out") rather than student lists.

**Subject-specific or other partial exclusions.** Out of scope for relationship 12. Handled as individual absences when they happen.

Operational consequences depend on type and timing:

**Whole-session cancellation (pre-send).** No order is constructed at all. No meals made, including for dietary students — the school is closed, nobody is physically there to receive food. This is the one place the dietary-always-made rule does not apply.

**Whole-session cancellation (post-send).** Order is already with the caterer; meals are made; we pay. The exclusion row still gets written, so Dylan can see patterns (late school cancellations clustering at a particular school). Schema doesn't try to undo the order.

**Partial exclusion (pre-send).** Year level out, session still runs. The agent factors the exclusion into order construction: those students' common meals are not made. Dietary students within the excluded cohort still get meals made under the existing dietary-override rule. Plus a 10% attendance buffer — ten percent of the excluded cohort, rounded up to the nearest whole meal, added as extra common meals. This handles the social reality that some students skip the camp and show up to tutoring anyway.

**Partial exclusion (post-send).** Recorded, no caterer amendment. Standard order buffers absorb any walk-ups; the 10% rule is meaningful only pre-send because there's nothing to change post-send.

### Tables

`exclusions`:
- `exclusion_id` (PK)
- `session_id` (FK)
- `scope` — text enum: `whole_session`, `year_level` (`student_group` deferred to when tutor groups exist)
- `scope_value` — text, nullable. Null for `whole_session`. For `year_level`, the year level affected ("Year 10", "Year 12").
- `reason` — text, nullable but expected. Free-form.
- `received_at` — timestamp
- `source_email_id` (FK to `incoming_emails`, nullable; forward reference to relationship 13)
- `created_at` — timestamp

Uniqueness rule: at most one row per `(session_id, scope, scope_value)`. Confirmation duplicates discarded; first-wins. Source emails preserved in `incoming_emails`.

### Decisions

**Order construction logic.** For each session being ordered for, the agent applies filters in this sequence:

1. **Whole-session check.** Active `whole_session` exclusion for this session? If yes, no order constructed. Stop.
2. **Per-student cohort check.** For each enrolled, non-opted-out student: covered by an active `year_level` exclusion? If yes and no dietary tag, skip the meal. If yes and dietary tag present, include the meal.
3. **Per-student absence check.** Same as relationship 11.
4. **10% attendance buffer.** For each active `year_level` exclusion on this session, count the excluded students (those matching the year level in their enrolment). Add `ceil(0.10 × excluded_count)` extra common meals to the order as buffer. This is on top of the standard buffer (one per tutor + two contingency per session).

Filters compose cleanly: a student excluded by year level *and* individually absent is filtered either way; no double-counting because we're filtering inclusions, not accumulating reasons.

**Pre-send vs post-send is computed, not stored.** Same pattern as absences: `exclusions.received_at` compared against `orders.sent_at` at query time.

**No walk-back mechanic.** Exclusions are imposed by the school and don't typically reverse. If a school's plans change, the operational handling is manual: delete or supersede the relevant exclusion row. Rare enough that no `walked_back_at` or `superseded_at` column is justified.

**Multi-session intake.** "Year 12 has exams all next week" arrives as one email, expanded by the intake parser into N rows — one per affected session. Same pattern as absences.

**10% attendance buffer is hard-coded.** The rate lives in the agent's order-construction logic, not as a configurable column on schools or caterers. Revisit in v2 if operational data shows the rate varies meaningfully by school or event type.

### Edge cases and trade-offs

**Whole-session cancellation: dietary students lose meal access.** The one case the dietary-always-made rule doesn't fire. Justified because the session is physically not running — nobody is there to receive food, including dietary students. If a dietary student turned up at a cancelled session (e.g. didn't get the message), they'd find a locked school regardless.

**10% rounding up means small cohorts get at least one buffer meal.** 10% of 8 Year 12s = 0.8 → 1 buffer meal. 10% of 30 Year 10s = 3 buffer meals. A cohort of zero genuinely excluded students (edge case: exclusion row exists but no students match the year level) produces zero extra buffer. The round-up applies only to non-zero counts.

**The 10% is a guess, not a measurement.** We have no operational data yet on actual exclusion-day turnout. The rate is sized to social reality (a couple of kids always skip camp / aren't sick on exam-block day / want to come anyway), not to evidence. v2 with real consumption data should refine it.

**Partial exclusions inside a year level.** "Half of Year 10 is on camp" — handled by individual absences, not by year-level exclusion. Schools sending bloc statements is the dominant pattern, so this case is rarer; when it happens, the school sends a list and the list becomes N absence rows.

**Wrong year-level exclusion in the wild.** Agent does not actively detect this. If multiple students from an excluded cohort appear as walk-ups, they get recorded normally and Dylan can spot the pattern manually if it matters. No detection logic in v1.

**Subject-specific camps and tutor groups out of scope.** Subject camps modelled as individual absences. Tutor camps don't happen. `student_group` scope deferred until tutor groups are first-class.

**Source channels.** School admin email is dominant. Dylan reading a school newsletter and noting it manually goes through the same intake (`source_email_id` null). Automated school-calendar sync deferred to v2.

**Late whole-session cancellation cost.** Post-send whole-session cancellation = full order paid for, full waste. Recorded as an exclusion row so the pattern is queryable. Commercial action (negotiating with the school about late cancellations) is operational, not schema.

### Out of scope for v1
- Automated school-calendar sync
- Term-break and holiday calendars as first-class data (a public-holiday Tuesday is a whole-session exclusion row entered manually)
- Predictive exclusion (agent inferring pupil-free days)
- Partial-cohort exclusions inside a year level (handled by absences)
- Walk-back / superseding of exclusions (manual fix when it happens)
- First-class group exclusions (deferred until tutor groups are modelled)
- Subject-specific camps as exclusions (modelled as individual absences)
- Per-school configuration of the attendance-buffer rate (hard-coded 10% in v1)
- Wrong-exclusion detection from walk-up patterns

---

## Relationship 13: Agent runs, escalations, decision logs

### What's happening in the world

The agent runs operationally — on a schedule plus on triggers. A run is a single invocation: wake up, read the database, decide what needs doing, take actions, finish. Each run produces three kinds of recorded output, plus a fourth piece that supports them all:

**Runs themselves.** The fact and metadata of each invocation — when, why, what it intended, whether it succeeded. Immutable event log.

**Decisions made inside runs.** The reasoning trail. Tool calls the agent made, branch decisions where it chose between alternatives, rule applications, escalation triggers, errors. Demo surface — Dylan reads this to understand what the agent was thinking.

**Escalations.** Items the agent hands off to Dylan because it can't or shouldn't act alone. MOQ shortfalls, dietary conflicts, walk-up mismatches, rotation approvals, parse failures, observed patterns. Has lifecycle: open → resolved / dismissed / auto-resolved.

**Incoming emails.** The input layer feeding all of the above. Parent absence notifications, school exclusion notices, caterer replies, Dylan's escalation resolutions — all land here first as raw records, get classified, get processed into operational events.

Three immutable event logs (`agent_runs`, `decision_logs`, `incoming_emails`) plus one lifecycle entity (`escalations`).

### Tables

#### `incoming_emails` — every email arriving at any watched Padea inbox

- `email_id` (PK)
- `message_id` — text, unique. The email's `Message-ID` header; dedup primitive.
- `received_at` — when the email landed (from headers)
- `fetched_at` — when our system pulled it
- `from_address`, `from_name`, `to_address`, `subject` — standard email metadata
- `body_plain`, `body_html` — both stored; multipart emails are the norm
- `raw_headers` — full headers block for re-parsing
- `attachments_info` — JSON, attachment metadata only (no binary in v1)
- `classification` — enum, nullable: `absence_notification`, `exclusion_notification`, `caterer_reply`, `escalation_resolution`, `unclassified`. Set by first-pass classifier.
- `classified_at` — timestamp, nullable
- `processing_status` — enum: `unprocessed`, `processed`, `failed`, `human_review`
- `processed_at` — timestamp, nullable
- `created_at` — timestamp

Uniqueness on `message_id`. Resolves the forward references from `absences.source_email_id` and `exclusions.source_email_id`.

#### `agent_runs` — one row per agent invocation

- `run_id` (PK)
- `trigger_type` — enum: `scheduled`, `event`, `manual`
- `trigger_detail` — text (schedule name, event description, or operator note)
- `trigger_context` — JSON (structured trigger info, including triggering email_id if event-driven)
- `intended_purpose` — text label (e.g. `generate_orders`, `process_incoming_emails`, `resolve_escalations`)
- `started_at`, `finished_at` (nullable)
- `status` — enum: `running`, `completed`, `completed_with_errors`, `crashed`, `aborted`
- `agent_version` — text (git commit short hash or semver)
- `model_identifiers` — JSON (which LLMs were used for what)
- `summary` — text, nullable, agent-written prose at run-end
- `error_summary` — text, nullable
- `created_at`

Crashed-run detection via next-run cleanup: when a new run starts, it marks any `running` rows older than 30 minutes as `crashed`.

#### `escalations` — items handed to Dylan, with lifecycle

- `escalation_id` (PK)
- `created_run_id` — FK to `agent_runs`
- `escalation_type` — enum (`moq_shortfall`, `dietary_conflict`, `unmatched_walkup`, `repeat_false_absence`, `caterer_rotation`, `parse_failure`, `data_conflict`, `repeat_post_send_cancellation`, `low_feedback_rotation_review`, `other`)
- `severity` — enum: `info`, `warn`, `urgent`. Agent-chosen per instance.
- `resolution_mode` — enum: `auto` or `human`
- `match_key` — text, nullable. Agent-computed dedup primitive (e.g. `moq_shortfall:caterer_5:week_2026-05-25`).
- `title` — text, short summary
- `body` — text, markdown, agent's full analysis (includes drafted action content for approval-shaped escalations)
- `referenced_entities` — JSON, list of `{type, id}` pairs
- `triggering_decision_ids` — JSON, nullable, list of decision_log IDs that led to this
- `state` — enum: `open`, `resolved`, `dismissed`, `auto_resolved`
- `created_at`, `last_observed_at`, `resolved_at` (nullable)
- `resolved_by` — text (v1: "Dylan via email" or run_id for auto-resolved)
- `resolution_note` — text, nullable

Dedup: before creating, agent queries open escalations by `(escalation_type, match_key)`; if found, updates `last_observed_at` instead of inserting.

Auto-resolution: each run, agent re-evaluates `open` escalations with `resolution_mode = auto`; closes any whose trigger condition is gone.

Human resolution: agent sends notification email at creation with `[PADEA-ESC-{id}]` token in subject; Dylan replies with `resolved` or `dismissed`; the reply lands in `incoming_emails`, gets classified as `escalation_resolution`, parsed, and used to close the row. Fuzzy matching on subject+sender+timestamp as fallback if the token is stripped.

Resolves the forward reference from `walkup_events.escalation_id`.

#### `decision_logs` — the reasoning trail, demo surface

- `decision_id` (PK)
- `run_id` — FK to `agent_runs`
- `decision_type` — enum: `tool_call`, `branch_decision`, `rule_application`, `escalation_trigger`, `error`
- `parent_decision_id` — FK to `decision_logs`, nullable (tree structure for nested decisions)
- `sequence_in_run` — integer, monotonic within a run
- `started_at`, `finished_at` (nullable)
- `title` — text, short label
- `summary` — text, nullable
- `reasoning` — text, nullable, markdown (populated for branch decisions; null for routine tool calls)
- `alternatives_considered` — JSON, nullable (for branch decisions)
- `chosen_option` — text, nullable
- `rule_applied` — text, nullable (for rule_application rows)
- `referenced_entities` — JSON
- `tool_name`, `tool_input` (JSON), `tool_output_summary` — for tool_call rows
- `status` — enum: `success`, `warning`, `error`, `in_progress`
- `flags` — JSON, structured flag objects
- `created_at`

Demo UI defaults to filtering `decision_type IN ('branch_decision', 'escalation_trigger', 'error')`; `tool_call` and `rule_application` hidden but expandable.

### Decisions (combined)

**Three event logs and one lifecycle entity.** Runs, decisions, and emails are immutable once written. Only escalations have mutable state.

**Run is the parent.** Every decision and escalation belongs to one run. The agent reads `agent_runs` to know what work has been done; writes to `decision_logs` as it goes; reads/writes `escalations` for hand-off and resolution checking.

**Decisions form a tree, not a flat list.** `parent_decision_id` lets nested reasoning (e.g. "pick a caterer" with sub-decisions for each candidate) render correctly in the demo. No depth cap.

**Tool calls and branch decisions in one table.** Same table, distinguished by `decision_type`. Demo filters by type. Single chronological trail per run; one query covers both views.

**Escalation dedup via match_key.** Text key with code-side convention per type. Open-escalation check before insert; same-key resolved escalations don't block new ones.

**Resolution model is hybrid.** `auto` escalations close themselves when their condition is gone; `human` escalations close when Dylan replies to the notification email. Identified by `[PADEA-ESC-{id}]` token in subject, with fuzzy matching fallback.

**Severity is per-instance, agent-chosen.** Same `escalation_type` can be `info` or `urgent` depending on magnitude.

**Approval-shaped escalations use `open` state.** Caterer rotations and similar items where Dylan must approve a drafted action don't need a special `awaiting_approval` state; the body carries the drafted content, and Dylan's reply (`approved`/`dismissed`) closes the row.

**Reasoning quality is a prompting concern, not a schema concern.** The `reasoning` field exists; the agent's prompts have to populate it with substance for the demo to be persuasive.

**Tool outputs stored as summaries only.** Full output preservation deferred. PII in `tool_input` stored verbatim in v1; redaction deferred.

**Crashed-run cleanup via next-run check.** No watchdog process. 30-minute staleness threshold.

**Outgoing emails not in this cluster.** Designed with the agent's action layer, not the data layer.

**`agent_version` and `model_identifiers` per run.** Enables retrospective correlation between behaviour and code/model changes.

### Operational rules

- Each agent invocation creates one `agent_runs` row at start, finalises status at end (or gets reclassified as `crashed` by the next run).
- Tool calls are logged automatically via the wrapper layer; branch decisions and rule applications logged explicitly by the agent.
- Decision rows reference each other via `parent_decision_id` for tree-structured reasoning; otherwise flat at top level.
- Escalations check for open dedup matches before creating new rows.
- Each run re-evaluates open `auto`-resolution escalations and closes any whose conditions are gone.
- Incoming emails get classified before processing; classification drives downstream parsing.
- Email replies to escalation notifications are classified as `escalation_resolution` and parsed for closure keywords.
- All escalations carry referenced entities as JSON for entity-pivoted queries.
- The walkup-events linkage runs both ways: walkup creates escalation, then writes the new `escalation_id` back to the walkup row.

### Out of scope for v1
- Watchdog process (next-run cleanup instead)
- Re-notification cadence for stale-open escalations
- User table; `resolved_by` is text
- Snooze / defer / assign escalation states
- Threaded discussion within an escalation
- SLA tracking
- Full tool-output storage
- PII redaction in tool inputs
- Decision-log retention/pruning
- Outgoing email storage in this cluster
- Email thread reconstruction
- Attachment binary storage
- Bulk escalation operations
- Cross-run decision lineage as first-class (queryable via referenced_entities pivoting)
- Confidence scores as separate columns (handled via flags)
- Full-text search indexing on reasoning

---

# Part 3: References

## Complete table list

The schema contains 26 tables. They are grouped here by functional area.

### Identity and structure (5 tables)
- `schools` — schools served
- `sessions` — per-occurrence session records
- `students` — student identities
- `enrolments` — student-to-session assignments with year level and opt-out
- `tutors` — tutor identities

### Dietary modelling (3 tables)
- `dietary_tags` — controlled vocabulary
- `student_dietary_tags` — junction
- `tutor_dietary_tags` — junction (reuses `dietary_tags`)

### Catering supply side (5 tables)
- `caterers` — caterer identities
- `contacts` — caterer contacts with role booleans
- `caterer_school_capabilities` — (caterer × school × day-of-week) capability matrix
- `menu_items` — versioned menu items with pricing
- `menu_item_dietary_tags` — junction
- `caterer_moq_rules` — variety-dependent MOQ rules

### Session execution (1 table)
- `session_tutor_assignments` — junction for tutors working sessions

### Orders (2 tables)
- `orders` — one per (caterer × session)
- `order_lines` — per-meal line items

### Feedback and consumption signals (4 tables)
- `feedback` — discriminated by `feedback_type` covering manager, tutor, and term survey rows
- `feedback_extracted_signals` — LLM-extracted structured signals from comments
- `walkup_events` — first-class walk-up student records
- `term_surveys` — extension table for term-survey-specific fields

### Operational events (4 tables)
- `absences` — per-(student × session) absence records with walk-back
- `exclusions` — per-session cohort exclusions
- `agent_runs` — per-invocation operational records
- `decision_logs` — reasoning trail, demo surface

### Lifecycle entities (1 table)
- `escalations` — open items handed to Dylan with full lifecycle

### Input layer (1 table)
- `incoming_emails` — raw email storage with classification and processing status

## All forward references and how they resolved

| Source | Target | Resolved in |
|---|---|---|
| `absences.source_email_id` | `incoming_emails.email_id` | Relationship 13 |
| `exclusions.source_email_id` | `incoming_emails.email_id` | Relationship 13 |
| `walkup_events.escalation_id` | `escalations.escalation_id` | Relationship 13 |

All forward references resolved. No dangling references remain.

## Cross-cutting patterns and conventions

### Dedup at the schema level

Tables that may receive multiple notifications about the same logical event enforce dedup via a database-level uniqueness rule:

| Table | Uniqueness rule | Source events preserved where |
|---|---|---|
| `absences` | `(student_id, session_id)` | `incoming_emails` |
| `exclusions` | `(session_id, scope, scope_value)` | `incoming_emails` |
| `incoming_emails` | `message_id` | (terminal; no upstream layer) |
| `escalations` | None at DB level; agent-side dedup via `match_key` | `agent_runs`, `decision_logs` |

The pattern: dedup at the operational layer where it matters, preserve the source event layer for audit.

### Event-storing exceptions documented

The schema is event-storing by default. Documented exceptions:

1. `feedback_extracted_signals` — LLM-extracted signals stored as a computed cache. Justified by LLM cost/latency and high query frequency. Source comments preserved for re-extraction.
2. `escalations.state` — escalation lifecycle requires mutable state by nature. Not an exception so much as a different table category.
3. `escalations.last_observed_at` — mutable to support runtime dedup of recurring conditions.
4. `walkup_events.escalation_id` — written back to the walkup row after escalation creation. One-time write, not ongoing mutation.

### Soft-state via nullable timestamps

Lifecycle moments tracked by nullable timestamps where there are 1-2 stages:
- `absences.walked_back_at` (null = standing; non-null = reversed)
- `enrolments.end_date` (null = current; non-null = withdrawn)
- `menu_items.effective_to` (null = current; non-null = retired)
- `caterer_school_capabilities.effective_to` (null = current; non-null = retired)
- `agent_runs.finished_at` (null = in progress or crashed; non-null = ended cleanly)
- `incoming_emails.classified_at` / `processed_at` (null = pending; non-null = done)
- `escalations.resolved_at` (null = open; non-null = closed)

### JSON columns and their uses

| Column | Shape | Purpose |
|---|---|---|
| `agent_runs.trigger_context` | structured trigger info | Flexible trigger metadata |
| `agent_runs.model_identifiers` | `{role: model_string}` map | Reproducibility |
| `escalations.referenced_entities` | `[{type, id}, ...]` | Entity-pivoted queries |
| `escalations.triggering_decision_ids` | `[id, ...]` | Decision → escalation linkage |
| `decision_logs.alternatives_considered` | per-decision shape | Branch decision audit trail |
| `decision_logs.referenced_entities` | `[{type, id}, ...]` | Entity-pivoted queries |
| `decision_logs.tool_input` | tool-specific | Reproducibility of tool calls |
| `decision_logs.flags` | `[{type, note}, ...]` | Demo UI flag rendering |
| `incoming_emails.attachments_info` | `[{filename, mime, size}, ...]` | Attachment metadata (no binaries v1) |

SQLite's JSON1 extension makes these queryable where needed.

### Enum-like text columns

Documented vocabularies, not database-enforced enums. Allows growth without migration.

| Column | Vocabulary |
|---|---|
| `enrolments.year_level` | "Year 7" through "Year 12" |
| `dietary_tags.tag_name` | See relationship 3 |
| `caterer_school_capabilities.day_of_week` | Mon, Tue, Wed, Thu, Fri (Sat/Sun if needed) |
| `orders.status` | draft / review_required / sent / confirmed / amended / delivered / cancelled |
| `order_lines.line_purpose` | student_meal / tutor_meal / contingency |
| `order_lines.status` | active / cancelled / delivered |
| `feedback.feedback_type` | manager_session / tutor_session / term_survey_parent / term_survey_student |
| `feedback.submitted_by_role` | manager / tutor / parent / student |
| `feedback_extracted_signals.signal_type` | food_quality / dietary_handling / delivery / quantity / cutlery / menu_specific / walkup_mention / other |
| `feedback_extracted_signals.sentiment` | positive / negative / neutral |
| `walkup_events.resolution_status` | pending / matched_to_enrolled / matched_to_absent / no_match_found / manually_resolved |
| `exclusions.scope` | whole_session / year_level (student_group deferred) |
| `incoming_emails.classification` | absence_notification / exclusion_notification / caterer_reply / escalation_resolution / unclassified |
| `incoming_emails.processing_status` | unprocessed / processed / failed / human_review |
| `agent_runs.trigger_type` | scheduled / event / manual |
| `agent_runs.status` | running / completed / completed_with_errors / crashed / aborted |
| `escalations.escalation_type` | moq_shortfall / dietary_conflict / unmatched_walkup / repeat_false_absence / caterer_rotation / parse_failure / data_conflict / repeat_post_send_cancellation / low_feedback_rotation_review / other |
| `escalations.severity` | info / warn / urgent |
| `escalations.resolution_mode` | auto / human |
| `escalations.state` | open / resolved / dismissed / auto_resolved |
| `decision_logs.decision_type` | tool_call / branch_decision / rule_application / escalation_trigger / error |
| `decision_logs.status` | success / warning / error / in_progress |

### The order-construction pipeline

Order construction is a single event at T-3 days before each session. The agent assembles the order from current state at that exact moment. The pipeline:

1. **Whole-session exclusion check.** If any `whole_session` exclusion is active for this session, no order is constructed. Stop.
2. **Per-student inclusion loop.** For each enrolled, non-opted-out student attached to the session:
   - Is the student covered by an active `year_level` exclusion?
     - If yes and no dietary tag: skip the meal.
     - If yes and dietary tag: include the meal (override).
   - Is the student covered by an active absence (`walked_back_at IS NULL`)?
     - If yes and no dietary tag: skip the meal.
     - If yes and dietary tag: include the meal (override).
   - Otherwise: include the meal.
3. **Tutor meal addition.** Add one `tutor_meal` line per tutor in `session_tutor_assignments` for this session.
4. **Standard buffer addition.** Add 2 `contingency` lines per session.
5. **Exclusion buffer addition.** For each active `year_level` exclusion: count excluded students, add `ceil(0.10 × excluded_count)` extra `contingency` lines.
6. **MOQ verification.** Sum committed orders for this caterer this week. If projected weekly total falls below MOQ floor for the caterer's variety count, raise an escalation.
7. **Order persistence.** Write the order row, write all order_lines, set `orders.sent_at`, dispatch to caterer.

Absences and exclusions arriving after step 7 are recorded but do not amend the order.

### Demo surface generation

The HTML decision-log file regenerated after each agent run is the main demo surface. It's generated from:

- Primary query: `agent_runs` ordered descending by `started_at`, joined with `decision_logs` ordered by `sequence_in_run`.
- Default filter: `decision_logs.decision_type IN ('branch_decision', 'escalation_trigger', 'error')`. `tool_call` and `rule_application` rows hidden but expandable.
- Cards rendered per decision: timestamp, title, type, reasoning, alternatives, chosen option, status colour, flags, referenced entities.
- Escalations rendered separately as an at-a-glance list of currently open items, with their `state`, `severity` colour-coding, and `body` content.

The decision-log file is the primary tool for trust-building and debugging. Failures render as "look how the agent considered options and escalated" rather than "the demo broke."

## Running assumptions list (complete, all 61 entries)

These are the documented interpretive decisions made during ingest and design. Each is an assumption the schema/agent operates under and could be revisited if operational reality contradicts it.

1. Same name at different schools = different students unless evidence to contrary.
2. Non-pork menu items are halal (from source PDF rule).
3. VO ("vegetarian option") is a capability, not a property of the menu item.
4. Preference rank baseline inferred from current "currently serves" data; updated by operational signal.
5. One caterer can serve at most one school per day.
6. Caterer capability is conditional on current operating conditions; significant changes trigger re-confirmation.
7. Capability matrix encodes (without separately modelling) distance feasibility, kitchen capacity, time-window constraints.
8. Email addresses are operational; Padea-controlled placeholders during judging.
9. Caterer contact email/name pairings preserved as given. (Earlier interpretation about Dylan vs James swap superseded — these are placeholder addresses.)
10. Contact roles modelled as four independent booleans (order_taker, chef, primary, cc).
11. Managers are tutors with a per-session manager role, not a separate population.
12. Tutor table in v1 minimal; expansion deferred to tutor module.
13. Default manager patterns not modelled explicitly; emerge from historical session_tutor_assignments.
14. Session manager captured as expected + actual fields; difference captures cover events.
15. Orders generated per-session, sent 3 days before session start. Weekly aggregates derived from queries.
15a. Agent forecasts remaining week's demand at early-week order generation for MOQ verification.
16. Buffer meals drawn from "common, broadly-appealing" pool. One per tutor + 2 contingency per session.
17. Dietary-restricted student meals are always made (no substitute exists). Common meals can flex.
18. v1 manifest organised by session-and-student; tutor-group organisation deferred.
19. Current Thursday-as-order-day operation demonstrates 3-day prep capability for all caterers.
20. Caterer capability modelled at (caterer × school × day-of-week). Schools adding session days require new capability rows.
21. Caterer rotation in v1 is human-in-the-loop. Agent surfaces and drafts; Dylan approves and triggers.
22. MOQ treated as hard weekly contract minimum in v1. Service agreement with MOQ floor would soften this and reduce escalations.
23. "3 days before" means 3 days before session start time, not dinner time.
24. Payment calculation derived from orders per (caterer × week) — query, not stored table. Actual payment recording deferred to v2 with real banking integration.
25. MOQ rules modelled as separate `caterer_moq_rules` table with (caterer × menu_variety_count) granularity.
26. Feedback collected via two-tier model (manager per-session + tutor self) plus end-of-term parent/student surveys. Not per-meal student ratings.
27. Manager rates session-overall with free-text comments; per-item granularity recovered via LLM extraction of structured signals from comments.
28. Tutor feedback identified (not anonymous) for outlier detection; aggregates anonymised at presentation.
29. Rating scale is 1-5 throughout. Comments expected as default for all feedback.
30. Solicited feedback only enters the feedback pipeline. Unsolicited messages (parent complaints, caterer concerns) become escalations.
31. Term survey respondents pseudonymous (random consistent ID per respondent across terms).
32. Walk-up student events captured as a first-class table; drive immediate escalation when unmatched, parent-call escalation after 2 false-absence walkups.
33. Comment-extracted signals stored as a computed cache (deliberate exception to event-storing default; justified by LLM cost and query frequency).
34. Caterer rolling rating computation includes rater-baseline normalisation and submission-timing reliability weighting — both done at query time, no stored calibration columns.
35. Dietary-restricted student meals are made even on pre-send cancellation (walk-up insurance + commercial guarantee).
36. All paying students have a meal available regardless of cancellation timing. Late walk-back of non-dietary students covered by buffer meals.
37. Absence intake primarily email-driven; non-email sources permitted via nullable `source_email_id`.
38. Walk-backs modelled as nullable timestamp on the absence row. Walk-back-of-walk-back creates a new absence row rather than re-flipping the existing one.
39. Pre-send vs post-send window derived from `received_at` vs `orders.sent_at` at query time, not stored.
40. Order construction is a single event at T-3 days; `order_lines` are never mutated by subsequent absences. Pre-send "cancellation" = omission at construction, not amendment.
41. One absence row per (student, session), database-enforced. Confirmation duplicates discarded; conflicting reasons resolved as first-wins. Source emails preserved in `incoming_emails` regardless of dedup outcome.
42. Whole-session cancellations override the dietary-always-made rule: no meals constructed at all. The school being physically closed makes the walk-up-insurance and commercial-guarantee reasoning inapplicable.
43. Partial exclusions (year level) trigger a 10% attendance buffer of extra common meals — ten percent of the excluded cohort, rounded up to the nearest whole meal, added on top of the standard buffer. Sized to the social reality that some excluded students attend anyway.
44. The 10% attendance-buffer rate is hard-coded in the agent's order-construction logic. Per-school or per-event-type configuration deferred to v2 pending actual consumption data.
45. Exclusions arrive primarily as year-level bloc statements from school admin. Individual-student lists (when schools send them) are processed as absences instead.
46. Subject-specific camps and similar partial-cohort exclusions are modelled as individual absences, not exclusions. Exclusions table is reserved for whole-session and year-level cases in v1.
47. Exclusions have no walk-back mechanic. Reversed school decisions are handled manually by deleting or superseding the exclusion row.
48. One exclusion row per (session, scope, scope_value), database-enforced. Confirmation duplicates discarded; source emails preserved in `incoming_emails`.
49. Whole-session cancellations arriving post-send are still recorded as exclusion rows. The order is not undone; the row exists for audit and pattern detection.
50. Agent runs are discrete invocations; each gets one `agent_runs` row. Crashed runs detected by next-run cleanup with 30-minute staleness threshold.
51. Tool calls and branch decisions live in the same `decision_logs` table, distinguished by `decision_type`. Demo UI defaults to hiding routine tool calls and rule applications.
52. Decisions form a tree via `parent_decision_id`; no depth cap.
53. Escalations use hybrid resolution: `auto` closes when trigger condition gone; `human` closes when Dylan replies to notification email with closure keyword.
54. Escalation dedup via agent-computed `match_key` with code-side conventions per escalation_type. Same-key resolved escalations don't block new ones.
55. Severity is per-instance, agent-chosen. Same escalation_type can range info to urgent based on context.
56. Approval-shaped escalations use `open` state; body carries drafted action; Dylan's reply (`approved`/`dismissed`) closes the row.
57. Reply parsing for escalation closure uses `[PADEA-ESC-{id}]` subject token with fuzzy matching as fallback.
58. Incoming emails stored with raw headers + plain + html bodies. Attachments metadata-only in v1.
59. Tool outputs stored as summaries only; full outputs and PII redaction deferred.
60. `agent_version` and `model_identifiers` recorded per run for retrospective correlation.
61. Outgoing emails not part of this cluster; designed with the action layer.

## Open / deferred decisions

Items raised during design but not finalised. None block v1 implementation; each is a known gap or v2 lever.

- **Parent table structure.** Kept in scope as a feedback channel; structure deferred until feedback intake from parents is actually built. v1 stores parent contact as text on `students.parent_contact_info`.
- **Schools attributes beyond name and short code.** Deferred until needed. v1 carries no school-level operational data beyond identity.
- **Layer 3 actual payment recording.** Deferred to v2 with banking integration. v1 uses `orders.actual_paid_cost` as a fabricated demo data field.
- **Buffer-size auto-tuning based on consumption data.** Deferred to v2. v1 uses fixed buffers (1 tutor + 2 contingency + 10% exclusion attendance).
- **Caterer day-of-week constraint validation logic.** TBD when designing agent's order-generation logic in detail. The constraint exists in the schema (`caterer_school_capabilities.day_of_week`); enforcement specifics during order construction TBD.
- **Tutor groups as first-class entities.** Deferred. The `exclusions.scope` enum includes `student_group` for future use, but no tutor group table exists.
- **Outgoing emails table.** Designed with the action layer, not the data layer. v1 will need this table but its design is part of action-layer work.
- **Re-notification cadence for stale-open escalations.** Out of scope for v1. Escalations sit open until Dylan replies.
- **Users / operator table.** v1 has no user table; `escalations.resolved_by` is text. v2 should introduce this.
- **Attachment binary storage.** Metadata-only in v1. v2 needs a storage approach plus PII handling.
- **PII redaction in `decision_logs.tool_input`.** v1 stores verbatim. v2 should add field-level redaction.
- **Decision-log retention policies.** v1 keeps everything forever. v2 may want pruning.

## Glossary

**Agent run.** A single invocation of the operations agent. Recorded as one row in `agent_runs`.

**Buffer meal.** A meal made beyond the count of confirmed-attending students, to absorb walk-ups, walk-backs, or attendance surprises. v1 buffers: 1 per tutor + 2 contingency per session + 10% of excluded cohort for partial exclusions.

**Caterer rotation.** Process of changing which caterer serves a given (school, day-of-week). v1: human-in-the-loop with agent drafts.

**Decision (in decision_logs).** Any logged action by the agent during a run. Includes tool calls, branch decisions, rule applications, escalation triggers, and errors.

**Event-storing.** Schema design principle: record events, derive state. The default approach in this schema.

**Escalation.** An item handed by the agent to Dylan for human judgement or action. Has lifecycle (open → resolved / dismissed / auto-resolved).

**Foreign key.** A column whose value matches a primary key in another table, establishing a reference.

**Forward reference.** A foreign key declared before the table it points to has been designed. Three forward references existed during design; all resolved in relationship 13.

**Hinge moment.** Operationally critical timing boundary. The dominant hinge in catering operations is `orders.sent_at` (T-3 days before session); absences and exclusions are classified by their position relative to this hinge.

**Junction table.** A table whose primary purpose is to link two other tables in a many-to-many relationship. Example: `student_dietary_tags`.

**Manager.** A tutor with the per-session role of session manager. Not a separate population — captured by `sessions.expected_manager_id` and `sessions.actual_manager_id`.

**Match key (escalations).** Agent-computed text key used to dedup recurring escalation conditions. Example: `moq_shortfall:caterer_5:week_2026-05-25`.

**MOQ.** Minimum Order Quantity. Caterer-specific weekly minimum below which the caterer charges a floor regardless of actual order. v1 treats MOQ as a hard contract minimum.

**Opt-out.** Per-enrolment boolean indicating the student is not a catering customer. Different from absence; persists across sessions until enrolment ends or a new enrolment overrides.

**Order construction.** The single event at T-3 days where the agent assembles an order from current absence/exclusion/enrolment state. Order lines are not subsequently mutated.

**Per-instance severity.** Design choice: escalation severity is set per row based on context, not derived from escalation type. The same type can range info to urgent.

**Pre-send / post-send.** Classification of an absence or exclusion by its `received_at` timestamp relative to the relevant `orders.sent_at`. Pre-send affects order construction; post-send doesn't.

**Primary key.** A column whose values uniquely identify each row in a table. Every table in this schema uses an auto-incrementing integer primary key.

**Resolution mode.** Per-escalation indicator (`auto` or `human`) of how the escalation can close. `auto` escalations close when their trigger condition is gone; `human` escalations close when Dylan replies to the notification email.

**Run loop cap.** The maximum number of tool calls the agent makes in a single run. Set to ~15 in v1.

**Soft-state.** Lifecycle state tracked by a nullable timestamp rather than a status enum. Example: `absences.walked_back_at`.

**Source email.** The `incoming_emails` row that an absence, exclusion, or escalation resolution was parsed from. Linked via nullable foreign keys to preserve audit even when intake is manual.

**Tool call (in decision_logs).** A single invocation of an agent tool (database query, LLM call, email send, etc.). Logged automatically via the agent's tool wrapper layer.

**Two-tier feedback.** Manager session feedback + tutor self-feedback. Periodic term survey is the cross-check on the two-tier model.

**Walk-back.** Reversal of a previously-notified absence. Stored as `absences.walked_back_at` timestamp on the original absence row.

**Walk-up.** A student appearing at a session who wasn't expected (either marked absent, not enrolled, or otherwise unexpected). Captured in `walkup_events`. Drives two escalation patterns: unmatched walk-ups (immediate) and repeat false absence (after 2 occurrences).

**Year level (on enrolments).** Stored on `enrolments`, not `students`, because year level is contextual to a time period. Used by exclusions for cohort filtering.

---

*End of schema reference. Total: 13 relationships, 26 tables, 61 documented assumptions, 0 unresolved forward references.*
