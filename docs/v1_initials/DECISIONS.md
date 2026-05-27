# DECISIONS.md — Padea Operations Agent

**Purpose.** Architectural Decision Records (ADRs) for the V1 build. Each entry captures one decision, the alternatives that were live at the time, and what each commits us to. The alternatives sections are the most important part of this document — they are where the "delete first, then add back if needed" thinking lives, and they record options that don't survive into the final schema or code but shaped how the surviving design was chosen.

**Status convention.** *Accepted* = committed in V1. *Deferred* = consciously parked, no V1 implementation. *Superseded* = an earlier decision replaced by a later one in the same register.

**Sources.** `v1_summary.md`, `schema_v1.dbml`, `data_observations.md`, `assumptions.md`, `requirements_v1.md`.

---

## Section 1 — Architecture

### ADR-001: Hybrid trigger model for agent runs

**Status:** Accepted
**Date:** Day 1
**Context:** The agent has work that recurs on a fixed cadence (composing the weekly order on Monday for the following week) and work that arrives unpredictably mid-week (absence notifications, caterer responses, exclusion submissions). How should the agent be triggered?
**Decision:** A hybrid model. A scheduled trigger runs the weekly composition. Event-based triggers run on incoming email arrival, on operator form submission (exclusions), and on threshold conditions (caterer non-response past expected confirmation deadline). The `agent_runs` table records the trigger type, detail, and intended purpose per run.
**Alternatives considered:**
- *Pure weekly batch* — every action gathered into one Monday run. Rejected because mid-week absences and caterer non-responses are time-critical; deferring them to the next Monday would cause meals to be wasted or sessions to run without food.
- *Pure event-driven* — every run triggered by an external event. Rejected because the weekly composition window is genuinely time-driven (the caterer needs the order with adequate lead time) and there is no triggering event to hang it off other than "it's Monday".
**Consequences:** The `agent_runs` table must distinguish trigger types (scheduled, email_inbound, operator_form, threshold). Replays must be reproducible given the trigger and the input snapshot at that time, hence the `trigger_context` field. Failure-mode handling differs by trigger: a missed scheduled run requires catch-up logic; a missed event-driven run requires retry from the source event.
**Out of scope as a result:** No queue infrastructure (Celery, RQ, etc.) in V1 — triggers fire the agent process directly.

---

### ADR-002: Per-student labelled meal manifest, not anonymous bulk

**Status:** Accepted
**Date:** Schema design
**Context:** When the agent composes an order, each line could either name the student the meal is for, or describe only the aggregate (e.g. "30 chicken wraps, 4 vegetarian, 2 gluten-free"). Which level of granularity does the system store and send?
**Decision:** Per-student lines. The `order_lines` table carries `enrolment_id` for every standard and dietary line, so the order is an explicit manifest of which meal is for which student. Margin and tutor-buffer lines exist as separate line purposes with `enrolment_id` null.
**Alternatives considered:**
- *Aggregate-only orders* — the order is a count by menu item, with student matching happening on site. Rejected because dietary safety requires the system to commit to who is getting which meal *before* the meal is prepared. An aggregate order makes the safety floor unverifiable. It also makes feedback attribution (which student ate what) impossible without a separate manifest.
- *Aggregate to caterer, manifest internally* — the caterer sees totals; Padea holds the manifest. Rejected because the labelled meals are also the mechanism by which students get the specific item they selected within their parent-approved set. Anonymous bulk delivery defeats the per-student selection model in ADR-004.
**Consequences:** `order_lines` rows are first-class records, each with a `submission_token` that resolves a future feedback submission back to the specific line, student, and menu item. Caterer-facing communication has to make the manifest legible; templates render the per-session breakdown in the outbound order email.
**Out of scope as a result:** Anonymous walk-up handling within a "free meals" buffer — every meal is meant for someone specific, with margin lines explicitly identified as buffer rather than as unallocated stock.

---

### ADR-003: Confidence-aware escalations with configurable thresholds

**Status:** Accepted
**Date:** Day 1
**Context:** The agent has to decide when to act autonomously and when to defer to the human approver. A binary approve/reject gate at every decision would create a bottleneck; never deferring would put the system out of bounds where it shouldn't be.
**Decision:** Each agent decision is tiered (routine / notable / escalation) with the tier driven by both the decision type and a confidence score derived from inputs. Escalation thresholds are configurable per decision type — e.g. order auto-send may be enabled per `(caterer, school)` with a graduated trigger. Below threshold, the agent proceeds; above threshold, it raises an escalation record with pre-drafted action options.
**Alternatives considered:**
- *Binary approve/reject on every action* — every order, every absence, every reconciliation requires operator sign-off. Rejected as a re-implementation of the bottleneck the system exists to remove (see Requirement §The coordinator out of the bottleneck).
- *Fully autonomous with retrospective review* — agent acts; operator reviews afterwards. Rejected because the decisions that require human judgement (caterer rotation, dietary edge cases, contract anomalies) cannot safely be performed and then reviewed; the action itself is the irreversible step.
**Consequences:** `decision_logs.tier` and `escalations.severity` carry per-instance values, not per-type. Escalations deduplicate via `match_key` so recurring conditions produce one escalation with a recurrence count rather than weekly noise.
**Out of scope as a result:** A separate "approval queue" UI — escalations are surfaced through the HTML run log only.

---

### ADR-004: Preference capture at term start + student weekly selection within parent-approved set

**Status:** Accepted
**Date:** Day 1
**Context:** The system needs to know what each student is willing to eat. The capture mechanism has to be light enough that households actually engage and structured enough that the matching engine has something to read.
**Decision:** Two-stage capture. At term start, the parent receives a per-child list of menu items pre-filtered for that child's dietary requirements, and marks each item as acceptable or not. This forms the per-student menu universe for the term. Each week, the student picks one item per session from within their parent-approved set (`student_session_selections`).
**Alternatives considered:**
- *Weekly polling of parents only* — the parent picks the specific meal each week. Rejected as too high-touch; response rates would drop and the system would default to "any acceptable" most of the time anyway. Also takes the choice away from students, which is itself a small re-enrolment factor.
- *Student-only selection at point of session* — student picks at the start of the session. Rejected because the order has to be composed days earlier with the meal already specified. The economic case for the caterer-side variety constraints requires per-meal counts at order time, not at session time.
- *No capture; system assigns based on dietary tags only* — rejected on the grounds of Requirement §Meals students want to eat: dietary compliance is necessary but not sufficient for re-enrolment value.
**Consequences:** `term_preference_selections` carries the parent's per-item acceptability per term; `student_session_selections` carries the student's weekly choice. Defaults exist: a student who hasn't selected falls back to a prior week or to a system pick within the parent-approved set (`selected_by` field captures which). Mid-term enrolments hit a manual-decision state for their first session until the term-start flow completes, which v1_summary acknowledges as a weak point.
**Out of scope as a result:** Direct student preference capture without parent gate (V1 routes through the parent contact in every case).

---

### ADR-005: Calendar-feature-based walk-up prediction; ML prediction for absences

**Status:** Accepted
**Date:** Schema design
**Context:** Operational margin sizing depends on two predictions: how many notified students will walk in anyway (walk-ups), and how many additional absences will arrive mid-week. Both could be hand-tuned rules or model outputs.
**Decision:** Both predictions are model outputs with stored `feature_snapshot` for reproducibility (`absence_predictions`, `walkup_predictions`). Features include trailing per-school rates, day-of-week, calendar-week-of-term, exam-period flag, end-of-term flag, public-holiday adjacency. The model itself is light (v1_summary doesn't commit to a specific algorithm) but the table structure supports replacing the model later.
**Alternatives considered:**
- *Hand-coded calendar rules in code* — "+1 meal during exam week, +2 around end of term". Rejected because rule maintenance scales with the calendar complexity, and the per-school rate is a meaningful feature that rules can't capture without becoming a model in disguise.
- *No prediction; fixed margin* — every session gets the same +2 buffer. Rejected because the variance across schools and weeks is large enough that a uniform margin either runs short routinely or carries an expensive average overhead.
- *Heavyweight ML pipeline (training infrastructure, MLflow, etc.)* — rejected as overkill for V1; a single feature snapshot + model version per prediction is enough to support reproducibility without operationalising an ML stack.
**Consequences:** Both prediction tables follow the same structure (input features, model version, confidence, output). Term-end reports include prediction-vs-actuals.
**Out of scope as a result:** Live model retraining inside the agent loop; V1 retrains offline.

---

### ADR-006: Tutor meals as a designed primitive, not a "use leftovers" hack

**Status:** Accepted
**Date:** Schema design
**Context:** Tutors managing sessions also need to eat. They could be served from leftover meals (when there are leftovers), from a separately-ordered allocation, or with no formal handling at all.
**Decision:** `orders.tutor_buffer_meals_per_session` carries an explicit per-session count of tutor meals composed into the order. `order_lines` has `line_purpose = 'tutor_buffer'` for these lines. They are first-class items, not leftover handling.
**Alternatives considered:**
- *Leftover handling only* — tutors eat whatever margin meals weren't claimed by walk-ups. Rejected because it ties tutor experience to the operational tail (sometimes they eat, sometimes they don't), which doesn't fit the "tutors are part of the operation" framing. Also makes the order count harder to reason about (the same line is both safety margin and tutor allocation depending on outcome).
- *Out-of-band ordering* — tutors order separately on the day. Rejected as friction for the session manager and a fragmentation of the catering relationship per caterer.
**Consequences:** The economics of an order include the tutor buffer explicitly, which makes the per-meal cost reasoning honest. Term-end reports surface tutor buffer utilisation rates. The buffer is sized per-session-flat: `orders.tutor_buffer_meals_per_session` is a single integer per session regardless of how many tutors are assigned, configured per school.
**Out of scope as a result:** A separate "tutor meals" sub-system or a separate purchasing flow.

---

### ADR-007: Measured-performance food quality system, not coercive caterer management

**Status:** Accepted
**Date:** Day 1
**Context:** Caterer quality drifts downward once a caterer is comfortably established (per Requirement §Quality maintained over time). The system needs a mechanism to keep quality up. Some framings are coercive ("threaten rotation"), some are coordination-based ("measure, expose, let market dynamics work").
**Decision:** A measured-performance model. Each caterer has a scorecard (`caterer_scorecard_snapshots`) snapshotted weekly, accessible to the caterer via a tokened URL. The scorecard shows their own aggregated performance over time; individual student identities and other caterers' scores are never exposed. Internal to Padea, a comparative dashboard surfaces caterers side-by-side. The discipline mechanism is the existence of the measurement and the credibility of alternatives (which the capability table preserves), not a threat.
**Alternatives considered:**
- *Explicit performance threats / SLA penalties* — written into the relationship, financial consequences for missing thresholds. Rejected because the relationships are still small-business commercial relationships; introducing penalty structures creates a different relationship type. The system's role is to maintain the conditions under which the existing relationship works.
- *No measurement; rotate when complaints accumulate* — rejected because complaints lag the underlying decline by weeks, and the decline-detection requirement is specifically that the system prevents prolonged decline rather than just detecting it.
- *Internal-only measurement* — caterers don't see their scorecard. Rejected because the visibility to the caterer is the incentive: a caterer who knows their performance is being measured and shown to them is structurally different from one who doesn't.
**Consequences:** `caterer_decline_signals` runs a two-condition rolling-window trigger (1-stddev drop in 4-week mean vs prior 12-week, AND current score below per-caterer configured floor). When triggered, a rotation proposal is drafted with comparative analysis and pre-drafted enquiry emails to alternatives. Rotation is never automatic.
**Out of scope as a result:** Penalty calculation, contractual SLA management, autonomous rotation, public ranking of caterers against each other.

---

### ADR-008: SQLite for development, Supabase Postgres mirror at submission

**Status:** Accepted
**Date:** Day 1
**Context:** The database needs to be runnable locally for development and demo, and also accessible from a hosted environment for the submission. Building directly against a hosted Postgres adds latency and account-management friction during a build week; building only against SQLite raises portability concerns for the deliverable.
**Decision:** SQLite is the local store during development. At submission, the schema and seed data are mirrored to a hosted Supabase Postgres instance. The schema is written to be compatible with both (integer auto-increment PKs, TEXT-stored timestamps and JSON where applicable, no dialect-specific features).
**Alternatives considered:**
- *Build against hosted Postgres from day 1* — rejected because the local development loop becomes slower and any network-flaky day blocks progress. Also adds a credential to manage from the start.
- *SQLite only* — rejected because the deliverable benefits from a hosted demo URL where judges can probe the database without running anything locally.
- *Postgres locally via Docker* — rejected as additional infrastructure for marginal benefit during the build week; the SQLite-Postgres difference is small enough that mirroring at submission is cheaper than running both locally.
**Consequences:** Schema migrations must be applied to both substrates. Column types are chosen for cross-compatibility (`text` everywhere a TEXT/VARCHAR distinction would exist; `int` for booleans where Postgres-native BOOLEAN would otherwise be used in some columns — though the schema uses native `boolean` in DBML, which both substrates handle). UUIDs were considered (see ADR-011) and rejected in favour of integer auto-increment.
**Out of scope as a result:** Multi-database read replication, sharding, or any other Postgres-only feature.

---

### ADR-009: Email I/O simulated via filesystem in V1

**Status:** Accepted
**Date:** Day 1
**Context:** The agent reads incoming emails (absences, caterer responses, feedback) and sends outgoing emails (orders, escalation notifications, parent forms). Real Gmail or SMTP/IMAP integration would consume a meaningful share of build-week budget without changing the agent's decision logic.
**Decision:** Email I/O is simulated through filesystem-backed inboxes and outboxes. Incoming messages are dropped into a directory the agent polls; outgoing messages are written to a directory and to the `outbound_emails` table. All outbound send routes through a single `email_out` tool, so swapping in real SMTP later is a one-tool change rather than a code sweep.
**Alternatives considered:**
- *Real Gmail integration from day 1* — rejected as build-time cost. OAuth, refresh tokens, label management, and the asymmetry between sending and receiving authentication would absorb time better spent on the agent logic itself.
- *In-memory mock with no persistence* — rejected because the simulated emails need to survive across runs (so a Monday composition can read a Friday absence notification), and a filesystem store is the simplest persistence that meets that bar.
**Consequences:** `incoming_emails` captures the verbatim message before any classification or interpretation. The `outbound_emails` table records the rendered body even though no real send occurs in V1. Demo realism: the judges can drop email files into the inbox directory and watch the agent process them.
**Out of scope as a result:** Bounce handling, deliverability, attachment binary processing (metadata only in V1), thread reconstruction (see ADR-039).

---

### ADR-010: Python + Anthropic SDK, Claude Sonnet 4.6 for reasoning, Haiku 4.5 for routing

**Status:** Accepted
**Date:** Day 1
**Context:** Language and model choices for the agent. The build week is short; the deliverable must be runnable; the model selection has to balance reasoning quality against latency and cost.
**Decision:** Python is the implementation language (broad SDK support, fastest path through the data layer). The Anthropic SDK drives the agent loop. Sonnet 4.6 is used for reasoning-heavy decisions — order composition, escalation analysis, dietary edge-case resolution. Haiku 4.5 handles classification, routing, and lightweight extraction (e.g. incoming email classification into the `classification` field).
**Alternatives considered:**
- *Single-model approach (Sonnet for everything)* — rejected because the routing and classification volume is high enough that latency and cost matter; Haiku's quality is sufficient for the routing decisions it handles.
- *Single-model approach (Haiku for everything)* — rejected because the reasoning-heavy decisions (variety pruning under MOQ constraint, escalation drafting, term-end reasoning) need Sonnet's depth.
- *Non-Anthropic stack* — out of scope for this competition.
- *Node/TypeScript instead of Python* — rejected because the data layer work (SQLite, pandas-style transforms during ingest) is faster in Python and the team comfort favours it. Python was the explicit choice.
**Consequences:** `agent_runs.model_identifiers` carries the model names used per run; replay reproducibility depends on the model identifier being stable. Cost reporting per run is feasible from the model identifier field plus token counts. Tool calls are bounded at a per-run cap (~15-20) to prevent runaway loops.
**Out of scope as a result:** A multi-vendor abstraction layer for swapping providers.

---

## Section 2 — Schema

### ADR-011: Integer auto-increment primary keys, not UUIDs

**Status:** Accepted (supersedes an earlier register entry)
**Date:** Schema design
**Context:** Every entity needs a primary key. The earlier decision register draft mandated UUIDs on integrity grounds (cross-school name collisions, opaque identifiers). The schema-as-built uses integer auto-increment.
**Decision:** Integer auto-increment primary keys for every table. Cross-school name collisions are handled by `enrolment_id` being the operational key (see ADR-014), not by primary key opacity.
**Alternatives considered:**
- *UUIDs everywhere* — the earlier register's position. Stronger against export-merge collisions but the V1 system has no export-merge flow. Rejected because the integrity argument is hypothetical until a second system exists to merge with, and integer keys are noticeably easier to debug during the build week (an integer in a log line is readable; a UUID is not). The collision-resistance benefit was load-bearing for the assumed export scenario but the export scenario isn't V1.
- *Composite natural keys (school + student name + year)* — rejected. Cross-school name matches exist in the data (13 cases), and natural keys collapse identities at exactly the wrong point.
**Consequences:** `student_id`, `enrolment_id`, `caterer_id`, etc. are integers throughout. The cross-school identity question is handled at the enrolment level: each (student, school, period) is a distinct enrolment row, so two students with the same name at different schools have different `enrolment_id`s without needing UUID opacity. Identity merge is handled by adding a `student_identity_merge` table (see ADR-031), not by retrofitting UUIDs.
**Out of scope as a result:** UUID-based replication, merge-by-UUID logic, opaque external-facing IDs (V1 internal IDs are integers; any external-facing token uses a separate `share_url_token` or `submission_token` field).

---

### ADR-012: Sessions stored as individual dated rows, not as recurring templates

**Status:** Accepted
**Date:** Schema design
**Context:** Padea sessions follow a recurring pattern: each school runs sessions on specific days of the week. The schema could store the pattern (school + day-of-week + start time) and derive concrete sessions, or store each dated instance as a row.
**Decision:** Concrete dated session rows. Each row in `sessions` is a specific date, with `session_start`, `session_end`, `dinner_start`, `dinner_end` as actual timestamps for that date. Recurrence patterns are inferred from the data, not stored.
**Alternatives considered:**
- *Recurring pattern as the primary entity* — store the school's session schedule once, derive sessions on demand. Rejected because exceptions are routine (exclusions, room changes, occasional rescheduling) and every exception would require either an override row or pattern mutation. With dated rows, the exception is just an edit to the specific row.
- *Hybrid — pattern + override rows* — rejected because the join logic to resolve "what is the actual session on this date?" becomes a tree of pattern + overrides, which is slower to query and harder to reason about than a flat table of concrete rows.
**Consequences:** A 12-week term produces ~12 rows per session-day per school. The session row carries `dinner_end` as a stored timestamp even though it's structurally derivable from `dinner_start + 30 minutes` (per assumption A21); the storage cost is trivial and the explicitness aids the join logic.
**Out of scope as a result:** A "session series" entity. If V2 wants pattern-aware queries, they can be derived from the concrete rows.

---

### ADR-013: Enrolment lifecycle via start_date / end_date, no current/historical split

**Status:** Accepted
**Date:** Schema design
**Context:** Students enrol, leave, and sometimes re-enrol. The lifecycle could be modelled with separate "current_enrolments" and "historical_enrolments" tables, or with date-bounded rows in a single table.
**Decision:** Single `enrolments` table with `start_date` and `end_date`. A null `end_date` means the enrolment is current. Re-enrolment after a gap is a new row, not a reactivation.
**Alternatives considered:**
- *Current vs historical split* — rejected as duplication of structure for marginal query convenience. The "current enrolments" view is a one-line `WHERE end_date IS NULL OR end_date > today`.
- *Status enum (active / inactive / suspended)* — rejected because the temporal information is more useful than the status (knowing *when* an enrolment ended matters for absence-period reasoning, fee questions, and reconciliation against the source records).
**Consequences:** Queries that need the current cohort filter on `end_date IS NULL`. Year level lives on the enrolment, not the student, so a student progressing from Year 11 to Year 12 produces a new enrolment row with the new year level (see ADR-014). `enrolment_history` captures mutations on the enrolment row itself (dietary tag changes, opt-out toggles).
**Out of scope as a result:** A status-machine enforcement layer. The temporal bounds are the source of truth.

---

### ADR-014: Enrolment as the first-class entity for year-level, opt-out, dietary, parent

**Status:** Accepted
**Date:** Schema design
**Context:** The same student can appear at two schools with different dietary disclosures (Benjamin Wilson: "No Beef" at JPC, blank at ISHS) and different parent contacts. Where do these contextual attributes live?
**Decision:** On the enrolment, not the student. `enrolments.year_level`, `enrolments.opted_out`, `enrolments.parent_id`, and `enrolment_dietary_tags` are all per-enrolment. The `students` table holds only name and (optional) date of birth — the sparse identity.
**Alternatives considered:**
- *Student-level attributes* — store year_level, opt-out, dietary on the student. Rejected because of the divergent-disclosure case in the source data; storing dietary on the student would force a reconciliation we cannot perform safely.
- *Mixed (some on student, some on enrolment)* — rejected because the principle is cleaner if applied uniformly: anything that can vary by school context lives on the enrolment.
**Consequences:** Matching, ordering, dietary safety checks, and feedback all join through enrolment. The student record is small and immutable; the enrolment record is where operational reality is recorded. Identity merge (if V2 confirms two students at different schools are the same person) operates on the student record without disturbing per-enrolment disclosures.
**Out of scope as a result:** Any "global preferences" concept that applies to the student across all schools.

---

### ADR-015: Controlled dietary vocabulary in a tag table + junction mapping

**Status:** Accepted
**Date:** Schema design
**Context:** The source data records dietary requirements as free text — 18 distinct cell values across 320 enrolments, some comma-grouped, with overlapping concepts (`Halal` separate from `No Pork`). The matching engine needs to read structured dietary data, not parse text at every check.
**Decision:** A `dietary_tags` table holds the controlled vocabulary (one row per atomic dietary concept). `enrolment_dietary_tags` is a junction table linking enrolments to their tags, with a per-link `severity` field (preference / allergy / anaphylaxis) and `recorded_at`. Menu items have parallel tables (`menu_item_contains` for positive ingredient attributes, `menu_item_suitable_for` for resolved suitability flags) using the same `dietary_tags` rows.
**Alternatives considered:**
- *Decomposed boolean columns on the enrolment* — one `requires_halal` column, one `excludes_pork` column, etc. The earlier register draft proposed this for matching speed. Rejected for V1 because the controlled-vocabulary approach is more extensible (a new dietary concept requires one row in `dietary_tags`, not a schema migration), and the query-speed difference at this data volume is negligible.
- *Free-text dietary column* — keep the source data as-is. Rejected: requires parsing at every match point, and dietary safety is the single most safety-critical operation; a parser at the matching boundary is a worse failure surface than a parser at ingest.
**Consequences:** Ingest maps each source dietary string to one or more rows in `dietary_tags` via a mapping function. Unmapped strings escalate. The same `dietary_tags` table governs ingest, matching, and analytics (e.g. "how many enrolments require halal" is a count query, not a text search). `is_safety_critical` distinguishes allergy-level tags from preference-level tags for the dietary-safety floor.
**Out of scope as a result:** Inline string-based dietary checks anywhere in the agent code.

---

### ADR-016: Three separate junction tables for dietary attributes, not one polymorphic table

**Status:** Accepted
**Date:** Schema design
**Context:** Three different entity types (enrolments, menu items in their positive-ingredients sense, menu items in their suitability sense) all link to `dietary_tags`. A polymorphic `tag_assignments` table with a `target_type` discriminator could replace the three separate tables.
**Decision:** Three separate tables: `enrolment_dietary_tags`, `menu_item_contains`, `menu_item_suitable_for`. The first two carry parallel semantics for different entities; the third is derived from the second at ingest.
**Alternatives considered:**
- *Single polymorphic `tag_assignments` table* with a `target_type` discriminator and a `target_id` column. Rejected because polymorphic associations in SQL break foreign-key integrity (the database can't enforce that `target_id` points to a valid row in the type-appropriate table), and the readability of joining queries suffers. The three tables are small enough that the duplication doesn't matter.
- *One big "everything has a dietary profile" table* — combines enrolments and menu items into one structure. Rejected because the semantic difference between "enrolment requires/excludes" and "menu item contains/is suitable for" is real, and merging them would force a single set of fields that doesn't fit either case well.
**Consequences:** Joins are typed and the database enforces referential integrity in both directions. Each table can carry table-specific fields (severity on `enrolment_dietary_tags`, an effective-dated field on menu item tables if needed later) without bloating the others.
**Out of scope as a result:** A generic tag system applicable to non-dietary attributes.

---

### ADR-017: Tutor managers via expected/actual rows in `session_tutor_assignments`

**Status:** Accepted
**Date:** Schema design
**Context:** A session has a designated manager set in advance. Cover happens — last-minute swaps mean the actual manager may differ from the expected one. Both states need to be captured for accountability and for the cover-event signal.
**Decision:** `session_tutor_assignments` is the single source of truth. The `role` field distinguishes manager from tutor; the `status` field distinguishes expected from actual. A session's expected manager is the row with `role='manager'` and `status='expected'`; the actual manager is the row with `role='manager'` and `status='actual'`. Cover events are detectable as a mismatch.
**Alternatives considered:**
- *Two nullable FK columns on `sessions`* — `expected_manager_id` and `actual_manager_id`. Rejected because (1) it doesn't extend to non-manager tutor cover, (2) it conflates the manager role with the session entity, when conceptually the assignment is the relationship.
- *Separate `cover_events` table* — log only the difference. Rejected because the "no cover" case is then encoded as "absence of a row", which is awkward to query and makes the routine state implicit.
**Consequences:** Manager population and tutor population are unified (per Assumption A17 — managers are tutors carrying a per-session manager role). The same `tutors` table backs both. Querying "who managed this session" is `SELECT tutor_id FROM session_tutor_assignments WHERE session_id = ? AND role = 'manager' AND status = 'actual'`.
**Out of scope as a result:** A separate "managers" table or a dedicated cover-event entity.

---

### ADR-018: Caterer-school capability as time-bounded rows, not a static assignment

**Status:** Accepted
**Date:** Schema design
**Context:** Caterer capability changes — a caterer stops serving a school, gains capacity to serve a new one, is taken off rotation pending review. The capability needs to be queryable at any point in time, not just "current".
**Decision:** `caterer_school_capabilities` carries `effective_from` and `effective_to` per row, with a `status` enum (currently_serving / able_to_serve / previously_served / confirmed_unable) and a `day_of_week` field for day-level granularity (per Assumption A12). Capability is a row, not a flag on the caterer.
**Alternatives considered:**
- *Boolean columns on `caterers`* like `serves_jpc` etc. Rejected as schema-fragile (every new school requires a migration) and unable to capture day-of-week granularity.
- *Single "currently serves" status only, no history* — rejected because rotation analysis depends on knowing when a caterer last served a school, which requires the previous-period rows to persist.
**Consequences:** "Who can serve this school on this day?" is a query against `caterer_school_capabilities` filtered by `status IN ('currently_serving', 'able_to_serve')`, `school_id`, `day_of_week`, and a date-range overlap on `effective_from`/`effective_to`. `preference_rank` orders alternatives when multiple are eligible. The `source` field captures whether the row came from initial data load or from a later capability re-confirmation event.
**Out of scope as a result:** A capacity model (how many meals per day per caterer); V1 treats capability as binary at the (caterer, school, day) level.

---

### ADR-019: Menu item snapshot pricing via effective_from / effective_to

**Status:** Accepted
**Date:** Schema design
**Context:** Menu prices change. Past orders need to reflect the price at the time of the order, not the current price. Future orders need the current price.
**Decision:** `menu_items` carries `effective_from` and `effective_to`. A price change creates a new row (with `effective_to` set on the old row and a fresh row for the new price). `order_lines.unit_price_at_order_cents` separately captures the price at order time, so order economics are reproducible even if the menu item rows are later edited.
**Alternatives considered:**
- *Mutable menu item rows* — rejected because past orders would become misleading if prices changed.
- *Order-line price only, no menu item history* — rejected because some queries (e.g. caterer rotation analysis) need to know what the menu looked like at a given time, not just what individual orders paid.
**Consequences:** Two layers of price record: the menu item rows are the catalogue history; the order_lines field is the transaction history. They are independent — a price could be recorded on the menu item in error and corrected without affecting the order_lines that already captured the executed price.
**Out of scope as a result:** Inflation-adjusted reporting, currency conversion, anything beyond cent-denominated AUD.

---

### ADR-020: MOQ rules per caterer with variety scaling, not per session

**Status:** Accepted
**Date:** Schema design
**Context:** Each caterer has a minimum order quantity that scales with the number of menu items in the order (MOQ-4-items, MOQ-5-items, MOQ-6-items in the source data). The MOQ applies to the weekly total across all sessions a caterer serves, not to a single session.
**Decision:** `caterer_moq_rules` carries one row per (caterer, variety_count → minimum). Order composition reads the rules for the caterer's chosen variety count and compares against the full weekly meal total. The MOQ check happens once per (caterer, week), not per session.
**Alternatives considered:**
- *Per-session MOQ* — rejected because it doesn't match how caterers actually plan (they prepare a week's worth) and would force needless inflation of individual sessions to clear an irrelevant threshold.
- *Single MOQ per caterer (no variety scaling)* — rejected because the source data explicitly records variety-tiered MOQs.
**Consequences:** Composition reads the variety-count chosen, looks up the MOQ for that tier, compares to the total weekly meals (standard + dietary + margin + tutor buffer). Shortfall surfaces as an escalation per Requirement §Reliable meal delivery with the financial cost made explicit. Dietary-specific meals do not count towards MOQ — they are reserved before the standard pool and the MOQ check applies to the standard pool. The dietary safety floor is committed before economic reasoning applies; this is a design decision, not a data-inferred rule.
**Out of scope as a result:** Per-school MOQ within a caterer's weekly total; volume discounts beyond the variety-tier mechanism.

---

### ADR-021: Order lines at per-student granularity, with session_id denormalised

**Status:** Accepted
**Date:** Schema design
**Context:** An order spans a full week and multiple sessions. Each line could represent a per-session aggregate ("12 chicken wraps for ISHS Tuesday") or a per-student line ("chicken wrap for enrolment 47 at session 12").
**Decision:** Per-student lines. `order_lines.enrolment_id` is set for standard and dietary lines; `session_id` is also stored on the line even though it's derivable through the enrolment (denormalised for query speed). `line_purpose` distinguishes standard / dietary / margin / tutor_buffer. Margin and tutor_buffer lines have `enrolment_id` null.
**Alternatives considered:**
- *Per-session aggregate lines* — rejected per the same reasoning as ADR-002 (anonymous bulk).
- *Per-student lines without `session_id`, derive from enrolment* — rejected because the join from enrolment to session would happen on most order queries and a denormalised column avoids it. The risk is the denormalisation becoming stale; in V1 the order line is effectively immutable once written, so this isn't a concern.
**Consequences:** `submission_token` is generated per line for student-served lines and used to attach incoming feedback. The order line is the unit of feedback attribution. Aggregate reporting (meals-per-session) is a group-by query against `order_lines.session_id`.
**Out of scope as a result:** Editing order lines after send; if an absence arrives late, the existing line is preserved and walk-up handling kicks in.

---

### ADR-022: Polymorphic feedback table with submission_token, not type-specific tables

**Status:** Accepted
**Date:** Schema design
**Context:** Feedback in V1 has multiple sources: student rating per meal, manager session report, parent comments on preference selections. Each could have its own table, or they could share one.
**Decision:** A single `feedback` table with `feedback_type` distinguishing the source. `submission_token` resolves the submission back to a specific `order_lines` row, which carries the enrolment, session, and menu item context. The `submitter_id` is *not* stored as a foreign key — the token is the link, with the source resolved through the order line.
**Alternatives considered:**
- *Separate tables per submitter type* — `student_ratings`, `manager_reports`, `parent_comments`. Rejected because the downstream extraction (LLM signal extraction into `feedback_extracted_signals`) operates uniformly across them; the dimensional analysis (taste, portion, temperature) is the same regardless of source.
- *Polymorphic with `submitter_id` as a foreign key* — would require a `submitter_type` discriminator and lose referential integrity for the same reasons as ADR-016. The token-based resolution is cleaner.
**Consequences:** `feedback_extracted_signals` rows reference the feedback row and the (resolved) menu item. The LLM extraction is auditable: `extracted_by_model` and `extraction_version` are stored, so re-extracting with a newer model produces a separate signal row rather than overwriting.
**Out of scope as a result:** Per-type validation rules at the database level (a student rating has different valid ranges than a manager report on dimensions). V1 enforces these in code.

---

### ADR-023: Walk-up events with anonymous name → resolved enrolment flow

**Status:** Accepted
**Date:** Schema design
**Context:** A walk-up is a student who attends a session despite an absence notification (or with no enrolment record at all). The session manager records walk-ups at session end, often by name only, without immediate access to enrolment records.
**Decision:** `walkup_events` carries both `enrolment_id` (set when known) and `walkup_student_name` (the name as the manager recorded it). A `resolved_enrolment_id` field captures the post-hoc resolution, with `resolution_status` indicating whether the resolution happened (resolved / unresolved / ambiguous). The flow accommodates the operational reality that the manager records what they see and resolution happens later.
**Alternatives considered:**
- *Require enrolment_id at write* — rejected because it puts the manager in the position of doing the lookup at session end, which is exactly the kind of friction the system is meant to remove.
- *Free-text walk-ups only, never resolve* — rejected because per-parent reliability statistics (Requirement §Reliable meal delivery, walk-up tracking) depend on knowing which student walked up, which requires resolution.
**Consequences:** Resolution is an operator action (or a background heuristic) that happens after session end. The `walkup_events` row captures both the raw record and the resolution, so the audit trail is preserved. Per-parent stats update on resolution, not on initial walkup capture.
**Out of scope as a result:** Real-time identity matching during the session itself.

---

### ADR-024: Absences and exclusions traced to source emails; exclusions at year-level granularity

**Status:** Accepted
**Date:** Schema design
**Context:** Absence notifications and exclusion submissions need traceability — the system must be able to surface "where did this come from?" for any operational record.
**Decision:** `raw_absence_notifications.source_email_id` and `exclusions.source_email_id` link operational records back to their source incoming email row (the verbatim capture per ADR-035). Exclusions carry `scope` (whole_session / year_level / cohort_subset) with `scope_value` carrying the year level or cohort detail. Reversals of exclusions create a new exclusion row pointed to by `superseded_by_id` on the original, not a mutation.
**Alternatives considered:**
- *No source linkage; treat operational records as primary* — rejected because the "why is this absence recorded?" question would be unanswerable without the email trail.
- *Single absence/exclusion table* — rejected because the lifecycle differs (absences have walk-backs; exclusions have supersession; channels differ).
**Consequences:** The audit chain runs from operational record back to raw notification back to incoming email. Year-level partial exclusions sizing the order to the remaining cohort plus an attendance buffer is straightforward to query from `exclusions.scope = 'year_level'`.
**Out of scope as a result:** Free-text parsing of school exclusion announcements; exclusions reach the system via an operator form per Assumption A31.

---

### ADR-025: Agent runs / decision logs (self-referencing tree) / escalations as three-tier observability

**Status:** Accepted
**Date:** Schema design
**Context:** The system must produce an inspectable record of every meaningful decision (Requirement §Visible operation). The granularity has to support both "what did the agent do this week?" and "why did it pick this specific item for this specific student?".
**Decision:** Three nested levels. `agent_runs` is the top level — one row per triggered run. `decision_logs` records each meaningful decision within a run, with `parent_decision_id` self-referencing to form a tree (a top-level decision spawns sub-decisions and tool calls). `escalations` is a first-class table with its own lifecycle (open / acknowledged / in_progress / resolved / superseded) and a `match_key` for deduplication of recurring conditions.
**Alternatives considered:**
- *Flat event log* — every action a row, no nesting. Rejected because the reasoning chain is lost; reviewing a complex composition becomes a scroll through hundreds of rows without obvious structure.
- *Run + flat decisions* — no nesting in decisions. Rejected because tool calls within a decision (e.g. "look up caterer alternatives" → "compose enquiry email" → "draft escalation") have a parent-child relationship that aids forensic reading.
**Consequences:** The HTML demo surface (per ADR-044) renders the decision tree directly. Routine / notable / escalation tiering is per-decision (the `tier` field) rather than per-type, supporting the same decision type being routine in one context and escalation-worthy in another. `referenced_entities` (see ADR-026) ties decisions to the operational records they touched.
**Out of scope as a result:** A separate "audit log" — the decision logs are the audit log.

---

### ADR-026: Cross-entity references as JSON soft refs, not polymorphic FK tables

**Status:** Accepted
**Date:** Schema design
**Context:** A decision log or escalation can touch many different entity types (an enrolment, a menu item, an order, a caterer). A type-specific foreign key per row is impossible (too many columns); a polymorphic FK table is one option; a JSON column listing referenced entities is another.
**Decision:** `decision_logs.referenced_entities` and `escalations.referenced_entities` are JSON columns carrying a list of `{type, id}` references. They are soft references — the database does not enforce them — but they are sufficient for forensic queries and demo rendering.
**Alternatives considered:**
- *Polymorphic FK tables* — a `decision_log_references` table with `target_type` and `target_id`. Rejected for the same reasons as ADR-016: SQL doesn't enforce polymorphic FKs, and the query convenience of a JSON column for the demo render outweighs the integrity benefit at this volume.
- *Multiple type-specific FK columns* — `referenced_enrolment_id`, `referenced_order_id`, etc. Rejected as schema sprawl; every new entity type would require a column migration.
**Consequences:** Application code is responsible for keeping references valid (deleting a referenced entity doesn't cascade). For V1's demo and operator review use cases, this is acceptable; the references are read for display, not for joining at scale.
**Out of scope as a result:** Cascade-delete logic on referenced entities; if an entity is hard-deleted, references to it become dangling, which is acceptable in V1.

---

## Section 3 — Data Ingest

### ADR-027: VO annotation interpreted as caterer capability, not vegetarian status

**Status:** Accepted
**Date:** Schema design
**Context:** The source menu legend defines `VO` as "vegetarian option". The natural reading is "this item is vegetarian", but the data observations show items annotated `VO` that contain meat — e.g. `Chicken Caesar Salad (VO)`.
**Decision:** `VO` is a caterer-side capability to substitute a vegetarian variant on request, not a property of the listed item. Items marked `VO` are stored with `vegetarian_swap_available = true` on `menu_items`, but `is_vegetarian` in their `menu_item_suitable_for` flags is set based on the actual item, not the swap. A vegetarian student matched to a `VO` item depends on the caterer making the swap, which is tracked separately on the order line (`is_vegetarian_variant`).
**Alternatives considered:**
- *VO = vegetarian* — interpret the annotation as suitability. Rejected because it would put non-vegetarian items into the vegetarian-suitable pool and break the safety floor.
- *Treat VO as unresolved* — flag for human resolution at ingest. Rejected because the legend is clear once read carefully; the resolution is in the data, not pending.
**Consequences:** Order line carries `is_vegetarian_variant` flag so the substitution is explicit in the manifest sent to the caterer. The dietary matcher treats `VO` items as eligible-with-swap for vegetarian students, distinct from items that are inherently vegetarian.
**Out of scope as a result:** Auto-applying the swap without flagging it on the order line.

---

### ADR-028: Halal status derived as "any non-pork meal"

**Status:** Accepted
**Date:** Schema design
**Context:** The source menu legend states explicitly: "Assume all non-pork meals are halal." This is one sentence with broad consequences for the dietary tag matrix.
**Decision:** At ingest, every menu item that does not contain pork is tagged as halal-suitable. `menu_item_contains` carries `contains_pork = true` for the four items where pork appears by name; `menu_item_suitable_for` carries `is_halal = true` for all other items. Items with ambiguous protein source (e.g. `Spaghetti meatballs`) are flagged with `dietary_resolution_status = 'pending'` until human resolution clarifies the protein.
**Alternatives considered:**
- *Require explicit halal certification per item* — rejected because the legend's rule is the operational truth, and requiring certification would block matching for items the legend already covers.
- *Ignore the legend, treat halal as unresolved everywhere* — rejected as ignoring source data; the legend is part of the data.
**Consequences:** Halal compliance for the 16 halal-requiring students is mechanically derivable from the data. Ambiguous-protein items remain unavailable for matching until resolved, which is conservative but acceptable in V1.
**Out of scope as a result:** Halal certification body verification; the legend's rule is taken as authoritative.

---

### ADR-029: GYG "$50 per trip" interpreted as per-school-per-trip

**Status:** Accepted
**Date:** Day 1
**Context:** Guzman y Gomez's delivery fee in the source data is recorded as "$50 per trip". On the Monday GYG delivers to both Loreto and CHAC (per the data observations §Same-caterer concurrent delivery), the interpretation of "trip" matters — is the $50 covering both schools or charged per school?
**Decision:** Per-school-per-trip. A Monday delivering both schools incurs $100, not $50.
**Alternatives considered:**
- *Per delivery run regardless of school count* — $50 for the Monday GYG run total. Rejected. The schema distinguishes `per_trip` from `per_school_per_trip` explicitly; the per-school-per-trip reading is the more defensible interpretation for cost accounting purposes.
**Consequences:** GYG's delivery cost in order economics is `num_schools_in_trip * delivery_fee_cents`. The other caterers' delivery structures are encoded in the same enum.
**Out of scope as a result:** A more granular fee structure (e.g. tiered by distance, or by total order size).

---

### ADR-030: GST normalised to ex-GST cents for all caterer comparison

**Status:** Accepted
**Date:** Schema design
**Context:** Two of the four caterers quote inclusive of GST, two exclusive. Direct comparison of headline prices is misleading.
**Decision:** All comparison happens on ex-GST cents. `caterers.price_includes_gst` flags the source quoting convention; the system normalises to ex-GST at the point of comparison. Order economics show both ex-GST (for comparison) and inc-GST (for the invoice line).
**Alternatives considered:**
- *Compare on inc-GST* — rejected because two caterers don't report inc-GST in the source data; the normalisation would happen anyway, just at a different point.
- *Store both* — wasteful; one canonical form is enough.
**Consequences:** Caterer rotation analysis is apples-to-apples. The operator-facing display can choose either convention as long as the underlying comparison is consistent.
**Out of scope as a result:** Handling GST rate changes mid-term (V1 assumes the 10% rate is stable).

---

### ADR-031: Student keying by (school, name) at ingest, with no automatic identity merge

**Status:** Accepted
**Date:** Day 1
**Context:** The source data has 13 cross-school name collisions. Some are likely the same person; some are likely different. At ingest, the system has to decide whether to merge or split.
**Decision:** No automatic merge. Each sheet row at ingest creates a distinct student row, keyed by (school, name) implicitly through the enrolment. Two enrolments with the same student name at different schools result in two distinct `student_id`s unless an operator asserts they are the same person. A `student_identity_merge` table is explicitly deferred — this is a scope decision, not a time constraint.
**Alternatives considered:**
- *Auto-merge on (name, year_level)* — would collapse 6 of the 13 collisions where year levels match. Rejected per Assumption A5 (default treatment is non-collapse).
- *Auto-merge on (name, year_level, date_of_birth)* — would be safe but date_of_birth is not in the source data, so this is moot.
**Consequences:** Cross-school analytics (per-student variety prevention, taste compatibility) treat the same person at two schools as two people in V1. This is a known and accepted limitation. The `student_identity_merge` table is the explicit mechanism for operator-asserted identity merges, deliberately excluded from V1 scope.
**Out of scope as a result:** Heuristic merge with confidence scores; any auto-merge logic.

---

## Section 4 — Deferred Scope

These are decisions to *not* build something in V1. Each is listed with what it would have given us and why it is parked.

---

### ADR-032: Parents IS a first-class table in V1 (not deferred)

**Status:** Accepted (correction to the original brief)
**Date:** Schema design
**Context:** The initial planning brief listed "parent table" as deferred. The actual schema has `parents` as first-class.
**Decision:** Parents are a first-class entity in V1. The rationale (per the schema note): "First-class entity so per-parent statistics (notification reliability, walkup patterns) survive contact-detail changes via stable parent_id reference." Putting parent contact details on the enrolment as text fields would have meant losing the per-parent identity across enrolments and across contact-detail changes.
**Alternatives considered:**
- *Parent as text fields on enrolment* — what the original brief proposed. Rejected because per-parent reliability stats (Requirement §Reliable meal delivery) require a stable parent identity over time. If a parent updates their email, the text-field model loses the link to prior absence notifications.
**Consequences:** `enrolments.parent_id` references `parents`. `parent_notification_stats` accumulates per-parent over rolling windows. A parent with children at two schools resolves to one `parent_id` linked to both enrolments. Parent identity matching across schools is operator-driven — automatic email-based matching is unsafe given shared accounts and address changes that would silently merge distinct parents.
**Out of scope as a result:** Parent self-service (login, history view) — V1 reaches parents only via tokened links per send.

---

### ADR-033: School attributes table deferred

**Status:** Deferred
**Date:** Schema design
**Context:** Schools in the source data have attributes beyond name and region (e.g. preferred delivery entry, security requirements, parking instructions for caterers). These could be modelled in a `school_attributes` table.
**Decision:** Deferred. V1's `schools` table holds name, short_code, region, created_at — nothing more. Operational details that vary per school live in the agent's prompt context or in operator-managed notes.
**Alternatives considered:**
- *Build the attributes table* — would have been clean but uses build-week budget for a feature with no V1 user.
**Consequences:** Adding school attributes later is a schema addition, not a schema change.
**Out of scope as a result:** Per-school delivery preferences, per-school session timing variations beyond what `sessions` already captures.

---

### ADR-034: `actual_paid_cents` is a fabricated demo column

**Status:** Accepted (with caveat)
**Date:** Schema design
**Context:** Real payment tracking would require integration with accounting (Xero, invoicing, bank reconciliation). The demo benefits from showing "what was paid" against "what was estimated", but the V1 build doesn't have time for the integration.
**Decision:** `orders.actual_paid_cents` exists in the schema and is populated by hand (or by a demo script) for the submission. It is honestly labelled as fabricated demo data. The system does not autonomously update this field.
**Alternatives considered:**
- *Remove the column entirely* — rejected because the demo narrative benefits from showing the column populated, and pruning it would leave a gap in the order-economics story.
- *Build real payment integration* — out of scope for build-week budget.
**Consequences:** Anyone reading the schema sees a column the V1 agent never writes to. The schema comment (or this ADR) is the disclaimer.
**Out of scope as a result:** Accounting integration of any kind.

---

### ADR-035: Buffer auto-tuning loop designed but not built

**Status:** Deferred
**Date:** Day 1
**Context:** Margin sizing should learn from session reconciliations — if margin meals are routinely unused, the margin shrinks; if they're routinely exhausted, it grows. The data structure supports this (`session_reconciliations` carries the actuals).
**Decision:** Designed but not built in V1. `orders.margin_meals_per_session` is set from a per-school configuration value. Reconciliation data accumulates; the tuning loop that reads it and adjusts the configuration is deferred.
**Alternatives considered:**
- *Build the tuning loop* — would have made the margin self-improving, which is a strong V1 story. Cut on time grounds.
- *Skip reconciliation collection too* — rejected because reconciliation has independent value (caterer scoring, walk-up prediction).
**Consequences:** V1 margins are operator-configured. Reconciliation data accumulates in `session_reconciliations`.
**Out of scope as a result:** Autonomous margin adjustment.

---

### ADR-036: Tutor groups / teams modelling deferred

**Status:** Deferred
**Date:** Schema design
**Context:** Tutors could be grouped by team, specialty, or availability pattern. Sick-tutor cover (a separate workflow not in V1's scope) would benefit from team structure.
**Decision:** Deferred. V1 has `tutors` flat — no team, specialty, or availability fields.
**Alternatives considered:**
- *Add team and specialty fields* — rejected because the cover workflow isn't in V1 and the catering workflow doesn't read these fields.
**Consequences:** The catering operation is unaffected. Tutor groups are not modelled in V1.
**Out of scope as a result:** Tutor scheduling, availability windows, specialty matching.

---

### ADR-037: `outbound_emails` IS in V1 (not deferred)

**Status:** Accepted (correction to the original brief)
**Date:** Schema design
**Context:** The original brief listed outgoing emails as deferred ("v1 writes to filesystem"). The schema has `outbound_emails` as first-class.
**Decision:** Outgoing emails are recorded in `outbound_emails` and also written to the simulated outbox directory. The table captures `rendered_body` verbatim per send, linked to the `template_id` and the originating `agent_runs` / `decision_logs` rows.
**Alternatives considered:**
- *Filesystem only* — would have been faster. Rejected because the audit chain (which decision generated which email) requires the database link, and the rendered body needs to be reproducible even if templates are later edited.
**Consequences:** Email reconstruction for the audit trail joins `outbound_emails` → `email_templates` → `decision_logs` → `agent_runs`. Real SMTP integration replaces the filesystem write without changing the table.
**Out of scope as a result:** SMTP send, bounce handling, delivery confirmation.

---

### ADR-038: Escalation re-notification logic deferred

**Status:** Deferred
**Date:** Schema design
**Context:** An escalation that goes unacknowledged for some period should re-notify the operator (or escalate further). V1 raises the escalation once.
**Decision:** Deferred. `escalations.state` lifecycle is implemented (open / acknowledged / in_progress / resolved / superseded) but the re-notification logic that would re-fire on stalled state is not built.
**Alternatives considered:**
- *Build re-notification with configurable delays per severity* — would have been clean but adds a scheduler dimension the build week didn't have room for.
**Consequences:** Operators rely on the dashboard surface (deferred — see ADR-042) to see pending escalations. The data is captured; the re-notification firing is the missing piece.
**Out of scope as a result:** Escalation reminder cadence, severity-based escalation chains.

---

### ADR-039: User / auth table deferred; `resolved_by` is a text field

**Status:** Deferred
**Date:** Schema design
**Context:** Operator identity needs to be captured on resolution actions, history rows, and so on. A full users table with authentication would be the production answer.
**Decision:** Deferred. `escalations.resolved_by` is a text field carrying the operator's name as recorded. History tables have `changed_by_actor` (system / user / agent) and `changed_by_id` (a free integer that can hold a tutor_id, a future user_id, or be left null).
**Alternatives considered:**
- *Build a users table with login* — out of scope for the demo. Padea's existing app handles auth; V1's operator interactions happen via forms or scripts.
- *Hard-code operator as "coordinator"* — too coarse; rejected because per-action accountability matters for the audit trail.
**Consequences:** When auth is added, the text field migrates to a proper FK. Historical rows retain the text record.
**Out of scope as a result:** Login, sessions, role-based access control, multi-tenant operator separation.

---

### ADR-040: Email attachment binary storage deferred; metadata only

**Status:** Deferred
**Date:** Schema design
**Context:** Incoming emails sometimes carry attachments (e.g. a school's exclusion letter as a PDF). V1 captures the metadata but not the binary.
**Decision:** `incoming_emails.attachments_info` is a text field carrying the filenames and types. The binary content is not stored.
**Alternatives considered:**
- *Store binaries in a blob table or filesystem* — adds storage management for marginal V1 benefit; the textual content is what the agent reads.
**Consequences:** If an attachment matters for forensic review, the operator goes back to the source mailbox. V1's audit chain doesn't include the binary itself.
**Out of scope as a result:** PDF parsing of attachments, OCR, binary virus scanning.

---

### ADR-041: PII redaction and data retention policies deferred

**Status:** Deferred
**Date:** Day 1
**Context:** Real operation involves minors' data, parent contact details, dietary information that includes medical conditions. Production deployment would require retention policies, redaction in logs, and access controls.
**Decision:** Deferred. V1 stores PII in clear, in the operational tables and in the verbatim `incoming_emails.body_plain` capture. The system is not production-deployed.
**Alternatives considered:**
- *Build redaction at ingest* — rejected as build-week cost without competitive value for the submission.
- *Encrypted at rest* — out of scope for a SQLite-local development build.
**Consequences:** V1 must not be deployed against real Padea data without this layer. The acknowledgement is explicit in the memo.
**Out of scope as a result:** GDPR / Australian Privacy Principles compliance work.

---

### ADR-042: Caterer rotation explore/exploit logic acknowledged, not built

**Status:** Deferred (acknowledged in memo)
**Date:** Day 1
**Context:** Caterer rotation could be framed as an explore/exploit problem — sometimes the system tries an alternative caterer to gather quality signal, sometimes it sticks with the known one. The framing is interesting; the V1 build doesn't have time for it.
**Decision:** Deferred. V1 surfaces rotation proposals when decline conditions trigger (per ADR-007). It does not run controlled experiments or proactively rotate for information gathering.
**Alternatives considered:**
- *Build a small explore loop* — would have been a strong V1 story. Rejected on time.
**Consequences:** Rotation in V1 is reactive (decline-triggered) rather than active (information-seeking).
**Out of scope as a result:** Multi-armed bandit logic; controlled caterer trials.

---

### ADR-043: "Why did you do this?" coordinator query interface acknowledged, not built

**Status:** Deferred (acknowledged in memo)
**Date:** Day 1
**Context:** The decision logs and history tables together support arbitrary backward-queries — "why is this student getting this meal?" or "what changed about this caterer's score last week?" A coordinator-facing query interface would expose this directly.
**Decision:** Deferred. V1 produces the HTML demo render (per ADR-044) which shows decision trees per run, but does not offer an ad-hoc query surface.
**Alternatives considered:**
- *Build a coordinator chat surface against the database* — would have been a strong story; out of scope for build week.
**Consequences:** Coordinators read the run log or ask the operator to query directly.
**Out of scope as a result:** Natural-language query interface; SQL playground; saved coordinator queries.

---

### ADR-044: What-if rotation simulator acknowledged, not built

**Status:** Deferred (acknowledged in memo)
**Date:** Day 1
**Context:** Before approving a rotation, an operator might want to simulate the alternative: "what would last term have cost if we'd used Terrific instead of GYG for CHAC?" The data supports this; the simulator UI doesn't exist.
**Decision:** Deferred. Rotation proposals include comparative analysis but not a full what-if simulator.
**Alternatives considered:**
- *Build the simulator* — out of scope on time.
**Consequences:** Operators trust the proposal's comparative analysis or do the simulation manually.
**Out of scope as a result:** Counterfactual replay against historical orders.

---

### ADR-045: Anomaly detection on input changes acknowledged, not built

**Status:** Deferred (acknowledged in memo)
**Date:** Day 1
**Context:** A school suddenly enrolling 20 new students, or a caterer suddenly halving their MOQ, would be worth flagging. Anomaly detection on operational inputs is a natural extension.
**Decision:** Deferred. V1 has no anomaly detection layer.
**Alternatives considered:**
- *Build threshold-based anomaly flags* — out of scope.
**Consequences:** Operators notice anomalies through routine review, not through automated flagging.
**Out of scope as a result:** Statistical change detection on enrolments, prices, MOQ values, or capability rows.

---

### ADR-046: HTML demo surface as the V1 operator view

**Status:** Accepted
**Date:** Day 1
**Context:** A full operator dashboard is out of scope for build week. The system still needs to expose its reasoning visibly enough that judges can see what happened in a run.
**Decision:** Each run regenerates an HTML demo file from the operational tables, showing the run's decision tree, tool calls, results, and escalations. The file is colour-coded by tier (routine / notable / escalation) and severity. It is regenerated per run rather than served as a live application.
**Alternatives considered:**
- *Build a live web dashboard* — out of scope for build week.
- *No demo surface; rely on raw database inspection* — rejected because the judges shouldn't have to query SQLite to understand what the agent did.
**Consequences:** The HTML file is the operator surface for V1.
**Out of scope as a result:** Live dashboard, search, filtering, dashboards-as-a-service.

---

*End of decision register. Companion documents: `data_observations.md`, `assumptions.md`, `requirements_v1.md`, `schema_v1.dbml`, `v1_summary.md`.*
