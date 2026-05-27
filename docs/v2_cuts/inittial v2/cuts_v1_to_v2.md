# Cuts — V1 to V2

**Purpose.** A per-decision review of `DECISIONS.md` (V1) against the V2 scope captured in `summary_v2.md` and `schema_v2.md`. Each V1 decision gets one of three verdicts: CUT (removed entirely), KEEP (survives as-is), or SIMPLIFY (survives in a reduced form). The criteria applied: deletion is the default; survival requires a positive argument grounded in the heats deliverable; automation is deferred unless the manual version genuinely cannot scale; abstraction is collapsed wherever the current data volume does not earn it.

**Compiled:** 26 May 2026
**Companion documents:** `summary_v2.md`, `schema_v2.md`, `DECISIONS.md` (V1).

---

## How to read this document

Decisions are reviewed in the order they appear in `DECISIONS.md`. The verdict is in bold; the second line states the rationale; a third line names the consequence for V3 if relevant. Where V2 differs structurally from V1 (not just by removal but by a different design choice), the divergence is called out explicitly.

A summary section at the end groups the cuts by theme so the overall shape of the reduction is visible.

---

## Section 1 — Architecture

**ADR-001: Hybrid trigger model (scheduled + event-based + threshold).** **SIMPLIFY.** V2 has one trigger: a scheduled weekly run on Thursday. Event-based triggers and threshold-based catch-up are folded into the next scheduled run — incoming emails are ingested at the start of the run, caterer non-response is checked at the start of the run. The `trigger_context` field on runs goes away because every run is the same shape. For V3 if mid-week intervention turns out to be necessary, the event-based layer can be added without restructuring V2's run model.

**ADR-002: Per-student labelled meal manifest.** **KEEP** (structurally simplified). V2 keeps the principle — each meal is committed to a specific enrolment before send. The `order_lines` table is collapsed into a `meal_assignments` JSON column on `orders`; the principle survives without the table.

**ADR-003: Confidence-aware escalations with configurable thresholds.** **SIMPLIFY.** V2 escalates or does not — no tier system (routine/notable/escalation), no per-decision-type configurable thresholds, no `match_key` deduplication, no recurrence count. The agent surfaces a reason text and the run's status carries `escalated`. Tiering and dedup are V3 candidates if the volume of escalations during heats operation justifies the structure.

**ADR-004: Term-start parent preference + weekly student selection.** **SIMPLIFY.** V2 keeps per-student acceptable item lists (as `acceptable_menu_item_ids` JSON on `enrolments`) but cuts the weekly student selection loop entirely. The agent picks one item from the student's acceptable list. The `term_preference_selections` and `student_session_selections` tables go away, along with the mid-term enrolment manual-decision state and the `selected_by` provenance field. Student-side per-week picking is the clearest V3 addition if the heats demo demonstrates the matcher works.

**ADR-005: ML predictions for absences and walk-ups.** **CUT.** V2 uses a flat operational margin (10% rounded up, configured as a constant). The `absence_predictions` and `walkup_predictions` tables, feature snapshots, model versions, and the prediction-vs-actuals reporting are all removed. The argument for ML predictions is that fixed margin either runs short or carries average overhead — both true, but neither is a heats blocker; this is exactly the kind of optimisation that earns its place once V2 reveals where the margin is wrong.

**ADR-006: Tutor meals as a designed primitive.** **CUT.** V2 does not model tutor meals separately. The data the system has is per-student enrolments; tutors are not in V2's cohort. If tutors eat at sessions (which they evidently do), they are absorbed by the operational margin or handled out-of-band for the demo. `orders.tutor_buffer_meals_per_session` and the `tutor_buffer` line purpose are removed entirely. Add back in V3 if the operational margin proves insufficient for tutor coverage.

**ADR-007: Measured-performance food quality system.** **CUT.** V2 does not measure caterer quality, does not produce scorecards, does not detect decline, does not draft rotation proposals. The `caterer_scorecard_snapshots` and `caterer_decline_signals` tables, the tokened scorecard URLs, and the rolling-window decline trigger are all removed. This is the biggest single cut from V1 and the strongest V3 candidate — the brief explicitly mentions food quality declining as a problem, so the rotation mechanism has a named consequence ready to argue for its return.

**ADR-008: SQLite local + Supabase Postgres mirror at submission.** **SIMPLIFY.** V2 ships SQLite, committed to the repo as a `.sqlite` file. The Postgres mirror step is deferred — the brief accepts "other tools as long as we can access the database via a link," and a GitHub-committed SQLite file qualifies. Dual-substrate compatibility is no longer a constraint on column types. If heats judges respond poorly to needing a SQLite browser, Postgres mirroring is a V3 addition.

**ADR-009: Email I/O simulated via filesystem.** **KEEP.** V2 retains the filesystem simulation. The `incoming_emails` and `outbound_emails` tables are removed (see ADR-037 below); raw incoming emails live as files in `emails/incoming/`, and outgoing emails are written to `emails/outgoing/` with the rendered body also stored on the relevant `order` row.

**ADR-010: Python + Sonnet 4.6 + Haiku 4.5 routing.** **SIMPLIFY.** V2 uses Sonnet 4.6 only. Haiku routing for email classification and lightweight extraction is removed. The argument for Haiku is volume-driven latency and cost — at heats scale (a single demo run), neither is binding. The `model_identifiers` field on `agent_runs` is unnecessary because every run uses the same model. If V3 demonstrates a real cost or latency concern, Haiku returns for routing.

---

## Section 2 — Schema

**ADR-011: Integer auto-increment primary keys.** **KEEP.** V2 matches exactly. UUIDs add nothing without a second system to merge with.

**ADR-012: Sessions as concrete dated rows.** **DIVERGE / SIMPLIFY.** V2 stores `session_slots` as recurring (school, day-of-week) templates rather than as one row per date. The V1 argument for dated rows is that exceptions are routine and per-date variation is easier to edit on a flat table; the V2 argument is that for a single-week heats demo with eleven session slots, the template form is materially smaller and exceptions are already handled by the `exclusions` table. This is the largest structural divergence between V1 and V2. If V3 introduces real per-date variation (different rooms, ad-hoc time changes), dated instance rows can be added without disturbing the templates.

**ADR-013: Enrolment lifecycle via start_date / end_date.** **CUT.** V2 has no enrolment lifecycle. Every enrolment is current; the system runs against the current term only. `enrolment_history` for mutations is removed. Re-enrolment across terms is V3 if the system runs across multiple terms.

**ADR-014: Enrolment as first-class for year, opt-out, dietary, parent.** **KEEP** (with further reduction). V2 keeps the principle that contextual attributes live on the enrolment, and goes one step further: the `students` table is removed entirely (see ADR-031 below). Each enrolment row carries the student's name directly. Dietary and opt-out are JSON/boolean columns on the enrolment; parent contact is two text columns on the enrolment.

**ADR-015: Controlled dietary vocabulary in tag table + junction.** **SIMPLIFY.** V2 stores dietary as a JSON `dietary_flags` field on enrolments (with keys for halal, vegetarian, gluten_free, dairy_free, nut_free, no_pork, no_beef, no_seafood, no_shellfish, no_fish, no_red_meat) and as boolean columns on menu items. The `dietary_tags`, `enrolment_dietary_tags`, `menu_item_contains`, and `menu_item_suitable_for` tables are removed. The severity distinction (preference / allergy / anaphylaxis) is also cut — the source data does not record severity, so V2 has no signal to model it on. V3 brings back severity and an extensible vocabulary if either earns its place.

**ADR-016: Three junction tables for dietary attributes vs polymorphic.** **N/A.** The underlying tables are cut by ADR-015's simplification, so the question of how to structure them does not arise in V2.

**ADR-017: Tutor managers via expected/actual rows in `session_tutor_assignments`.** **SIMPLIFY.** V2 has `manager_name` and `manager_phone` directly on `session_slots`. The `tutors` table, the `session_tutor_assignments` table, the expected/actual status distinction, and cover-event detection are all removed. The catering workflow needs the manager's contact details only — that's the entire surface. Cover events return in V3 if the sick-tutor-cover workflow is added.

**ADR-018: Caterer-school capability as time-bounded rows.** **CUT.** V2 has `schools.current_caterer_id` and nothing else. The `caterer_school_capabilities` table, the `effective_from`/`effective_to` columns, the `status` enum, the `day_of_week` granularity, and the `preference_rank` ordering are all removed. V2 escalates when the primary caterer doesn't respond; routing to alternates is the V3 addition that needs the capability table.

**ADR-019: Menu item snapshot pricing via effective_from / effective_to.** **SIMPLIFY.** V2 has no menu price history. Menu item rows are mutable; the only price snapshot kept is the total cost on the order at composition time. The `unit_price_at_order_cents` column on order lines is moot because there are no order lines. If V3 demonstrates a real need for menu price reconstruction (rotation analysis with comparative cost history is a candidate), the price history columns return.

**ADR-020: MOQ rules per caterer with variety scaling.** **SIMPLIFY.** V2 keeps the variety-tiered MOQ logic but stores it as three denormalised columns on `caterers` (`moq_4_items`, `moq_5_items`, `moq_6_items`) rather than a `caterer_moq_rules` table. The data has exactly three tiers, the tiers are fixed across all caterers, and a rules table buys nothing at this volume.

**ADR-021: Order lines at per-student granularity with `session_id` denormalised.** **SIMPLIFY.** V2 keeps per-student granularity but collapses to `meal_assignments` JSON on `orders`. The `order_lines` table is removed along with the `line_purpose` enum, the `submission_token` per line, and the denormalised `session_id`. Feedback attribution via submission_token is also cut because feedback collection itself is cut.

**ADR-022: Polymorphic feedback table with submission_token.** **CUT.** V2 does not collect feedback. The `feedback` table, the `feedback_extracted_signals` table, the LLM extraction pipeline, and the token-based source resolution are all removed. The feedback loop is the clearest V3 candidate after rotation — both are explicitly mentioned in the brief as problems the operation faces.

**ADR-023: Walk-up events with anonymous name → resolved enrolment.** **CUT.** V2 does not model walk-ups. The operational margin absorbs walk-ups silently; the `walkup_events` table, the `walkup_student_name` field, the `resolved_enrolment_id` field, and the resolution workflow are all removed. Per-parent reliability statistics are cut along with the walk-up tracking they depended on. V3 brings walk-up modelling back if the operational margin proves insufficient or per-parent reliability metrics earn their place.

**ADR-024: Absences and exclusions traced to source emails; exclusions at year-level granularity.** **SIMPLIFY.** V2 keeps `source_email_filename` on absences (a filename string, not a foreign key to a table) and keeps the whole-session vs partial exclusion distinction with year-level granularity. What's removed: the `raw_absence_notifications` table (the verbatim/structured split), the `exclusions.superseded_by_id` supersession mechanism, and the source_email_id foreign key (because there's no incoming_emails table). Exclusion reversals in V2 are handled manually by deleting the exclusion row.

**ADR-025: Agent runs / decision logs (self-referencing tree) / escalations as three-tier observability.** **SIMPLIFY.** V2 has `agent_runs` and `agent_steps` (flat, no tree). The `decision_logs` table with `parent_decision_id` self-reference is collapsed into `agent_steps`. The separate `escalations` table with its own lifecycle (open / acknowledged / in_progress / resolved / superseded) is removed; escalation is a `severity = 'escalation'` value on `agent_steps` plus an `escalation_reason` field on `orders`. The tree structure was the strongest argument for keeping the V1 shape — for the heats decision log, a chronological flat list is materially easier to render and to read. If the heats demo reveals reasoning chains that would have benefited from explicit hierarchy, V3 brings back the parent reference.

**ADR-026: Cross-entity references as JSON soft refs.** **SIMPLIFY.** V2's `agent_steps` has `tool_input` and `tool_output_full` as JSON columns; entity references appear inside these payloads naturally rather than as a separate `referenced_entities` field. The convenience of an explicit references column is real for forensic queries but not load-bearing for the heats demo.

---

## Section 3 — Data Ingest

**ADR-027: VO annotation interpreted as caterer capability, not vegetarian status.** **KEEP.** V2 has `vegetarian_option_available` and `is_vegetarian` as separate boolean columns on menu items. The substitution decision lives on `meal_assignments` as a `vegetarian_substitution` flag per assignment. The order email body makes the swap explicit to the caterer.

**ADR-028: Halal status derived as "any non-pork meal".** **KEEP** (with reduced ambiguity handling). V2 derives halal from the absence of pork. Ambiguous-protein items (e.g. `Spaghetti meatballs`) are resolved by a human at ingest, with the conservative default being `contains_pork = 1` until the actual recipe is confirmed. The automated `dietary_resolution_status = 'pending'` mechanism is cut — V2 does not have a "pending" state at runtime. If V3 introduces a high-volume menu ingest pipeline, the pending mechanism may return.

**ADR-029: GYG "$50 per trip" interpreted as per-school-per-trip.** **KEEP.** V2's `caterers.delivery_fee_structure` includes the `per_school_per_trip` option, and GyG is configured this way.

**ADR-030: GST normalised to ex-GST cents for all caterer comparison.** **SIMPLIFY.** V2 stores price as-given with a `price_includes_gst` flag and normalises in code at the point of comparison. The "store one canonical form" decision is reversed because the per-order total cost is what matters operationally, and the comparison happens at runtime in the matcher, not as a stored value.

**ADR-031: Student keying by (school, name) at ingest, no automatic identity merge.** **SIMPLIFY.** V2 goes further than V1 — there is no `students` table at all. Each enrolment is its own row carrying the student's name. Cross-school identity resolution is deferred to V3 if it earns the addition; for V2, two enrolments with the same name at different schools are treated as two unrelated rows. The `student_identity_merge` table V1 deferred is also cut from V2's scope, not just from V2's build.

---

## Section 4 — Deferred Scope (already not-built in V1)

These were deferred in V1 and remain deferred in V2. They are listed here for completeness rather than for fresh cutting.

**ADR-032: Parents as first-class table.** **CUT (changed from V1).** V1 corrected the original brief by promoting parents to first-class; V2 reverses this. Parent contact lives as two text columns (`parent_email`, `parent_name`) on the enrolment. The argument for first-class parents was per-parent reliability statistics across enrolment changes — V2 doesn't track those statistics, so the argument falls away. Re-promote in V3 if reliability metrics return.

**ADR-033: School attributes table.** **CUT (matches V1).** V2 has no school_attributes table. Operational details that vary per school live in the agent's prompt context.

**ADR-034: `actual_paid_cents` fabricated demo column.** **CUT.** V2 does not have a payment column at all. The argument for a demo column was narrative completeness; V2's demo narrative is order-to-delivery, not order-to-payment. Payment integration is V3 at earliest.

**ADR-035: Buffer auto-tuning loop.** **CUT (matches V1).** Auto-tuning is deferred, and V2 additionally cuts the `session_reconciliations` table that V1 retained as the data substrate for future tuning. V2 has no reconciliation collection at all — the operational margin is a constant, not an adjustable parameter. Reconciliation returns in V3 alongside the tuning loop.

**ADR-036: Tutor groups / teams modelling.** **CUT (matches V1).** V2 has no tutors table whatsoever (see ADR-017), so the team modelling question is moot.

**ADR-037: `outbound_emails` as first-class table.** **CUT (changed from V1).** V1 corrected the original brief by promoting outbound_emails to first-class; V2 reverses this. The rendered email body lives directly on the `orders.email_body` column. The audit chain V1 wanted (outbound_emails → email_templates → decision_logs → agent_runs) is reduced to a simpler chain: the order row carries the body and the agent_step that composed it logs the action. The `email_templates` table is cut; V2's templates live as Python format strings in the codebase.

**ADR-038: Escalation re-notification logic.** **CUT (matches V1).** V2 raises escalations once. No re-notification, no severity-based cadence, no state machine on escalations. The `escalations.state` lifecycle V1 built (open / acknowledged / in_progress / resolved / superseded) is cut along with the escalations table itself; severity is a value on agent_steps and a reason text on orders.

**ADR-039: User / auth table.** **CUT (matches V1).** V2 has no users table. Operator identity on resolution actions is also cut because V2 has no resolution actions to record.

**ADR-040: Email attachment binary storage.** **CUT (matches V1).** V2 doesn't store attachment metadata either, because the `incoming_emails` table is cut entirely; attachments arrive as files alongside their parent emails in `emails/incoming/` and are inspected directly if needed.

**ADR-041: PII redaction and data retention.** **CUT (matches V1).** Same posture as V1 — V2 is not production-deployed, and PII handling is acknowledged in the memo as a precondition for any real deployment.

**ADR-042: Caterer rotation explore/exploit.** **CUT (matches V1, and further).** V1 deferred the explore/exploit framing but still surfaced reactive rotation proposals when decline conditions triggered. V2 cuts reactive rotation too — there is no decline detection in V2, so there is no trigger to react to. Rotation in any form is V3.

**ADR-043: "Why did you do this?" coordinator query interface.** **CUT (matches V1).** The HTML decision log is the only operator surface in V2; ad-hoc query interfaces are V3 at earliest.

**ADR-044: What-if rotation simulator.** **CUT (matches V1).** Rotation itself is cut, so a simulator over rotation is doubly out of scope.

**ADR-045: Anomaly detection on input changes.** **CUT (matches V1).** V2 has no anomaly detection. Operators notice anomalies through routine review.

**ADR-046: HTML demo surface as the V1 operator view.** **KEEP.** V2 keeps the regenerated HTML decision log. It is the demo surface, the operator surface, and the "Build Artifact" deliverable. Colour-coding by severity, timeline layout, escalations highlighted at the top.

---

## Summary of cuts, grouped by theme

**Predictive / learning systems removed entirely.** Absence prediction, walk-up prediction, buffer auto-tuning, anomaly detection, feedback signal extraction. V2 uses fixed margins and direct data; learning waits for V2's operation to demonstrate where the constant is wrong.

**Caterer relationship layer removed entirely.** Scorecards, decline detection, rotation proposals, capability tracking with time bounds and day-of-week granularity, alternate caterer enquiries. V2 escalates and lets the human decide; the rotation mechanism is the strongest V3 candidate because the brief explicitly names food-quality decline.

**Feedback loop removed entirely.** No student ratings, no parent comments, no manager session reports, no LLM signal extraction, no per-line submission tokens, no per-parent reliability metrics. V2 sends the order; what happens to the meal after delivery is out of scope. Feedback is the second-strongest V3 candidate.

**Identity layers collapsed.** Students table removed entirely (enrolment carries name). Parents table removed (enrolment carries contact). Tutors table removed (session slot carries manager name and phone). Users/auth deferred. Each of these is a one-row-per-distinct-person abstraction that earns nothing without cross-reference queries V2 does not run.

**Junction tables collapsed.** Dietary tag tables, caterer capability table, MOQ rules table, session-tutor assignments, order lines. Each is replaced by either a JSON column, a set of denormalised columns, or removal of the modelled relationship. The data volume at heats scale does not earn the joins.

**Lifecycle/temporal modelling removed.** Enrolment start/end dates, menu price effective dates, capability effective dates, exclusion supersession, escalation state machine. V2 runs against the current term; history is not modelled.

**Observability tree collapsed.** Decision logs as a self-referencing tree become a flat agent_steps table. Cross-entity reference column on decisions becomes ad-hoc JSON inside tool input/output payloads. The HTML decision log survives because it is the demo.

**Trigger model simplified.** Hybrid trigger (scheduled + event + threshold) becomes one scheduled trigger that does ingest at the start of each run.

**Model stack simplified.** Sonnet + Haiku routing becomes Sonnet only.

**Email layer simplified.** Incoming and outbound emails tables removed; raw incoming emails live as files, rendered outgoing emails live on the order row. Email templates live in code, not in a database table.

---

## What survives, named explicitly

The full set of decisions V2 commits to is documented in `summary_v2.md` (what the system does) and `schema_v2.md` (the ten-table data model). The five durable architectural commitments are:

A single SQLite database as the source of truth, shared across all components. A Python tool layer of typed deterministic functions that the agent calls. Claude Sonnet 4.6 invoked via the Anthropic SDK's tool-use loop, with a per-phase cap of ~15 tool calls. Simulated email I/O via filesystem folders, with the rendered body of each outgoing message stored on the corresponding `order` row. A regenerated HTML decision log written after every run, sourced entirely from the `agent_runs` and `agent_steps` tables, colour-coded by severity, opened in a browser as a flat file.

Everything else in V2 — the schema shape, the workflow steps, the escalation triggers — derives from these five commitments meeting the heats deliverable.
