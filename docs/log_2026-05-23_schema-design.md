# Schema Design Log — 23 May 2026

**Project:** Padea Operations Agent
**Session:** Schema design — relationships and data model
**Status:** Relationships 1–8 locked. Relationship 9 (pricing) embedded in earlier tables. Relationships 10–13 to be designed in subsequent sessions.

---

## Core design principles (apply throughout)

**Event-storing as default.** The database records *events* (orders placed, feedback submitted, prices charged) rather than *state* (current rating, current caterer). State that downstream code needs is derived from events on demand. This costs slightly more query complexity but pays back in auditability, history preservation, and modular agent compatibility. Override only when derivation cost becomes genuinely expensive, with documentation.

**Student IDs auto-incrementing integers.** Generated at ingest. UUIDs rejected as overkill. Composed keys rejected as brittle to lifecycle changes (year level, school).

**Ingest interpretations are documented assumptions.** Any time source data is messy or implicit and ingest has to make a call, the interpretation is documented in three places: ingest code comments, schema notes file, and the memo.

**Ingest is a one-time bootstrap.** Translates messy source files into the structured schema once. Subsequent data enters through the agent, forms, or escalations — not through re-ingest.

**Schema is general, not catering-specific.** Tables and tools designed so future agentic modules (sick-tutor replacement, attendance, hiring) can build on the same data layer without renegotiating the contract.

---

## Relationship 1: schools and sessions

**Pattern:** One-to-many. One school has many sessions; one session belongs to exactly one school.

**Tables:**
- `schools` — `school_id` PK, attributes: name, short code (e.g. "ISHS", "MBBC").
- `sessions` — `session_id` PK, `school_id` FK, attributes: date, day_of_week, session_start, session_end, dinner_start, dinner_end, building, room.

**Decisions:**
- Each session is its own row per occurrence (no session-template abstraction).
- Building, room, dinner times all live on the session, not on the school — handles mid-term changes without schema gymnastics.
- Manager assignment lives on the session (via `expected_manager_id` / `actual_manager_id`, see relationship 7).

---

## Relationship 2: students and their connection to schools

**Pattern:** Students have *no direct connection to schools*. School relationship captured through the `enrolments` table linking students to specific sessions. School is then derived through enrolments → sessions → schools.

**Tables:**
- `students` — `student_id` PK, attributes: full name, parent_contact_info (TBD).
- `enrolments` — `enrolment_id` PK, FKs: `student_id`, `session_id`. Attributes: `start_date`, `end_date` (nullable; null = currently enrolled), `year_level`, `opted_out` (boolean).

**Decisions:**
- Enrolments link students to *sessions*, not schools — handles "student attends Mon but not Tue" cleanly.
- Year level lives on enrolment, not student — contextual to time period.
- Opt-out is a boolean on enrolment (not a dietary tag) — different kind of fact (whether student is a catering customer), and placement on enrolment handles per-term opt-in/out.
- Default ingest rule: same name at different schools = different students unless explicit evidence to contrary.
- Withdrawal: set `end_date`, don't delete. Re-enrolment creates a new row.

---

## Relationship 3: students and dietary tags

**Pattern:** Many-to-many via pure junction table.

**Tables:**
- `dietary_tags` — `tag_id` PK, `tag_name` (controlled vocabulary).
- `student_dietary_tags` — junction, two FKs (`student_id`, `tag_id`), no extra attributes.

**Decisions:**
- Junction over comma-separated string — enforces vocabulary, enables structured queries.
- No tag categories in v1 — all dietary tags treated as hard constraints.
- Same `dietary_tags` table reused for tutors via `tutor_dietary_tags`.

**Controlled vocabulary (initial set):**
- Descriptor tags (apply to menu items and/or students): `gluten_free`, `dairy_free`, `nut_free`, `vegetarian`, `contains_pork`
- Student-only tags: `halal`, `no_seafood`, `no_shellfish`, `no_beef`, `no_red_meat`, `no_fish`

Note: `no_seafood` ≠ `no_shellfish` (different restrictions, don't collapse).

---

## Relationship 4: menu items and dietary tags

**Pattern:** Many-to-many via pure junction table, with two interpretation rules baked into ingest.

**Tables:**
- `menu_items` — `menu_item_id` PK, `caterer_id` FK, attributes: name, base_price, gst_treatment, `vegetarian_swap_available` (boolean), `effective_from`, `effective_to` (menu versioning).
- `menu_item_dietary_tags` — junction, two FKs, no extra attributes.

**Decisions:**

*VO ("vegetarian option") handling:*
- Modelled as `vegetarian_swap_available` boolean column on menu_items (not as a dietary tag).
- Reasoning: VO is a *capability* of the item, not a property. Treating VO as a tag would create safety bugs.
- Matching: vegetarian students match items tagged `vegetarian` OR items with `vegetarian_swap_available = TRUE`.
- Order lines record the menu_item_id plus a `is_vegetarian_variant` flag for unambiguous caterer communication.

*Halal handling:*
- Modelled via `contains_pork` tag at ingest (keyword detection: "pork", "bacon", "ham"; flag ambiguous cases for manual review).
- Halal-matching done as exclusion query: items NOT tagged `contains_pork`.
- Reasoning: matches the source rule "non-pork = halal" structurally, requires less data entry than tagging halal directly, future-proofs to other pork-avoiding frames (kosher, Adventist).

*Menu item versioning:*
- Items versioned with effective dates rather than mutated. When a caterer changes their menu, the old item gets an end date and a new row is created.
- Consistent with event-storing principle. Past orders still reference accurate menu state.

---

## Relationship 5: caterers, schools, and day-of-week

**Pattern:** Many-to-many at the (caterer × school × day-of-week) level, via associative table.

**Tables:**
- `caterer_school_capabilities` — `capability_id` PK, FKs: `caterer_id`, `school_id`. Attributes: `day_of_week`, `effective_from`, `effective_to` (nullable), `preference_rank`.

**Decisions:**
- Capability ("can serve") stored explicitly; current assignment ("does serve") derived from most recent orders.
- Day-of-week granularity: a caterer can serve School X on Mondays but not necessarily on Wednesdays. Capability rows specify the day. Schools adding new session days require explicit capability confirmation.
- `preference_rank` populated at ingest as a prior (lower = more preferred, inferred from current "currently serves" data), updated by operational signal over time.

**Operational constraints (enforced in agent logic, not data):**
- One caterer can serve at most one school per day. Simplest reading; covers all conflict cases without time-window calculations.
- Capability is conditional on current operating conditions. Significant changes (enrolment growth, schedule shifts, MOQ pressure) trigger re-confirmation escalation rather than silent continuation.

**Out of scope for v1:** delivery distance/feasibility, kitchen capacity, caterer-specific time windows. Captured implicitly in capability matrix; could be modelled if operations expand.

---

## Relationship 6: contacts and caterers

**Pattern:** One-to-many. One caterer has many contacts. Contact roles modelled as four independent booleans.

**Tables:**
- `contacts` — `contact_id` PK, `caterer_id` FK, attributes: name, email, mobile (nullable), `is_order_taker`, `is_chef`, `is_primary_contact`, `cc_on_orders`.

**Decisions:**
- Four orthogonal booleans rather than a single role field. Allows any combination of responsibilities and supports lifecycle changes (primary contact rotation, dual roles).
- Source data preserved as-is at ingest, including apparently-swapped email/name pairings. Caterer emails are Padea-controlled placeholders Dylan uses to monitor the system during judging.

**Operational rules (enforced in agent logic):**
- Every caterer must have exactly one contact with `is_primary_contact = TRUE`.
- Every caterer must have at least one contact with `is_order_taker = TRUE`.
- When primary contact changes, system escalates: "Should previous primary remain cc'd on orders?"

---

## Relationship 7: managers as tutor role on sessions

**Pattern:** Managers are not a separate population from tutors. Manager is a property of (session × tutor), not a person-type.

**Tables:**
- `tutors` — `tutor_id` PK, attributes: name, mobile (nullable). Other fields deferred to future tutor module.
- `tutor_dietary_tags` — junction, reuses shared `dietary_tags` table.
- `sessions` gains two columns: `expected_manager_id` (FK to tutors, nullable) and `actual_manager_id` (FK to tutors, nullable).
- `session_tutor_assignments` — junction, FKs: `session_id`, `tutor_id`. No extra attributes (subject specifics rejected as too fluid to model usefully).

**Decisions:**
- Two manager fields on sessions: expected (pre-session, used for caterer logistics) and actual (post-session, from app data, source of truth).
- Difference between expected and actual implicitly captures cover events; no separate tutor_absences table needed.
- Subject/role specifics not modelled — tutor-student-subject relationships are too fluid in reality (swaps happen, students rotate subjects, tutors help outside their formal expertise).

**Operational rules:**
- A tutor cannot be `actual_manager_id` or appear in `session_tutor_assignments` for two sessions on the same day.
- Pre-session communications use `expected_manager_id` for caterer-to-manager phone routing. If null, system escalates.

---

## Relationship 8: orders and order_lines

**Pattern:** Per-session orders. One order per (caterer × session). Order contains many order_lines.

**Tables:**

`orders`:
- `order_id` (PK)
- `caterer_id` (FK)
- `session_id` (FK)
- `status` — text (draft / review_required / sent / confirmed / amended / delivered / cancelled)
- `generated_at`, `sent_at`, `confirmed_at`, `delivered_at` — timestamps
- `total_estimated_cost` — money snapshot (Layer 2)
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
- `unit_price_at_order_time` — money snapshot (Layer 2)
- `status` — text (active / cancelled / delivered)
- `notes` — text

`caterer_moq_rules`:
- `rule_id` (PK)
- `caterer_id` (FK)
- `menu_variety_count` — integer (4, 5, 6, etc.)
- `min_weekly_meals` — integer

**Decisions:**

*Order granularity:*
- One order per (caterer × session), not per (caterer × week).
- Reasoning: enables per-session caterer rotation (rotation can happen at single-session granularity rather than swapping whole-school assignments); matches how caterers actually work (one delivery at a time); enables clean one-order-one-delivery mental model.
- Trade-off accepted: more emails to caterers per week (11 vs 4), but each email is simpler and matches their per-delivery operations.

*Order sending rule:*
- Orders sent 3 days before session *start* time (not dinner time). Standardised rule across all sessions.
- Mon session → Fri send. Tue session → Sat send. Wed session → Sun send. Thu session → Mon send.

*Per-student meal labelling:*
- Each `order_line` represents one meal for one specific student (or one buffer/contingency meal).
- `quantity` column dropped — implicitly always 1 per line.
- Order line records the menu_item AND the vegetarian variant flag for unambiguous caterer communication.

*Buffer meal model (Option 2 of three options considered):*
- For each session order: one student_meal line per enrolled non-opted-out student + one tutor_meal line per tutor working that session + 2 contingency lines per session.
- Buffer meals (tutor + contingency) drawn from a "common, broadly-appealing" pool — menu items with no major exclusions, common base proteins.
- Dietary-restricted student meals are *always made* even on likely absence (no substitute exists). Common student meals can flex.
- `line_purpose` enum captures the distinction for reporting/analysis.

*Manifest organisation:*
- v1 organises caterer-facing manifest per-session per-student. Tutor-group organisation deferred to future tutor module (would require modelling tutor-student assignments within sessions).
- Physical sorting at delivery is the manager's responsibility, not the caterer's.

*Order status lifecycle:*
- Documented in schema notes. Text field with constraint; could be promoted to enum table later.

*Cross-order weekly aggregates:*
- Tracked as queries over `orders` filtered by caterer + week — not as a stored table.
- Used for MOQ verification, cost reporting, anomaly detection.

*MOQ verification at order generation:*
- When generating an early-week order, agent forecasts remaining week's demand at the same caterer (using current enrolment minus known absences). If projected weekly total falls below MOQ, escalate.
- Alternative: service agreement guaranteeing MOQ floor payment regardless of actual order — would reduce escalations but is a contract negotiation, not a system feature.

*Day-of-week capability constraint:*
- Caterer capability is per (caterer × school × day-of-week). Schools adding new session days require new capability rows.

*Caterer rotation (v1):*
- Human-in-the-loop. Agent detects performance issues, identifies eligible alternatives, drafts communications (email to new caterer offering shift; email to original caterer if accepted), escalates to Dylan with full context.
- Dylan approves before any emails are sent. Future versions may automate parts of this; v1 protects commercial relationships by keeping decision with a human.

---

## Relationship 9: pricing (no new tables)

Pricing structure is fully accommodated by existing tables. No separate `pricing_rules` or `payments` table.

**Where pricing lives:**
- `menu_items.price` — Layer 1 (pricing rules, current state)
- `menu_items.effective_from` / `effective_to` — Layer 1 versioning (when prices change, new row created)
- `caterers.delivery_fee` and `caterers.gst_treatment` — Layer 1 delivery and tax structure
- `caterer_moq_rules` — Layer 1 MOQ rules (variety-dependent)
- `order_lines.unit_price_at_order_time` — Layer 2 (snapshot at order time)
- `orders.total_estimated_cost` — Layer 2 aggregate (sum of order_lines + delivery)
- `orders.actual_paid_cost` — Layer 3 (fabricated demo data, populated near end of build to show variance tracking)

**Payment workflow:**
- Payment calculation derived from orders per (caterer × week) — query, not stored.
- Monday EOD: agent sums committed orders per caterer, compares to MOQ rules, computes `max(committed_total, MOQ_floor)`.
- If MOQ shortfall: escalation requests extras at the week's final session to make use of MOQ floor payment.
- Recording actual payment events (post-banking integration) is a future concern; not modelled in v1.

---

## Relationship 10: feedback

**Pattern:** Multiple feedback row types (manager session feedback, tutor self-feedback, term surveys for parents and students) all live in one `feedback` table discriminated by `feedback_type`. Extension tables hold type-specific structured data. LLM-extracted structured signal lives in a related cache table. Walk-up student events get their own dedicated table because they drive operational escalations.

**Tables:**

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
- `escalation_id` (FK, nullable — populated when escalation is generated)
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

**Decisions:**

*Two-tier collection model plus a periodic check:*
- **Manager session feedback** — one row per session. Manager observes consensus among students and submits one overall rating with free-text comments capturing specific issues. Reduces response-rate degradation; trusted operationally.
- **Tutor self-feedback** — one row per tutor per session. Captures: did you eat your meal? if not, why? plus a 1-5 rating and free-text comment. Walk-up student names captured here when meals are redirected.
- **Term survey** — periodic (end-of-term) survey to parents and students separately. Mostly structured questions plus optional free text. Cross-checks manager reliability.

*Manager rates session-overall, not per-menu-item:*
- Per-item rating is too much work and asks the manager to decompose an inherently session-level judgement.
- Granularity recovered via comment processing — the agent extracts structured signals from comments, tagging mentions of specific menu items, dietary issues, delivery concerns, etc.

*Tutor feedback retains tutor_id (NOT anonymous):*
- Internal: identified, for outlier detection (consistent-5s rater, unusually low rater).
- External (aggregates shown to caterers): anonymised at presentation time.
- Manager training reinforces: feedback drives quality improvements; blind 5s degrade signal.

*Rating scale 1-5:*
- Avoids cognitive bias and mean-drift of 1-10 scales.

*Comments expected as default for all feedback, not just extremes:*
- Earlier "extreme rating requires comment" rule dropped. Comments are the default practice.

*Solicited only — unsolicited messages go through escalation path:*
- Parent complaints, caterer concerns, etc. become escalations to Dylan, not feedback rows.
- Keeps the feedback pipeline structured and the issue-handling pipeline separate.

*Term survey respondents pseudonymous:*
- Random consistent ID per respondent across terms. Honesty preserved; longitudinal tracking possible.

*Two separate term surveys (parents and students):*
- Parents emphasise overall satisfaction, value, communication.
- Students emphasise taste, quantity, variety.
- Distinguished by `feedback_type` enum value.

*Walk-up events as a first-class table:*
- Walk-up student names captured in tutor free text are post-processed into the `walkup_events` table.
- Drives two escalation patterns:
  1. Walk-up name doesn't match any enrolled student in the school → immediate escalation.
  2. Walk-up name matches a student marked absent at this session, and same student has 2+ such events → escalation: call parent.

*Comment extraction stored as a computed cache (deliberate exception to event-storing):*
- Justified because LLM extraction involves cost/latency, signals are queried frequently, and source comments are preserved (re-extraction possible if logic improves).

*`submission_delay_seconds` NOT stored:*
- Derived at query time from `submitted_at - sessions.session_end`. Cheap join; no denormalisation needed.

**Operational analyses (derived from feedback, computed by agent, not stored):**

1. **Caterer rolling rating** — average over 4 weeks per (caterer × school), weighted by submission-timing reliability, normalised by rater baseline.
2. **Rater baseline normalisation** — per-manager average across historical ratings; individual ratings adjusted relative to baseline before aggregating. Compensates for rating-personality differences.
3. **Submission-timing reliability weighting** — feedback weight decays with submission delay. Live submission gets full weight; delayed submissions weighted lower.
4. **Per-tutor reliability** — outlier detection on tutor ratings; tutors consistently rating 5s or rating unusually low get downweighted.
5. **Per-student preference inference** — derived from feedback patterns and consumption signals.
6. **Rotation trigger** — sustained low rolling rating for a (caterer × school × day) escalates rotation review to Dylan.
7. **Walk-up escalation triggers** — unmatched walk-up = immediate escalation; second false-absence walk-up for same student = parent call escalation.
8. **Manager reliability cross-check** — compare manager session-feedback averages to term-survey aggregates per (caterer × school); flag systematic over/under-rating.

**Out of scope for v1:**
- Per-meal student ratings (replaced by manager consensus model).
- Real-time sentiment analysis of unsolicited inbound messages (treated as escalations).
- Automatic rotation actions (rotation remains human-in-the-loop).

---

## Running assumptions list (for memo)

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

---

## What remains to design

**Relationship 11: Absences** — link student to session with date; how it interacts with order amendment timing.

**Relationship 12: Exclusions** — session cancellation with year-level granularity (the CHAC Y10/Y12 partial-cancellation case).

**Relationship 13: Agent runs, escalations, decision logs** — operational tables for the agent's own activity. Note: `escalation_id` is referenced from `walkup_events` already; the escalations table needs to support that FK.

---

## Open / deferred decisions

- Parent table structure (kept in scope as feedback channel; structure TBD when designing feedback).
- Schools attributes beyond name and short code (deferred until needed).
- Layer 3 actual payment recording (deferred to v2 with banking integration).
- Buffer-size auto-tuning based on consumption data (deferred to v2).
- Caterer day-of-week constraint validation logic (TBD when designing agent's order-generation).
