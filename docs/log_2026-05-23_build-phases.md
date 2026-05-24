# Build Phases — Padea Operations Agent

**Status:** Implementation plan for v1 build, phased to match workflow needs.
**Compiled:** 23 May 2026
**Companion document:** `schema_complete.md` (the full 26-table architectural design that this build progressively implements)

---

## Purpose of this document

The schema design (`schema_complete.md`) is the architectural target — 26 tables, locked through three sessions of design work. This document is the *implementation plan* that delivers that schema progressively over the build week.

The build is split into phases. Each phase:

- Adds a specific subset of tables from the full schema
- Adds the agent capabilities that use those tables
- Is rigorously tested before the next phase begins
- Respects the final 26-table architecture (no restructuring of phase-1 tables when phase-2 lands)

**The architecture is not being simplified.** Enrolments stay explicit, dietary tags stay normalised, event-storing stays the default, the operational tables stay reserved for their purpose. Each phase implements a slice of the final design at full fidelity. Tables not yet built are *deferred*, not *redesigned*.

**The deletion test the task asks for is applied at the phase level**, not at the architecture level. For each phase: was every table and capability added because the workflow demanded it? If not, defer to the next phase. The phases earn their tables.

---

## How phases relate to each other

Phases are additive. Phase 2 does not modify any table created in phase 1; it adds new tables and extends agent logic. Phase 3 likewise.

The schema design was done deliberately to support this: foreign keys point in the right direction, junction tables are self-contained, and the operational cluster (agent_runs, decision_logs, escalations, incoming_emails) is referenced by other tables via nullable FKs that stay null until those tables are built.

**The expansion path from one phase to the next is purely additive.** No table from a completed phase needs to be altered when a later phase lands.

---

# Phase 1 — Identity, dietary, and supply foundation

## Goal

Establish the static reference data that the catering workflow depends on. After phase 1 the database knows what schools, students, sessions, caterers, and menus exist, and what every student can and can't eat. No orders are generated yet; no workflow runs end-to-end.

This phase is the *substrate*. Everything downstream queries against it.

## Tables introduced

From the identity and structural cluster:
- `schools`
- `sessions` (without `expected_manager_id` / `actual_manager_id` populated yet — these columns exist but stay null until phase 3)
- `students`
- `enrolments`

From the dietary modelling cluster:
- `dietary_tags`
- `student_dietary_tags`

From the catering supply side:
- `caterers`
- `contacts`
- `caterer_school_capabilities`
- `caterer_moq_rules`
- `menu_items`
- `menu_item_dietary_tags`

**Total: 12 tables.**

## Agent capabilities introduced

There is no agent loop yet in phase 1. The "capabilities" are ingest and read-only query.

- **Ingest scripts** that read the messy source files (`students.xlsx`, `sessions.xlsx`, `caterers.xlsx`, the three PDFs) and populate the 12 tables.
- **Ingest interpretation logic** that applies the documented assumptions: dietary controlled vocabulary mapping, VO as boolean, `contains_pork` tag inference, halal as the absence of `contains_pork`, name-collision handling across schools, GST normalisation, capability matrix by (caterer × school × day).
- **Read-only query tools** that the agent will use in later phases: lookup students by session, lookup eligible caterers for a session, lookup menu items by caterer with dietary tags, lookup MOQ thresholds.

## Test criteria

Phase 1 is complete when all of the following pass:

- All 12 tables exist with their full column sets from the schema doc.
- All 6 schools, 11 sessions, ~290 students, 4 caterers, 6 contacts, ~40 menu items, the capability matrix, and the dietary controlled vocabulary are populated from the source files.
- Ingest is idempotent — re-running the script produces the same database state, not duplicate rows.
- Spot-check queries return correct results: "list all halal students at ISHS", "which caterers can serve CHAC on Wednesday", "what's Kenko's MOQ at 5 menu items".
- Every interpretation made by the ingest scripts is documented in code comments and reflected in the assumptions list.
- Edge cases visible in the source data are handled or flagged: name collisions across schools, opt-outs combined with dietary restrictions, VO items split from regular tags, contains_pork inference, capability rows per (caterer × school × day).

## What is deliberately deferred

Not in phase 1:

- `tutors`, `tutor_dietary_tags`, `session_tutor_assignments` — the tutor data isn't needed until manager assignments and buffer-meal logic appear in phase 2.
- `orders`, `order_lines` — no orders are generated yet.
- `absences`, `exclusions` — no order generation means no cancellation logic yet.
- `feedback` and its extensions — feedback collection is phase 4 at earliest.
- `walkup_events`, `term_surveys`, `feedback_extracted_signals` — all downstream of feedback; deferred.
- `agent_runs`, `decision_logs`, `escalations`, `incoming_emails` — phase 1 has no agent loop; reasoning isn't being logged yet.

## Why phase 1 is complete without those pieces

Phase 1 establishes the *data substrate*. Until that substrate is correct, building order generation on top of it would be premature — bugs in ingest would cascade into bugs in the workflow.

Phase 1 ends with a database that is *queryable and trustworthy* but doesn't yet do anything operational. That's the right floor: the workflow phases that follow can assume the substrate is correct rather than testing it themselves.

---

# Phase 2 — Catering order engine

## Goal

Build the full catering order generation workflow. After phase 2 the agent can generate a complete, per-session order for any caterer — respecting all dietary constraints, absences, exclusions, tutor meals, contingency meals, the 10% exclusion attendance buffer, and the weekly MOQ floor. The agent decides what to send; the email itself is not yet sent (that's a phase 3 concern).

This is the operational core. Phase 2 contains most of the substantive agent logic.

## Tables introduced

From the identity and structural cluster (deferred from phase 1):
- `tutors`
- `tutor_dietary_tags`
- `session_tutor_assignments`

Plus the manager fields on `sessions` get populated (`expected_manager_id` and `actual_manager_id`).

From the orders cluster:
- `orders`
- `order_lines`

From the event tables that feed order generation:
- `absences`
- `exclusions`

From the operational cluster (because order generation logs decisions and creates escalations):
- `agent_runs`
- `decision_logs`
- `escalations`

**Total: 10 new tables, 22 cumulative.**

## Agent capabilities introduced

This is where the agent becomes a real entity.

- **The agent loop itself** — invocation, structured reasoning via Claude API tool-calling, tool-call cap (~15 per run), graceful failure.
- **Tool layer** built on phase 1 reads, extended with writes to orders, order_lines, absences, exclusions, agent_runs, decision_logs, escalations.
- **Order construction logic** — the per-session order-generation algorithm:
  - Filter to enrolled non-opted-out students
  - Apply exclusions (whole-session and year-level partial)
  - Apply absences received before order send time
  - Dietary-override rule for restricted students (meal still made even on cancellation)
  - Per-student meal selection from the eligible caterer's menu, respecting dietary tags
  - VO handling via the `is_vegetarian_variant` flag on order_lines
  - Tutor buffer meals (1 per tutor working the session)
  - Contingency buffer (2 per session)
  - 10% attendance buffer for year-level exclusions
  - MOQ forecasting across the week: if the projected weekly total falls below the caterer's variety-dependent MOQ, escalate
  - Pricing snapshot on each line at order construction time
- **Decision logging** — every meaningful agent decision (branch decisions, rule applications, tool calls) gets a row in `decision_logs`, with the reasoning written into the `reasoning` field for branch decisions.
- **Escalation creation** — when the agent encounters a condition it shouldn't auto-resolve (MOQ shortfall, dietary conflict, missing capability, ambiguous data), it creates an `escalations` row with a `match_key` for deduplication.
- **Run lifecycle** — every invocation creates an `agent_runs` row; status is finalised at the end of the run; crashed-run cleanup runs at the start of each subsequent run with a 30-minute staleness threshold.

## Test criteria

Phase 2 is complete when all of the following pass:

- Running the agent against the phase 1 data produces a complete order for every session in the demo week, for every relevant caterer.
- Each order is auditable end-to-end via `decision_logs`: which students were included, which were excluded and why, what menu items were chosen and why, how MOQ was verified.
- Dietary safety verified: a vegetarian student is never assigned a non-vegetarian item without the VO flag; a halal student never gets a `contains_pork` item; allergy tags are respected.
- Buffer logic verified: every session has 1 tutor meal per tutor + 2 contingency, and year-level exclusions trigger the 10% attendance buffer (rounded up to whole meals).
- Absences received before the order send time omit non-dietary meals and retain dietary meals (walk-up insurance + commercial guarantee).
- Whole-session exclusions correctly prevent any order from being constructed.
- MOQ shortfall correctly produces an escalation rather than silently under-ordering.
- An adversarial harness tests at least the following edge cases: a caterer with no eligible students, a session with all students opted out, a session entirely excluded, an absence arriving for an already-opted-out student, a student with conflicting dietary tags.
- Decision logs render as readable HTML (rough form is fine; polish is phase 5).
- Escalation deduplication works: re-running the agent doesn't create duplicate escalations for the same `(escalation_type, match_key)`.

## What is deliberately deferred

Not in phase 2:

- Email sending (incoming or outgoing). The agent generates the orders into the database; the email channel itself comes in phase 3.
- `incoming_emails` table — needed once email intake is real; phase 3.
- Walk-back logic for absences in the database — the `walked_back_at` column exists but the workflow for handling walk-backs runs through phase 3's email parsing.
- Feedback in any form — phase 4.
- Caterer rotation logic — phase 4 or v2; depends on whether feedback data justifies it within demo scope.
- The HTML decision log as a *polished* demo surface — phase 5.

## Why phase 2 is complete without those pieces

The catering order engine is the heart of the system. By the end of phase 2 the agent is doing real, complex reasoning about real, messy data — and producing orders that respect every constraint we've designed for.

Email sending is mechanical glue that turns the database output into delivered communication. Important for the demo, but separable from the reasoning. Building it before the reasoning is correct would risk shipping a system that *looks* automated but makes silently bad decisions.

Feedback is a closing-the-loop concern. The order engine has to work before feedback about it can mean anything. Phase 4 is where the loop closes.

---

# Phase 3 — Email channel and intake

## Goal

Connect the agent to the simulated email I/O channel. After phase 3 the agent receives parent absence emails, school exclusion notifications, and caterer replies through `emails/incoming/`, and sends its generated orders, escalation notifications, and caterer communications through `emails/outgoing/`.

This phase turns the order engine from "generates orders into the database" into "operates the catering process end-to-end via email", which is what the demo needs to show.

## Tables introduced

From the operational cluster:
- `incoming_emails`

That's it for new tables. Phase 3 is primarily about *capabilities* that use existing tables.

The forward references from `absences.source_email_id` and `exclusions.source_email_id` to `incoming_emails.email_id` now resolve.

**Total: 1 new table, 23 cumulative.**

## Agent capabilities introduced

- **Email reading** — the agent watches `emails/incoming/` for new text files, parses them as emails, writes them to `incoming_emails` with classification.
- **Email classification** — first-pass classifier categorises each incoming email as `absence_notification`, `exclusion_notification`, `caterer_reply`, `escalation_resolution`, or `unclassified`. Unclassified emails escalate for human review.
- **Absence intake** — parent emails classified as `absence_notification` get parsed: sender, student name, school (for disambiguation), session date(s), reason. The agent writes one `absences` row per affected session, expanding multi-session intake ("away all week") into N rows.
- **Exclusion intake** — school emails classified as `exclusion_notification` get parsed: scope (whole session or year-level), affected sessions, reason. The agent writes `exclusions` rows.
- **Walk-back handling** — when a parent emails to reverse a previous absence, the agent finds the matching absence row and sets `walked_back_at`.
- **Email sending** — the agent writes outbound emails to `emails/outgoing/` for caterer orders (with per-contact `cc_on_orders` rules respected), for escalation notifications to Dylan (with the `[PADEA-ESC-{id}]` token in the subject), and for any other agent-initiated communication.
- **Escalation resolution parsing** — Dylan's replies to escalation notification emails land in `incoming_emails`, get classified, and are parsed for closure keywords. The matching `escalations` row gets closed.
- **Auto-resolution of stale escalations** — at the start of each run, the agent re-evaluates open `auto`-resolution escalations and closes any whose trigger condition is gone.

## Test criteria

Phase 3 is complete when all of the following pass:

- The agent runs end-to-end on a simulated week: receives absence emails, parses them into `absences`, generates orders, sends order emails to caterers, generates escalation notifications, parses Dylan's replies, closes escalations.
- Email classification is reliable: at least the four primary classes (absence, exclusion, caterer reply, escalation resolution) are correctly identified for clean inputs, with unclassified emails escalating cleanly.
- Multi-session absences ("Noah is away all of next week") correctly expand into N absence rows.
- Walk-back emails correctly update the original absence row rather than creating a new one.
- CC rules respected: GYG's Medium Giraffe is cc'd on GYG order emails; Terrific's James is not cc'd.
- Adversarial cases handled: absence email for a student not enrolled at the named school, exclusion email arriving after the order has been sent, caterer reply that doesn't fit any classification, malformed sender info.
- The `[PADEA-ESC-{id}]` subject token correctly routes Dylan's replies to the right escalation; fuzzy matching as fallback works when the token is stripped.
- Idempotency: re-running the email-intake pass doesn't double-process emails (via `processing_status` and `message_id` uniqueness).

## What is deliberately deferred

Not in phase 3:

- Feedback collection in any form — phase 4.
- Caterer rotation logic — depends on feedback.
- Pre-delivery reminders (day-of caterer reminders with manager mobile, building, room) — useful in production but not demo-critical; could be a quick add at the end of phase 3 if time permits, otherwise phase 5.
- Attachment handling on incoming emails — metadata only in v1; binary storage deferred.
- PII redaction in `decision_logs.tool_input` — deferred to v2.

## Why phase 3 is complete without those pieces

After phase 3, the agent is operating a real end-to-end catering workflow. Inputs arrive via email; outputs are sent via email; the database is the single source of truth. The system is *demonstrable*.

Feedback collection is the loop-closing layer. It depends on the order workflow being correct, which phase 3 verifies. Phase 4 adds it.

---

# Phase 4 — Feedback ingestion and rotation signal

## Goal

Close the satisfaction loop. After phase 4 the agent receives manager session feedback and tutor self-feedback, processes it into structured data, computes caterer rolling ratings (with rater-baseline normalisation and submission-timing weighting), and surfaces rotation candidates as escalations when a caterer's rating sustains below threshold.

This phase is where the system stops being an ordering tool and becomes the *satisfaction loop* that the goal statement specified.

## Tables introduced

From the feedback cluster:
- `feedback`

Plus the existing `escalations` table picks up new escalation types (`low_feedback_rotation_review` and similar) without schema changes.

**Total: 1 new table, 24 cumulative.**

Note: `feedback_extracted_signals`, `walkup_events`, and `term_surveys` are *not* in phase 4. See deferrals below.

## Agent capabilities introduced

- **Feedback intake from the manager and tutor apps** — simulated as files in `emails/incoming/` with a `feedback_submission` classification, parsed into `feedback` rows.
- **Rating aggregation logic**:
  - Caterer rolling rating: average over 4 weeks per (caterer × school × day), weighted by submission-timing reliability (faster = more reliable), normalised by rater baseline.
  - Per-tutor reliability scoring: simple outlier detection on tutor ratings; tutors consistently rating 5s or unusually low get downweighted.
- **Rotation trigger** — when a caterer's rolling rating for a (school × day) sustains below threshold (configurable, default <3.0 over 4 weeks), the agent creates an escalation drafting the recommended rotation: which alternative caterer to switch to (from `caterer_school_capabilities`), draft emails to both the incumbent and the candidate. Human-in-the-loop: Dylan approves before any rotation email is sent.
- **Feedback summary in the decision log** — the HTML decision log gains a "feedback observed" section showing recent ratings and any pattern shifts.

## Test criteria

Phase 4 is complete when all of the following pass:

- Feedback submissions for a simulated week are correctly parsed into `feedback` rows from both manager and tutor sources.
- The rating aggregation produces sensible caterer ratings for the simulated data, with rater-baseline normalisation visibly affecting outputs (a 4 from a high-baseline rater is treated differently from a 4 from a low-baseline rater).
- Submission-timing weighting works: a feedback row submitted 24 hours after session end is weighted lower than one submitted within an hour.
- A simulated quality decline scenario (synthetic feedback data showing a caterer's rating dropping over 4 weeks) correctly triggers a rotation escalation with a drafted recommendation.
- Rotation escalations include the draft emails to both caterers, the performance data justifying rotation, and Dylan can approve/dismiss by replying to the escalation notification.
- No rotation email is sent without Dylan's approval reply.

## What is deliberately deferred

Not in phase 4:

- `feedback_extracted_signals` — LLM-extracted structured signals from comments. Real value but expensive to build for one-week demo data. The comments are stored as plain text on the `feedback` row; the extraction layer is v2.
- `walkup_events` — first-class walk-up reconciliation. The escalation logic is genuinely useful but a one-week demo won't show walk-up patterns firing. Walk-up names mentioned in tutor feedback comments stay as plain text in v1; the agent can flag them via simple keyword detection in the comment if needed.
- `term_surveys` — end-of-term parent and student surveys. No term data in the demo; deferred to v2.

## Why phase 4 is complete without those pieces

The satisfaction loop closes the moment feedback informs the next order. Phase 4 delivers that: feedback comes in, ratings adjust, rotation candidates surface. The loop is operational.

The deferred pieces (extracted signals, walkups, term surveys) all add fidelity to the signal but don't change the fundamental loop shape. They're v2 enhancements that the architecture already accommodates — the `feedback_extracted_signals` cache and the `walkup_events` table are designed and documented; they just aren't built in v1.

---

# Phase 5 — Demo polish

## Goal

Convert the working system into a submission-ready demonstration. After phase 5 the HTML decision log is polished, the process diagram is finalised, the memo is drafted, and the database is mirrored to Supabase for the submission link.

This phase has no architectural significance. It's the layer of work between "the system runs" and "the system can be judged".

## Tables introduced

None. All tables from the v1 build are in place by end of phase 4.

## Agent capabilities introduced

None new. The agent works as it did at the end of phase 4.

What changes:

- The HTML decision log gets its presentation layer: timeline cards, colour-coded statuses (green/amber/red), tool-call filtering for readability, expandable reasoning sections.
- The process diagram (deliverable #2) is finalised, drawn from the actual flow the agent runs.
- The memo (deliverable #1) is drafted, telling the deletion-tested build story honestly.
- The SQLite database is mirrored to Supabase via a one-way push for the deliverable link.
- The GitHub repository is cleaned up: README updated to reflect the actual built system, log files committed and dated, decisions document tidied.
- The 5-minute demo video is recorded.

## Test criteria

Phase 5 is complete when all of the following pass:

- The five required deliverables (memo, process diagram, database link, demo video, build artifact) are produced and reviewed at least once.
- The demo video shows the system running end-to-end including at least three of the adversarial edge cases.
- The Supabase mirror is queryable and matches the SQLite source.
- The GitHub repo is in a state Dylan could clone and run with the documented setup steps.
- The memo doesn't overstate what's built and explicitly names the deferred work as deferred.

## What is deliberately deferred

Everything not yet built remains deferred. The deferral story is the memo's story.

## Why phase 5 is complete without those pieces

Phase 5 is the seam between "this is what I built" and "this is how you assess it". Adding more capability in phase 5 risks shipping unfinished work; the discipline is to *polish* what works rather than *extend* it.

---

# Tables not yet implemented at end of v1

For the memo's deletion-and-deferral story, the following tables are designed in `schema_complete.md` but deliberately not built in v1:

- `feedback_extracted_signals` — LLM-extracted structured signal from feedback comments. Cache table; not justified by demo data volume.
- `walkup_events` — first-class walk-up reconciliation. Schema-ready; walk-up patterns won't manifest in one demo week.
- `term_surveys` — end-of-term survey extension. No term data in demo scope.

Each of these is *designed* — the schema doc specifies columns, FK relationships, and operational rules. Adding them to the codebase is a forward task with no architectural restructuring required. The seam where each plugs in is documented:

- `feedback_extracted_signals` plugs in via FK to `feedback.feedback_id`. The extraction logic runs as a post-feedback agent task; no other table changes.
- `walkup_events` plugs in via FKs to `feedback`, `sessions`, `students`, and `escalations`. The walk-up extraction logic reads tutor feedback comments; no other table changes.
- `term_surveys` plugs in via FK to `feedback`. Term-survey-specific structured fields live on the extension table; the parent `feedback` row carries the common metadata.

**This is the v1/v2 boundary.** v2 picks up here.

---

# Sequencing rationale

Why this phase order, in honest plain English:

**Phase 1 first** because nothing else can be built or tested against the wrong data substrate. Bugs in ingest cascade into bugs in every workflow; fix them at the bottom.

**Phase 2 next** because the catering order engine *is* the heart of the system. Until orders are generated correctly, every other capability (email, feedback, rotation) operates against a workflow that doesn't yet work. Build the hard reasoning first.

**Phase 3 then** because the email channel turns the working order engine into a *demonstrable* end-to-end system. The order engine doesn't change; it just gets a real input and output channel.

**Phase 4 then** because feedback only matters when there's a working order workflow to feed back about. Phase 4 closes the loop the goal statement requires.

**Phase 5 last** because polish is the wrong instinct for any phase that isn't ready for polish. Once the system runs correctly, the time spent on presentation is concentrated and productive.

---

# Risk register

What could derail the plan, and what we do if it does.

**Phase 1 takes longer than expected (ingest is messier than predicted).** Acceptable. The substrate has to be right. Phase 2 can compress if needed; phase 4 can shrink to feedback-intake-only without rotation if necessary.

**Phase 2 reveals a schema bug that requires restructuring.** This is the scenario the schema design tried to prevent. If it happens, fix the schema, document the change in the decisions log, and proceed. Don't try to work around it in code.

**Phase 3 email parsing turns out to be much harder than expected.** Reduce email classification to the bare minimum (absence and exclusion only; caterer replies escalated as-is). Caterer-reply parsing is genuinely hard with real messy text; for the demo, escalating ambiguous replies to Dylan is a reasonable v1 stance.

**Phase 4 is reached late and feedback can't be fully built.** Drop rotation logic; keep feedback intake. The story becomes "the loop is plumbed; rotation logic is v2". Honest, demonstrable, and consistent with the deletion philosophy.

**Phase 5 is reached late.** Memo and process diagram are non-negotiable. Demo video can be lower fidelity. Supabase mirror is a one-day task that should be slotted in regardless of phase 5 timing.

---

# What stays unchanged through the build

A few principles that govern every phase:

- The full schema is the architectural target. No phase modifies a table built in a previous phase.
- Event-storing remains the default. Deferred tables (extracted signals, walkup_events) are deliberate exceptions documented in advance.
- Ingest interpretations are documented in three places: code comments, schema notes, and the memo's assumptions list.
- Every agent decision worth understanding gets a `decision_logs` row with reasoning when the agent loop is built (phase 2 onwards).
- Escalations are how the agent hands work to Dylan. The system never silently fails; ambiguous data escalates.
- Tests are written and run at the end of each phase, not deferred to phase 5.

---

*End of build phase plan. The plan is a working document. As we build, we update this file with what actually happened, what we cut, what we learnt. The honest retelling is the memo material.*
