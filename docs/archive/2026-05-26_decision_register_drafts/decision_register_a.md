# Decision Register — Padea Operations Agent

**Purpose:** The design choices that shape V1 of the system. Each decision selects between viable options, justified by what we observe in the data, what we assume to fill gaps, and what the requirements demand. Decisions are the bridge between the requirements (*what the system must do*) and the schema (*the form the system takes*).

**Compiled:** 25 May 2026
**Version:** V1 — the ambitious initial pass. Some entries will be cut in V2 and selectively reinstated in V3, evidenced in `docs/ledgers/`.
**Companion documents:** `data_observations.md` (DO), `assumptions.md` (A-numbers), `requirements_v1.md` (R), `schema.md`.

---

## How to read this document

Each entry has a stable identifier (D1, D2, …), a one-line statement of the decision, the upstream material it derives from, the reasoning, the alternatives that were considered and why they were rejected, and the downstream implications it carries forward.

The citation convention: **DO §X** for data observations sections, **A-N** for assumption N in the assumptions doc, **R §X** for sections of the requirements doc. Where a decision derives from operational judgement rather than a specific source, it's noted as **(operational judgement)**.

Decisions are grouped by domain. The grouping is for readability — many decisions touch more than one domain.

---

# 1. Identity and student data

### D1 — Each enrolment row at ingest is treated as a distinct student record

**Decision.** Every row in the per-school student sheets is ingested as a distinct student-enrolment, even where the same name appears at multiple schools. No automatic collapse is attempted at ingest, regardless of whether year levels match.

**Derived from.** DO §Students/Duplicate names across sheets · A5 (cross-school duplicate-name default).

**Reasoning.** The data contains 13 cross-school name duplicates: 7 with differing year levels (almost certainly different people) and 6 with matching year levels (could be either). Auto-collapsing on name+year would conflate distinct individuals 100% of the time on the differing-year set, and would risk false-positives on the matching-year set. Conservatism here is safer than apparent neatness; identity reconciliation can happen later when evidence emerges, but irreversible auto-collapse cannot.

**Alternatives considered.**
- Auto-collapse on (name, year_level): would have folded the 7 differing-year cases incorrectly.
- Auto-collapse on name alone: even more incorrect.
- Ingest with a "possible duplicate" flag for human review: defers decisions but doesn't make them worse; consider for V2.

**Implications.** The `students` table is keyed by an integer ID, not by name. A given person attending two schools occupies two rows. Cross-school analytics that want to count *people* rather than *enrolments* require explicit reconciliation logic; the V1 build does not provide it.

---

### D2 — Year level lives on the enrolment, not on the student

**Decision.** The `year_level` column is on the `enrolments` table, not on `students`. A student progressing from Year 11 to Year 12, or attending two schools at different levels in the same period, produces multiple enrolment rows with different year levels.

**Derived from.** DO §Students/Year-level breakdown per session (year level recorded per row per sheet) · A6 (year level as contextual to enrolment).

**Reasoning.** Year level is not a permanent property of a person — it changes annually, can differ across institutions, and is contextual to a time period. Putting it on `students` would require mutation on transition or duplication for cross-school cases. Putting it on `enrolments` makes each enrolment a self-contained statement of where, when, and at what level a student participated.

**Alternatives considered.**
- Year level on `students` with edits over time: loses history unless paired with a separate audit table.
- Year level on both `students` (current) and `enrolments` (historical): introduces a source-of-truth question.

**Implications.** Any query for "Year 11 students at CHAC" joins `enrolments` to `students`, filtering on the enrolment row. The `students` table holds only identity-stable data: name, contact details, possibly parent linkage.

---

### D3 — Opt-out from catering is a boolean on the enrolment row, not a separate event

**Decision.** Catering opt-out is captured as a boolean `opted_out` column on the `enrolments` table. No separate opt-out event table is created.

**Derived from.** DO §Students/Dietary information (`Opted out of Catering` mixed into the dietary column) · A7 (opt-out as enrolment property).

**Reasoning.** The data shows opt-out as a per-enrolment marker mixed into the dietary column. Operationally, a student can opt out at one school and not another, and can opt back in next term. Modelling opt-out as an enrolment property captures all this naturally — a new enrolment row reflects the new state. A separate event log would over-engineer a binary fact.

**Alternatives considered.**
- A separate `enrolment_opt_outs` table with timestamps: justified only if the audit history of opt-outs matters operationally, which it does not in V1.
- Opt-out as a tag in the dietary vocabulary: confuses dietary safety (a hard constraint) with commercial preference (a soft fact).

**Implications.** At ingest, the parser must detect `Opted out of Catering` in the dietary column, set `opted_out = TRUE` on the enrolment, and *not* add an opt-out value to the dietary tag set. Other dietary tags on the same row are still recorded (per Lei Li at ISHS Tuesday — `Nut Free, No Shellfish, Opted out of Catering`).

---

### D4 — Dietary information uses a controlled vocabulary, not free text

**Decision.** Dietary tags are stored against a small controlled vocabulary in a `dietary_tags` lookup table; students associate with tags through a junction table `student_dietary_tags`. Free text is not stored at the dietary-tag layer.

**Derived from.** DO §Students/Dietary information (distinct values enumerable, ~13 concepts) · R §The non-negotiable safety floor (matching must be reliable, dietary properties resolved in advance, no ad-hoc inference).

**Reasoning.** The safety floor admits no tradeoffs and no inference at the point of decision. A typo in free text — `vegitarian`, `vegeterian` — could cause a meal-matching failure that produces a safety incident. A controlled vocabulary makes matching a join, not a string comparison. The data shows the universe of dietary concepts is small (~13) and stable; the cost of the vocabulary is negligible against the safety benefit.

**Alternatives considered.**
- Free text on the enrolment: rejected on safety grounds.
- A single `dietary` text column with parsing at runtime: same safety risk.
- A wide table with one boolean per dietary concept: brittle to vocabulary growth, harder to query for "any restriction at all."

**Implications.** Ingest must parse the comma-separated values in the source data and resolve each against the controlled vocabulary. Unknown values raise an ingest-time escalation. The vocabulary itself is defined at build time and grows only by deliberate update.

---

### D5 — The dietary vocabulary is shared between students and any future role that needs it

**Decision.** A single `dietary_tags` table holds the controlled vocabulary. Students reference it through `student_dietary_tags`. If future scope requires dietary tags on tutors, walk-ups, or anyone else, they reference the same vocabulary.

**Derived from.** DO §Students/Dietary information · (operational judgement: vocabulary drift across entities is a known failure mode).

**Reasoning.** Two separate vocabularies for the same real-world concept invite drift — one updated, the other forgotten. A vegetarian is a vegetarian regardless of whether they're a student or a tutor. Sharing the vocabulary keeps the source of truth single. The cost is trivial (a junction table per entity that needs tagging); the benefit is consistency over time.

**Alternatives considered.**
- Separate `student_dietary_vocabulary` and `tutor_dietary_vocabulary` tables: simple but invites the drift problem.
- Free text per entity: rejected at D4.

**Implications.** Adding a new dietary concept to the vocabulary applies to all entities. Junction tables stay narrow (entity_id + tag_id). Note that V1 does not yet require tutor dietary tracking — the architecture admits it but does not implement it.

---

### D6 — Parent contact lives on the enrolment, not on the student

**Decision.** Parent name, parent email, and parent mobile are captured at the enrolment level. A student with multiple enrolments may have different parent contacts recorded at each (e.g. a divorced household where different parents handle different schools).

**Derived from.** DO §Students (parent contact columns present in each per-school sheet) · A6 (enrolment-as-context principle, generalised).

**Reasoning.** The same operational case that motivates per-enrolment year level applies to parent contact: real households are complicated, and forcing a single parent record per student loses information. Parent-school-contact pairings reflect operational reality, not an abstract single-source-of-truth ideal.

**Alternatives considered.**
- Parent contacts on `students` (one set per student): cleaner data model, loses real-world variation.
- A separate `parents` table with many-to-many to students: justified if parents become first-class entities (e.g. for term surveys); over-engineered for V1.

**Implications.** Absences received from parent emails reference the enrolment's parent contact for verification, not a global parent-student linkage. V3 may promote `parents` to first-class if survey pseudonymisation needs to track them.

---

# 2. Caterers and capability

### D7 — "Currently serves" and "able to serve" are modelled as the same kind of relationship, distinguished by a status

**Decision.** A single `caterer_school_capabilities` table holds (caterer, school) pairs with a status field. Status values include `currently_serving`, `able_to_serve`, and `not_capable`. There is no separate "current" table.

**Derived from.** DO §Caterers/Caterer capability and current assignments · A10 ("able to serve" applies to current schools/days only, not hypothetical schedules).

**Reasoning.** Two separate tables (`current_assignments` and `capabilities`) would duplicate the (caterer, school) pair across them and force a join-or-union to ask "can this caterer serve this school in any capacity." A single table with a status field captures the same information with less ceremony. Rotation events (a swap from "able" to "currently serving") become a status update, with history preserved through an event log if needed.

**Alternatives considered.**
- Two tables (one for current, one for capability): the most obvious split, but creates the consistency problem above.
- Status as a boolean (`is_current`): doesn't admit the third option of "explicitly not capable" which V2 may need.

**Implications.** Queries for "who serves school X" filter on status `currently_serving`. Queries for "who could serve school X" include both `currently_serving` and `able_to_serve`. Rotation updates the row, not a separate join.

---

### D8 — Capability is recorded at (caterer × school) granularity, not (caterer × school × day-of-week)

**Decision.** The `caterer_school_capabilities` table has one row per (caterer, school) pair, not per (caterer, school, day). Day-specific capability is inferred from the existence of currently-running sessions on that day.

**Derived from.** DO §Caterers/Caterer capability and current assignments (capability stated at school level in the source) · A12 (capability granular to caterer×school×day-of-week).

**Reasoning.** This is a deliberate departure from A12 in the assumptions doc. The source data states capability at the school level, not the day level. Inflating capability to day-of-week granularity for every (caterer, school) combination would create 28 rows per (caterer, school) pair for no operational gain — the days the caterer actually serves are already visible from the sessions table. Where day-specific incapability needs to be recorded (e.g. caterer X can serve school Y on Mondays but not Thursdays), we add a separate `caterer_day_blackouts` table for the exceptions. This keeps the common case lean.

**Alternatives considered.**
- Full (caterer, school, day) capability matrix: 4 caterers × 6 schools × 7 days = 168 rows, mostly noise.
- Day-of-week constraints on the capability row itself: muddles "this caterer can serve this school" with "on these specific days."

**Implications.** Rotation logic that proposes a new caterer for a session must check both that the caterer has `able_to_serve` for that school AND that the caterer has no blackout for that day of the week. The blackout table starts empty and is populated only when constraints are discovered.

---

### D9 — Caterers can serve multiple schools per day where capability is recorded for both

**Decision.** No constraint is enforced preventing the same caterer from being assigned to two schools on the same date.

**Derived from.** DO §Schools and sessions/Building, year levels, and concurrent sessions (GyG delivers to Loreto and CHAC on Monday 1 May concurrently) · A11 (multi-school-per-day is operationally feasible where capability permits).

**Reasoning.** The data shows this is already happening — GyG delivers to two Central Brisbane schools simultaneously. Encoding a "one school per caterer per day" constraint would reject existing operational reality. The capability list combined with regional proximity is the operational filter; the schema does not need to second-guess it.

**Alternatives considered.**
- One-school-per-day constraint at the schema level: would reject the GyG Monday case.
- Concurrent-delivery warning surfaced as an escalation: useful if a new concurrent assignment is created where capability proximity is questionable; deferred to V2.

**Implications.** Rotation suggestions can produce same-day multi-school assignments. The system surfaces concurrent assignments for human approval (per the escalation logic) but does not block them.

---

### D10 — MOQ rules are stored as (caterer, menu_variety_count) triples in a dedicated table

**Decision.** A `caterer_moq_rules` table holds one row per (caterer, menu_variety_count). Each row specifies the minimum weekly meal count required to meet MOQ at that variety level. Lookups are by joining caterer to (caterer, current_week_variety_count).

**Derived from.** DO §Caterers/Minimum order quantity (MOQ table with three variety tiers per caterer) · A14 (MOQ as financial penalty when missed) · R §Reliable meal delivery (must distinguish failing MOQ from meeting MOQ).

**Reasoning.** The MOQ rules in the source data have a 2D structure: per caterer × per menu variety count. Flattening them into the `caterers` table would require columns like `moq_at_4`, `moq_at_5`, `moq_at_6` — brittle to caterers with different variety tiers (Lakehouse may someday offer a 7-item tier; Kenko already has tiers at 35/40/45 vs Terrific's 10/20/30). A separate table absorbs the variation naturally.

**Alternatives considered.**
- Wide columns on `caterers`: brittle, as above.
- MOQ as a single column representing "minimum at standard variety": loses the tiered information.

**Implications.** Order generation must determine the desired variety count, look up the MOQ for that (caterer, variety) pair, and compare against the weekly volume. Variety reduction (per requirements) cascades down through MOQ levels until a feasible point is found.

---

### D11 — Dietary-specific meals do not count toward MOQ

**Decision.** When checking whether a weekly order meets a caterer's MOQ at a given variety level, dietary-specific meals (meals served because of a recorded dietary tag, including VO-substituted meals) are excluded from the count. Standard meals only contribute to MOQ.

**Derived from.** DO §Caterers/Minimum order quantity (volume vs MOQ comparison) · DO §Menus (VO annotations as caterer capability not item property) · A9 (VO as caterer capability) · (operational judgement: dietary meals are typically priced and prepared as a separate line in catering).

**Reasoning.** Dietary meals in catering are usually prepared and priced as a separate process from standard meals — a vegetarian variant via VO substitution is a different SKU from the headline item. Counting them toward MOQ would let the system silently under-order the standard line. A session with 18 standard + 4 dietary meals must be evaluated as 18 against MOQ; if 18 is below MOQ, the MOQ failure fires.

This is an ambitious decision — it commits to a more careful financial model than the obvious "count everything." Confirm with Dylan as part of the May 27 meeting.

**Alternatives considered.**
- Count all meals (standard + dietary) toward MOQ: simpler but operationally wrong if the caterer prices them separately.
- Treat dietary meals as a separate MOQ count: over-engineered when dietary counts are small.

**Implications.** Order generation produces two figures per session: standard count (against MOQ) and dietary count (independently guaranteed). The MOQ shortfall escalation includes both numbers and the implied financial cost.

---

### D12 — Caterer contacts can carry any combination of four role flags

**Decision.** The `caterer_contacts` table includes four boolean columns: `is_order_taker`, `is_chef`, `is_primary_contact`, `cc_on_orders`. Any combination of these is operationally valid; no constraint enforces particular combinations.

**Derived from.** DO §Caterers/Caterer contacts (four distinct combinations of role flags appear across the six contacts) · A16 (any combination of roles is operationally valid).

**Reasoning.** The data shows contacts with single roles (Big Mom is both order-taker and chef at Kenko) and split roles (Terrific has Dylan Chern as order-taker and James Chern as chef with no cc). The role combinations don't fit a clean role-enum (chef, manager, owner, etc.). Four orthogonal booleans capture every combination present in the data without forcing categorisation.

**Alternatives considered.**
- A single `role` enum column: doesn't admit the multi-role cases like Big Mom.
- A separate `contact_roles` junction table: over-engineered for four fixed flags.

**Implications.** Outgoing emails route based on `is_order_taker` (primary recipient) and `cc_on_orders` (cc list). Escalations to a caterer route to `is_primary_contact`. Chef contacts are recorded but typically not emailed for order operations.

---

### D13 — Caterer contact name and email pairings are stored exactly as the data presents them

**Decision.** Ingest does not attempt to repair name-email mismatches in the caterer-contacts data. Names appearing inverted relative to the email handle (Big Chicken at carmengabrielleee@gmail.com; Medium Giraffe at dylan@padea.com.au) are preserved verbatim.

**Derived from.** DO §Caterers/Caterer contacts (name-to-email inversions present) · A15 (pairings as given, even where inverted).

**Reasoning.** The inversions are part of the test fixture; reading them as data quality errors and attempting repair would corrupt the test setup. The system's job is to operate on the data as given, not to second-guess it.

**Alternatives considered.**
- Ingest-time correction with logged warnings: actively dangerous if the inversions are intentional.
- Flag inversions for manual review: useful future enhancement but not V1.

**Implications.** Emails sent to "Big Chicken" go to carmengabrielleee@gmail.com. Audit logs record this without complaint.

---

# 3. Sessions and managers

### D14 — Sessions store start, end, and dinner timestamps explicitly; duration and midpoint are derived

**Decision.** The `sessions` table stores `session_start`, `session_end`, and `dinner_start` as columns. Session duration (180 minutes) and dinner duration (30 minutes) are derived at runtime or stored only as computed columns.

**Derived from.** DO §Schools and sessions/Session timing (every session is 180 minutes, dinner at the 90-minute midpoint, only dinner start is in the source data) · A20 (180-minute session, dinner at midpoint as structural rule) · A21 (30-minute dinner duration as authoritative).

**Reasoning.** The source data records only three timestamps per session and three are sufficient to derive everything else. Storing computed values (duration, midpoint, dinner end) introduces consistency burden — if any input changes, all derived values must update. Deriving at runtime is cheap; the values are computed once per query.

**Alternatives considered.**
- Store duration and midpoint as columns: cheap storage but consistency risk.
- Store dinner_end explicitly: requires a value the source doesn't provide; effectively storing the assumption A21.

**Implications.** Session structure (180min, dinner at midpoint) is enforced as a *validation rule* at ingest, not as a schema constraint. If future data ever contains a session that deviates, the rule fires and the human approver is informed.

---

### D15 — Session times are parsed into typed timestamps at ingest, not stored as strings

**Decision.** The session-time columns in the source data (recorded as `"4:00pm"` strings) are converted to typed timestamps at ingest. The database stores `TIMESTAMP` types, not `TEXT`.

**Derived from.** DO §Schools and sessions/Session timing (times stored as strings in source data) · R §Reliable meal delivery (correct timing is foundational).

**Reasoning.** Timestamp arithmetic is needed throughout the system — computing lead time, comparing absences against order send times, scheduling escalations. Storing strings would force runtime parsing at every query, with the consistent risk of parsing failure. Ingest-time parsing fails loudly (the row is rejected) rather than silently producing wrong arithmetic later.

**Alternatives considered.**
- Store strings, parse on read: cheap ingest, expensive queries, risky.
- Store both: redundancy without benefit.

**Implications.** Ingest must include a robust time-string parser that handles the AM/PM format. Parsing failures escalate.

---

### D16 — Managers are tutors carrying a session-specific role, not a separate population

**Decision.** No `managers` table exists. The `sessions` table has `expected_manager_id` and `actual_manager_id` columns referencing the `tutors` table. A given person can be assigned as manager on some sessions and not others.

**Derived from.** DO §Schools and sessions/Session managers (7 managers named, all also appear elsewhere as tutors per project context) · A17 (managers as tutors with session-role) · R §The coordinator out of the bottleneck (manager-as-role rather than population principle).

**Reasoning.** A separate `managers` table would be a near-duplicate of `tutors` with an artificial boundary. The same person managing one session and tutoring another would either be duplicated in two tables (with consistency burden) or excluded from one role's view. Treating "manager" as a per-session role keeps identity unified.

**Alternatives considered.**
- Separate `managers` table: as above.
- A boolean `is_manager` flag on tutors: doesn't capture per-session variation.

**Implications.** Cover events (a tutor stepping in to manage when the expected manager is unavailable) become a difference between `expected_manager_id` and `actual_manager_id` on the session row. No separate cover or absence entity is required.

---

### D17 — Tutor records hold only what catering needs: name and mobile

**Decision.** The `tutors` table in V1 has three columns: `tutor_id`, `name`, `mobile`. No subject specialty, qualifications, employment history, or other tutor metadata.

**Derived from.** A18 (tutor record minimal, broader data lives in other Padea systems) · R §The coordinator out of the bottleneck (system owns catering-relevant data, not the full Padea record).

**Reasoning.** The catering system should not duplicate or compete with Padea's existing tutor records. Mobile is the operational essential (caterer drivers call mobiles); name is needed for human-readable manifests and decision logs. Anything more is scope creep.

**Alternatives considered.**
- Full tutor records: scope creep, sync burden with the source system.
- Tutor name only (no mobile): loses the operational essential.

**Implications.** Reports that need tutor specialty (e.g. "which Physics tutors are at school today") cannot be generated from this system; they require joining external Padea tutor data.

---

### D18 — Session assignments use a junction table even though sessions list a manager directly

**Decision.** The `session_tutor_assignments` table records every tutor assigned to each session, including the manager. The `expected_manager_id` and `actual_manager_id` columns on the session are pointers to assignments, not the full assignment surface.

**Derived from.** DO §Schools and sessions (sessions reference manager, but full tutor team is not in source data) · A18 (tutor record minimal) · (operational judgement: tutor teams may be larger than the manager and the catering system should record participation for cross-referencing).

**Reasoning.** The session row captures the manager role specifically; the junction table captures *all* tutors at the session, of which one is the manager. This handles the case where the source data later expands to include the full tutor roster per session — no schema migration required.

**Alternatives considered.**
- Only store the manager on the session: simpler but loses the future expansion path.
- Only use the junction table: forces a join for the common-case manager lookup.

**Implications.** The junction table starts populated with just the manager in V1 (because the source data only provides the manager). Future ingest can populate the full team without schema change.

---

# 4. Order generation and weekly cadence

### D19 — Orders are composed once per (caterer × week), with the full week visible at composition time

**Decision.** The `orders` table is keyed by (caterer, week). One order per caterer per week. The order's line items reference individual sessions within that week. Composition happens at one event in the Monday-of-prior-week window.

**Derived from.** A17 (weekly composition with full week visible) · A23 (order composed once with full week in view) · R §Reliable meal delivery (correct order generation).

**Reasoning.** A caterer cares about their total weekly commitment and revenue. A per-session order would force the caterer to track multiple inbound documents per week, each binding only a fraction of their MOQ. A per-caterer-per-week order, with session-level line items inside, mirrors the caterer's mental model: "what am I making this week?" It also collapses the MOQ check into a single decision at composition.

This dissolves the prior question of whether the agent must forecast remaining-week demand mid-week — the entire week is composed at once, so no forecast is needed.

**Alternatives considered.**
- One order per session: as above, fragments the caterer's view and complicates MOQ.
- One order per (caterer × day): intermediate and uncomfortable; no clear advantage.

**Implications.** The `orders` table has one row per (caterer, week). The `order_lines` table breaks the order down by (session, menu_item, quantity). Cancellations or amendments mid-week become *exceptions* against the original weekly order, recorded as separate events.

---

### D20 — Order generation has a fixed weekly cadence aligned to the earliest caterer lead time

**Decision.** All caterer orders for the coming operational week (Monday–Thursday) are composed and sent on the Monday of the prior week. This provides a minimum lead time of 7 days for the earliest session and matches the brief's current Thursday-for-Monday operation in spirit while running on a single weekly cycle.

**Derived from.** A23 (weekly composition cadence is feasible per current operation) · R §Reliable meal delivery (adequate lead time) · DO §Observation period (only weekday sessions in the data).

**Reasoning.** A single weekly cycle simplifies the agent's run schedule, the caterer's mental model, and the demo narrative. The Monday-of-prior-week timing gives every session at least 7 days of lead time and gives the system a clear deadline for absence intake (any absences received by Sunday EOD are reflected in the order; absences received Monday onward are post-send).

**Alternatives considered.**
- Per-caterer rolling 3-day cadence: more flexible but scatters the agent's work across the week.
- Thursday-for-following-week (matching the brief's current state): tighter lead time, more demo-friendly because the agent runs once per week on a clear day.

**Implications.** The agent has one scheduled run per week. Mid-week corrections (absences received after Monday) do not amend the sent order — they're recorded as state changes and absorbed by operational margin. This locks in D21 below.

---

### D21 — Orders, once sent, are not amended for absences or walk-backs

**Decision.** The `orders` table records `sent_at`. Any absence, walk-back, or exclusion recorded *after* this timestamp does not modify the order's line items. The order is treated as a frozen contract from `sent_at` onward.

**Derived from.** A18 (orders not amended post-send) · A24 (single composition event in the session timeline) · R §Reliable meal delivery (amending caterer orders post-prep is disruptive).

**Reasoning.** Caterers prepare meals on a schedule that doesn't tolerate late changes; amending the order downstream would create caterer-side disruption disproportionate to the gain. Late absences are absorbed by the operational margin (D24 below); late walk-backs are also absorbed by the margin. The "frozen contract" framing also produces a clean audit surface: anyone asking "what did we order?" gets a clear answer from the order row, not a moving target.

**Alternatives considered.**
- Allow amendments up to N hours before the session: workable but requires complex amendment logic and caterer-side acknowledgement.
- Allow amendments only for net-reductions: easier on caterers but inconsistent.

**Implications.** Late absences are *recorded* (in the `absences` table) but not *reflected in the order*. The decision log shows the absence arriving and being absorbed by margin without modifying the upstream order.

---

### D22 — Order construction reserves dietary meals before computing the standard meal pool

**Decision.** Order generation runs in two phases. Phase 1 reserves one dietary-specific meal for every student with a dietary tag who is expected to attend (i.e. not opted-out, not excluded, not pre-send-absent). Phase 2 fills the remaining slots from the standard meal pool using the per-student preference data.

**Derived from.** R §The non-negotiable safety floor (dietary safety above all other considerations) · A29 (whole-session override is the only condition that suspends dietary guarantees) · D11 (dietary meals don't count toward standard MOQ).

**Reasoning.** Two-phase construction enforces the safety floor by construction — dietary meals are committed before any standard-meal economics enter the picture. If MOQ pressure forces variety reduction, the reduction happens in the standard pool only. This guarantees no dietary student is ever traded against budget.

**Alternatives considered.**
- Single-pass construction with dietary meals tagged: easier to write but loses the structural guarantee.
- Two separate orders (one dietary, one standard): cleaner separation but doubles the caterer-facing surface.

**Implications.** The `order_lines` table has a `line_type` column distinguishing `dietary` from `standard`. MOQ logic filters on this column. The decision log explicitly shows phase 1 and phase 2 as separate decision branches.

---

### D23 — Menu variety is selected against the cohort's recent menu history

**Decision.** Order generation looks back N weeks (4 in V1) at the cohort's menu history for the same caterer and weights variety selection away from items served recently. Items repeated within the lookback window are excluded unless variety constraints force them back in.

**Derived from.** R §Sufficient variety (palate fatigue prevention requires history-aware selection) · A23 (weekly cadence makes lookback well-defined).

**Reasoning.** Palate fatigue is a real signal in the data — the brief calls out students disliking repeated meals. Without explicit history tracking, the agent's selection would drift toward whatever the caterer has many of, repeating common items. A 4-week lookback gives the variety policy real teeth without requiring infinite memory.

**Alternatives considered.**
- No history tracking, random selection: cheap but doesn't prevent fatigue.
- Lookback of 8 weeks: more variety, harder to satisfy on small menus.
- Per-student lookback (track what each student has been served): more sophisticated but requires per-meal-per-student logging that V1 does not yet have.

**Implications.** The `order_lines` history is queryable by (cohort, caterer, item, week). Variety selection joins this history with the caterer's full menu and ranks candidates by recency.

---

### D24 — Operational margin is fixed at 2 meals per session, drawn from a common-pool item set

**Decision.** Every session order includes 2 extra meals beyond the confirmed-attendance count. These margin meals are drawn from a designated "common-pool" item — a meal known to be broadly acceptable across the cohort. The margin is not preference-matched to any specific person.

**Derived from.** A19 (margin required the moment we start cutting meals) · A25 (margin sourcing per common-pool reasoning) · R §Reliable meal delivery (margin sized to avoid routine shortfalls).

**Reasoning.** Two is small enough to be tractable financially, large enough to absorb the realistic walk-back rate (the data shows 10 absences across the dataset week; if even 20% are walked back, the margin handles them). Common-pool sourcing means the margin meal is genuinely usable by whoever needs it — a margin meal that's a vegetarian noodle bowl doesn't help a meat-eating student.

**Alternatives considered.**
- Margin sized as a percentage of cohort: doesn't reflect the absolute nature of the unpredictability.
- Margin matched to most-common preference: closer to optimal but assumes a single dominant preference exists per cohort.
- Zero margin: rejected per A19.

**Implications.** The `order_lines` table records margin meals with `line_type = margin`. The decision log shows the margin computation as a separate explicit step. If margin is regularly exhausted (signal: walk-up events repeatedly consume the full margin), the system surfaces this for re-sizing — V2 may make the size dynamic.

---

### D25 — Partial exclusions add a 10% attendance buffer to the remaining cohort's order

**Decision.** When a session has a partial exclusion (e.g. Year 12 at camp), the order is sized to the *remaining* cohort plus a buffer of 10% of the *excluded* cohort, rounded up to a whole meal. This is on top of the standard 2-meal margin.

**Derived from.** DO §Exclusions (CHAC Wed exclusion as concrete example) · A30 (excluded students still paying, may attend anyway) · R §Reliable meal delivery (partial exclusions account for students who attend anyway).

**Reasoning.** Partial exclusions are inherently messy — some excluded students will turn up anyway (forgot the camp, opted out of the excluded event, weren't actually going). The 10% rate is calibrated to social reality: not so high that the exclusion saves nothing, not so low that the cohort regularly hits the margin. Rounding up to whole meals avoids fractional-meal nonsense.

This is a deliberate V1 ambition — V2 will debate whether the 10% rate is too high, too low, or should be per-school-configurable.

**Alternatives considered.**
- Zero attendance buffer for excluded cohorts (trust the exclusion completely): produces a 10-meal shortfall when half a year level shows up anyway.
- 20%: over-buffers; large excluded cohorts produce expensive waste.
- Per-school configuration: more accurate but requires data we don't have yet.

**Implications.** CHAC Wednesday with the Year 12 and Year 10 exclusion (17 students excluded, 22 attending) gets an order of 22 + 2 (margin) + 2 (10% of 17 rounded up) = 26 meals. The decision log shows this calculation explicitly.

---

# 5. Absences and exclusions

### D26 — Absences are stored with the source email, walk-back timestamp, and reason

**Decision.** The `absences` table records: student_id, session_id, received_at, reason (free text), walked_back_at (nullable), source_email_id (nullable). One row per absence event.

**Derived from.** DO §Absences (file provides name + date only) · A20 (email-primary intake) · A21 (walk-back as same event, reversed) · R §Reliable meal delivery (absence handling).

**Reasoning.** The walk-back is a property of the original absence, not a new event — if a parent says "actually, ignore that, she's coming" it's still about the same Tuesday. Capturing the walk-back as a nullable timestamp on the row keeps the event arc intact. The source_email_id link preserves the audit trail.

**Alternatives considered.**
- Walk-backs as separate events: doubles the rows, complicates aggregation.
- No walk-back column, walk-backs as a status change on the row: same outcome, less explicit.

**Implications.** A "walk-back of a walk-back" (parent reverses their reversal) creates a *new* absence row, not a re-flip. The decision log preserves both the original absence and the final state.

---

### D27 — Duplicate absence notifications are deduplicated at ingest by (student_id, session_id)

**Decision.** Ingest enforces a unique constraint on (student_id, session_id) in the `absences` table. A second notification for the same (student, session) updates the existing row's `received_at` to the later timestamp and appends to a `notification_count` field; it does not create a new row.

**Derived from.** A22 (parents sometimes send the same absence multiple times) · DO §Absences (file presents each absence once, but production data will have duplicates).

**Reasoning.** Multiple "Lily is sick today" emails should not produce multiple absence events. Deduplication at ingest is cleaner than at every query. The `notification_count` field preserves the fact that the parent sent multiple notifications — useful for detecting anxious-parent patterns.

**Alternatives considered.**
- Store every notification as a separate row, dedupe at query time: more flexible but every query that uses absences must remember to dedupe.
- Reject duplicates at ingest with an error: loses the data that the duplicate existed.

**Implications.** The `incoming_emails` table still records each notification email, even when the absence row is updated rather than created. The audit trail is in the email table; the operational state is in the absence row.

---

### D28 — Pre-send vs post-send absence is derived from timestamps, not stored as a column

**Decision.** Whether an absence affected the upstream order is determined at query time by comparing `absences.received_at` against `orders.sent_at` for the relevant order. No `is_pre_send` boolean is stored.

**Derived from.** A18 (orders not amended post-send) · A23 (single composition event with clear send timestamp) · R §Reliable meal delivery (must distinguish absences that affect order from those that don't).

**Reasoning.** Storing the derived state introduces a consistency problem (what happens if `orders.sent_at` is corrected?). The comparison is cheap. Keeping it derived means the source of truth is the two timestamps, and any analysis that wants the distinction does the comparison itself.

**Alternatives considered.**
- Store a boolean `is_pre_send`: as above, consistency burden.
- Store a categorical status (pre_send, post_send, walked_back): combines too many things.

**Implications.** Reports and decision-log entries that mention "pre-send" or "post-send" status include the relevant comparison in their generation logic.

---

### D29 — Exclusions are stored with scope, scope_value, and a reason

**Decision.** The `exclusions` table holds: session_id, scope (`whole_session` or `year_level`), scope_value (null for whole_session; year level value for year_level scope), reason (free text), received_at, source_email_id.

**Derived from.** DO §Exclusions (3 exclusions: 2 whole-session, 1 partial year-level) · A29 (whole-session overrides dietary always-made rule) · A31 (exclusions arrive pre-filtered by human).

**Reasoning.** The two scope values cover all observed cases. Subject-specific exclusions (e.g. "Physics students at competition") are handled as individual absences per A31, not as exclusion entries — keeping the exclusions table focused on the well-defined cohort-level case.

**Alternatives considered.**
- Single boolean `is_whole_session`: doesn't admit the year-level case cleanly.
- More granular scope (year_level + section + cohort): over-engineered for the data observed.

**Implications.** Order generation joins exclusions to sessions and applies them based on scope. Whole-session exclusions skip the order entirely; year-level exclusions filter the cohort.

---

### D30 — Exclusions do not have a walk-back mechanism

**Decision.** No `walked_back_at` column on the `exclusions` table. A reversed school decision is handled by deleting the exclusion row (with audit log) or by superseding it with a new row.

**Derived from.** A32 (exclusions reversal is rare, handled manually) · (operational judgement: parity with absences would over-engineer).

**Reasoning.** Reversed school decisions are extremely rare in practice — schools don't usually cancel a camp the day before. Building parity with the absences walk-back model would add complexity for almost no operational gain. The escape valve (delete or supersede) is sufficient for the edge case.

**Alternatives considered.**
- `walked_back_at` column for parity with absences: over-engineered.
- Soft-delete with a `deleted_at` timestamp: useful audit feature, deferred to V2.

**Implications.** When a school reverses an exclusion, the human approver removes or supersedes the row manually. The decision log records the change but the schema does not formalise the reversal flow.

---

### D31 — Post-send whole-session cancellations are recorded as exclusions and trigger a human-approved decision flow

**Decision.** A whole-session cancellation arriving after the relevant order has been sent is still recorded in the `exclusions` table (preserving the audit trail), AND triggers an escalation to the human approver to decide the operational response (cancel delivery, accept delivery and donate, pay caterer regardless, etc.).

**Derived from.** A33 (post-send cancellation requires human intervention) · R §Reliable meal delivery (post-send order is a frozen contract by D21).

**Reasoning.** Recording the exclusion preserves the audit trail (the order shows what was sent; the exclusion shows what changed afterward). The escalation captures that the system explicitly recognised the conflict — "we have an order out and the session is cancelled." The human handles the caterer conversation; the system records the decision and outcome.

**Alternatives considered.**
- Don't record the post-send exclusion: loses audit trail.
- Auto-trigger a recall message to the caterer: presumes a policy that hasn't been established.

**Implications.** The decision log shows the conflict explicitly: order X sent, exclusion Y arrived post-send, escalation Z opened, human approver resolved with action A. The late-cancellation policy is one of the open questions for Dylan.

---

# 6. Feedback (V1 initials state: parent-selects, student-rates)

### D32 — Parents receive a weekly meal-selection email with a dietary-filtered menu

**Decision.** Each Sunday (or the day after order composition), parents whose children have an upcoming session receive an email listing the menu options for that session, pre-filtered to remove items incompatible with their child's dietary tags. Parents respond by selecting which options are acceptable for their child.

**Derived from.** A28 (parents in a position to know acceptable options) · A29 (parent-facing list is dietary-filtered) · R §Meals students want to eat (per-student acceptability data needed).

**Reasoning.** This is the V1 ambitious mechanism, deliberately included even though it generates per-student data only from parent-mediated input. V2 will examine the response rate weakness and possibly cut this mechanism; V3 will likely replace it with the manager + tutor + term-survey model. Documenting it in V1 makes the journey examinable.

The dietary filtering is a safety measure — showing parents items their child cannot eat invites mis-selection.

**Alternatives considered.**
- Student-direct selection (no parent mediation): better data quality for older students, but works against the safety floor for younger students.
- Term-start preference capture only (no weekly): less administrative load but less responsive to changing preferences.
- No preference capture at all: cheapest, abandons the satisfaction loop.

**Implications.** The `weekly_preference_selections` table holds parent responses, keyed by (enrolment_id, week, menu_item_id, accepted). Order construction phase 2 (per D22) filters menu choices through this table. Non-responders default to "all options acceptable" per D33.

---

### D33 — Non-response defaults to "all options acceptable"

**Decision.** Where a parent does not respond to the weekly selection email by the Monday composition cutoff, the system defaults to treating all dietary-compatible options as acceptable for that student.

**Derived from.** A36 (some response participation expected but not 100%) · R §Meals students want to eat (system must distinguish students with preferences from students content with whatever).

**Reasoning.** Non-response is a real signal — most parents don't have strong preferences and trust the system. Treating non-response as "no preference" lets the system serve those students efficiently while preferences from engaged parents drive the variety calculation. The alternative — escalating every non-responder — would generate noise without producing useful action.

This is deliberately ambitious: the system commits to a default behaviour rather than forcing parent action, which makes the system more useful from week 1 but accepts that some students may receive meals their parents wouldn't actively endorse.

**Alternatives considered.**
- Treat non-response as "no data" and skip the student: produces operational failures (student arrives, no meal).
- Escalate non-responders to the coordinator: creates exactly the bottleneck the system is supposed to eliminate.
- Use the student's previous week's selections: useful enhancement, deferred to V2.

**Implications.** The `weekly_preference_selections` table includes rows only for active responses. Non-responders are inferred from absence-of-row, not from explicit "no response" markers. The decision log shows the default-acceptance behaviour explicitly when it fires.

---

### D34 — Students rate their served meal via a same-evening response link

**Decision.** After each session, students receive a link (sent via the parent contact or directly to the student email if recorded) to rate the meal they received on a 1–5 scale. Ratings are pseudonymous from the caterer's perspective but linked internally to the student-meal-session triple.

**Derived from.** A37 (students participate in rating) · A38 (ratings remain Padea's property, not caterer-visible per-student) · R §Quality maintained over time (quality signals from multiple sources).

**Reasoning.** Same-evening response captures the meal fresh in the student's memory. The rating is anchored to the specific meal served, not to a session-overall vibe. Pseudonymity means caterers see aggregate decline ("CHAC ratings down 12% over four weeks") without seeing which specific students are unhappy.

This is deliberately ambitious: V2 will debate whether the response rate justifies the complexity. V3 likely replaces or supplements with manager + tutor channels.

**Alternatives considered.**
- No same-evening capture, end-of-term survey only: misses the temporal granularity needed for early decline detection.
- Per-meal rating via parent (not student): doubles the parent-side administrative load.
- Free-text feedback only: harder to aggregate, no scale signal.

**Implications.** The `meal_ratings` table holds (enrolment_id, order_line_id, rating, comment_text, submitted_at). Quality aggregation joins this against caterer history. The rating intake channel is open (one of the Dylan questions for May 27).

---

### D35 — Caterer quality is computed at query time with two corrections

**Decision.** Caterer quality scores are computed on-demand by aggregating raw ratings, with two corrections:
- **Rater-baseline normalisation:** each rater's mean rating across all caterers is subtracted (some students rate harshly, others generously).
- **Submission-timing weighting:** ratings submitted within 24 hours weighted at 1.0; later submissions weighted lower on a decay curve.

**Derived from.** R §Quality maintained over time (signals from multiple sources, decline detected early) · (operational judgement: rater bias is well-studied; recall bias is real).

**Reasoning.** Computing at query time means the aggregation algorithm can evolve without backfilling stored aggregates. Both corrections are well-known signal-quality improvements. Without rater normalisation, a single harsh rater can drag a caterer's score down disproportionately. Without timing weighting, a rating submitted three weeks later (memory blurred) counts as much as a same-evening one.

This is ambitious deliberately — V2 will debate whether the corrections are worth the complexity; V3 will likely refine the weighting functions.

**Alternatives considered.**
- Stored aggregate updated on rating: faster reads, fragile to algorithm changes.
- No corrections, raw averages: cheapest, less reliable signal.
- Bayesian shrinkage toward population mean: more sophisticated, deferred.

**Implications.** Quality query performance must be acceptable. If query-time aggregation becomes a bottleneck, V2 may introduce a daily-refreshed materialised view.

---

### D36 — Caterer rotation is triggered when rolling 4-week quality drops more than one standard deviation below the caterer's own historical mean

**Decision.** The rotation trigger compares the caterer's rolling 4-week mean quality score against their own historical mean over the previous 12 weeks. A drop of more than one standard deviation (computed from the historical period) triggers a rotation escalation.

**Derived from.** R §Quality maintained over time (decline detected early enough to act) · A42 (rotation is human-judged, system surfaces and drafts).

**Reasoning.** Comparing against the caterer's own history (rather than a fixed threshold) accounts for caterers who run consistently better or worse than peers. A 1-SD drop is statistically significant — it's not noise. The 12-week historical window gives enough data to make the SD meaningful.

**Alternatives considered.**
- Absolute threshold (e.g. "any caterer below 3.5/5"): doesn't account for caterer-specific norms.
- Comparison against peer caterers: noisy if peer mix changes; harder to explain to the caterer being rotated.
- 8-week historical: less stable SD estimate.

**Implications.** Rotation is delayed by at least 4 weeks of data. Brand-new caterers don't have rotation triggers for the first 12 weeks. The decision log shows the SD calculation explicitly.

---

### D37 — Unsolicited feedback becomes an escalation, not a rating

**Decision.** When a parent, student, manager, or caterer sends feedback through a channel other than the formal rating link or survey (e.g. a complaint email, a phone call summary), the feedback is logged as an escalation for human review, not added to the rating aggregates.

**Derived from.** A4 (feedback in structured form for the rating pipeline; unstructured handled separately) · (operational judgement: unsolicited and solicited feedback have different trust and bias properties).

**Reasoning.** Unsolicited feedback skews negative (people complain more than they praise) and has unclear identity (which session? which meal?). Mixing it into the aggregates would distort the signal. Surfacing it as an escalation puts a human in the loop to interpret context.

**Alternatives considered.**
- Mix unsolicited feedback into ratings with a different weight: muddles the model.
- Discard unsolicited feedback entirely: loses real signal.

**Implications.** The escalations table grows to include "unsolicited feedback received" entries. The decision log shows the routing explicitly.

---

# 7. Caterer relationship and rotation

### D38 — Caterer scorecards are visible to caterers themselves on a weekly cadence

**Decision.** Each caterer receives a weekly summary email containing their rolling 4-week mean quality score (anonymised at the student level), their order volume, their MOQ compliance, and a comparison to their own historical baseline. They do not see per-student detail or comparison to other caterers.

**Derived from.** R §Quality maintained over time (visible measurement is the leverage) · A42 (transparency rather than threat) · (operational judgement: scorecards are a known mechanism for supplier discipline).

**Reasoning.** Visibility to the caterer is itself the discipline mechanism. A caterer who knows their score is being measured and shared back will adjust without explicit threats. Anonymising at the student level protects student privacy; not comparing to other caterers avoids unhelpful competitive dynamics (the caterer can't say "well at least I'm better than Y").

This is deliberately ambitious — most catering relationships don't include scorecards. V2 may strip this if Dylan prefers a less visible operating mode; V3 may refine.

**Alternatives considered.**
- No scorecard, internal scores only: loses the discipline effect.
- Scorecard including peer comparison: invites unhealthy dynamics.
- Daily/per-session scorecard: too frequent, normalises noise into the relationship.

**Implications.** The agent has a weekly scorecard-email tool. The scorecard generation joins quality ratings, orders, and MOQ events. The decision log shows the scorecard composition.

---

### D39 — Caterer non-response triggers escalation at 24 hours, with backup-caterer enquiry options

**Decision.** When an order has been sent and the caterer has not confirmed receipt within 24 hours, the system escalates. The escalation includes three drafted options: (a) a follow-up email to the caterer's primary contact, (b) a draft enquiry to an alternative eligible caterer asking if they can cover, (c) a note to proceed under explicit human direction.

**Derived from.** A41 (caterers respond within reasonable windows in the routine case) · R §Reliable meal delivery (caterer non-response handling).

**Reasoning.** 24 hours is well under the lead time (7+ days) and gives enough room for both diagnosis and recovery. Three drafted options give the human approver real choices, not a "what do we do?" question. The third option (proceed under direction) acknowledges that humans sometimes know things the system doesn't.

**Alternatives considered.**
- 48-hour threshold: gives more time but compresses recovery.
- Single drafted action (just chase the caterer): less optionality.
- Auto-fallback to backup caterer: removes the human from a relationship-sensitive decision.

**Implications.** The escalations table includes drafted-action templates. The decision log shows the non-response detection and the escalation composition explicitly.

---

### D40 — Caterer capability re-confirmation triggers when material conditions change

**Decision.** The system surfaces a re-confirmation escalation when material changes occur affecting a caterer's currently-served schools: enrolment growth above 20% term-on-term, schedule shifts (new session days), or sustained MOQ-shortfall warnings (3+ consecutive weeks). The escalation includes a drafted email to the caterer asking them to confirm continued capability.

**Derived from.** A10 (capability conditional on current operating conditions) · R §The coordinator out of the bottleneck (escalate for material changes affecting relationships).

**Reasoning.** Caterers commit to capability under specific conditions. If conditions shift, the system should ask rather than assume. The 20%, 3-week thresholds are operational starting points; V2 may refine them.

**Alternatives considered.**
- Annual re-confirmation: too infrequent; conditions can shift mid-year.
- Re-confirmation triggered by the human only: loses the proactive surfacing.

**Implications.** The agent monitors enrolment trends, schedule changes, and MOQ history. The escalation logic runs weekly with the order composition.

---

# 8. Agent runtime and decision logging

### D41 — An agent run is a discrete invocation with start, finish, and intent

**Decision.** The `agent_runs` table holds one row per agent invocation. Columns include `started_at`, `finished_at` (nullable for in-progress), `intent` (free text describing the run's purpose: "weekly order composition", "absence intake", etc.), `status` (running / completed / crashed / abandoned).

**Derived from.** R §Visible operation (inspectable record of every decision the agent makes).

**Reasoning.** Discrete runs anchor the decision log — every decision belongs to a run. The intent field makes the demo timeline navigable ("show me all the weekly-order runs from May"). Status captures the lifecycle including the crash case.

**Alternatives considered.**
- Continuous agent loop with no run boundaries: harder to audit, harder to demo.
- Multiple status fields rather than enum: more flexible, more complex.

**Implications.** Every tool call, every decision, every escalation references a run_id. The HTML demo surface groups by run.

---

### D42 — Crashed runs are detected by a staleness threshold of 30 minutes

**Decision.** A run with `status = running` and `started_at` more than 30 minutes ago, with no recent decision-log activity, is reclassified as `crashed` by the next agent invocation's housekeeping pass.

**Derived from.** D41 (run lifecycle includes crash) · R §Graceful failure (crashed runs must be detectable).

**Reasoning.** 30 minutes is a generous upper bound — the longest legitimate agent runs in V1 are weekly compositions, which complete in single-digit minutes. Stale runs need detection because they would otherwise occupy a "running" slot indefinitely.

**Alternatives considered.**
- Heartbeat mechanism: more sophisticated but adds infrastructure.
- Manual crash detection: human burden, defeats the purpose.

**Implications.** The next-run housekeeping pass scans for stale runs and updates their status. The decision log captures the reclassification.

---

### D43 — Tool calls and reasoning decisions share a single decision_logs table, distinguished by type

**Decision.** The `decision_logs` table records both tool calls and reasoning branches as rows, distinguished by a `decision_type` column (`tool_call`, `branch`, `escalation`, `rule_application`, `result`, etc.). Tool input and tool output are stored as JSON columns on the same row when relevant.

**Derived from.** R §Visible operation (every decision captured with context).

**Reasoning.** Tool calls and reasoning branches share most fields (timestamp, run_id, parent_decision_id, content). Two tables would duplicate the structure and complicate the demo timeline. Merging gives one ordered stream per run, which is exactly what the demo shows.

**Alternatives considered.**
- Separate `tool_calls` and `reasoning_branches` tables: cleaner type separation, but the demo needs them interleaved anyway.
- Polymorphic association: over-engineered.

**Implications.** Queries that want only tool calls filter on `decision_type = 'tool_call'`. The demo HTML iterates over all rows for a run in order.

---

### D44 — Decisions form a tree via parent_decision_id

**Decision.** Each row in `decision_logs` may reference a parent decision via `parent_decision_id`. The agent's reasoning forms a tree: a top-level branch may spawn sub-branches, tool calls, and results. No depth cap is enforced.

**Derived from.** R §Visible operation (decisions in context) · D41 (~15 tool-call cap bounds the tree size).

**Reasoning.** Agent reasoning is naturally nested. "Consider rotating GyG → check eligible alternatives → call get_alternatives(school=CHAC) → result: Lakehouse, Terrific → consider each → ..." The tree shape preserves this. The tool-call cap bounds the overall size so depth is implicitly constrained.

**Alternatives considered.**
- Flat sequence with reasoning encoded in content text: loses the structural information for the demo.
- Tree with hard depth cap (e.g. 5): forces artificial flattening at the cap.

**Implications.** The demo HTML renders the tree with indentation. Queries that want a specific sub-branch can recursively walk the tree.

---

### D45 — Tool outputs are stored as summaries, not full payloads

**Decision.** When a tool returns a large payload (e.g. a full session roster), the full result is not stored in `decision_logs`. A summary is stored (count, key fields, anomaly flags), and the full data is reconstructible from the database state by replaying the query.

**Derived from.** R §Visible operation (record useful, not overwhelming) · (operational judgement: large payloads in logs are an anti-pattern).

**Reasoning.** Full payloads bloat the log, slow the demo, and duplicate state already in the database. Summaries preserve the operational meaning. If V2 demonstrates that summaries lose important information, full payloads can be added back.

**Alternatives considered.**
- Full payloads for forensics: bloats the log.
- No tool output captured: loses the operational meaning.

**Implications.** Each tool defines its own summarisation. The summary is a small JSON object on the decision_logs row.

---

### D46 — Agent version and model identifiers are recorded per run

**Decision.** The `agent_runs` table includes `agent_version` (a string version identifier for the agent code) and `model_identifiers` (a JSON object: `{"router": "claude-haiku-4-5-20251001", "reasoner": "claude-sonnet-4-6"}`).

**Derived from.** R §Visible operation (forensic capability) · (operational judgement: behaviour changes with prompts and models).

**Reasoning.** Without this, "why did the agent do X last Tuesday" is unanswerable. Models update, prompts evolve, the agent's effective decision policy drifts. Per-run recording lets a future investigator correlate behaviour with version.

**Alternatives considered.**
- Single agent version at deploy time: misses model and prompt changes that don't bump the version.
- Per-decision recording: redundant within a run.

**Implications.** Deploy scripts must update the version identifier. The decision log demo surface displays the version subtly (footer per run).

---

# 9. Escalation mechanics

### D47 — Escalations have a hybrid closure model: auto-close on condition resolution, human-close on reply

**Decision.** Escalations close in two ways:
- **Auto-close** when the underlying condition disappears (the missing student turns up; the late caterer responds).
- **Human-close** when the human approver responds to the escalation email with a closure keyword (`resolved`, `dismissed`, `approved`, `rejected`).

**Derived from.** R §The coordinator out of the bottleneck (escalations for human-judged decisions) · R §Graceful failure (escalations don't stay open forever).

**Reasoning.** Pure auto-close misses cases where the human needs to acknowledge. Pure human-close clogs the queue with stale escalations the world already resolved. Hybrid covers both. Closure keywords give the human a low-effort response (no need to write prose if the situation is clear).

**Alternatives considered.**
- Auto-close only: misses acknowledgement cases.
- Human-close only: queue grows indefinitely.

**Implications.** The escalations table has `closed_at`, `closed_by` (system / human), and `closure_reason`. The agent monitors for auto-close conditions on each run.

---

### D48 — Escalation deduplication uses an agent-computed match key

**Decision.** When an escalation is created, the agent computes a `match_key` based on the escalation's identifying fields (e.g. for MOQ-shortfall, the key is `moq_shortfall:caterer_X:week_Y`). If an open escalation with the same key exists, the new one is recorded as a recurrence rather than a duplicate.

**Derived from.** R §Visible operation (avoid noise from repeated identical escalations).

**Reasoning.** Without deduplication, a recurring condition (e.g. Lakehouse MOQ shortfall every week) would produce a fresh escalation each week, drowning the queue. Match keys collapse recurrence into a single escalation with a recurrence count.

**Alternatives considered.**
- Hash of escalation content: too brittle (small wording changes cause non-matches).
- Manual deduplication: defeats automation.

**Implications.** The escalations table has a `match_key` column with an index. The `recurrence_count` increments on match. The decision log shows the dedupe decision explicitly.

---

### D49 — Severity is assigned per-instance, not per-type

**Decision.** Severity (`info`, `warning`, `urgent`, `blocking`) is assigned to each individual escalation based on context, not predetermined by escalation type.

**Derived from.** R §Visible operation (routine activity distinguishable from notable) · R §Graceful failure (urgent escalations must be visible).

**Reasoning.** The same escalation type can be high or low severity. An MOQ shortfall in October is `warning`; the same shortfall the night before delivery is `urgent`. Per-instance severity captures context that a fixed mapping would lose.

**Alternatives considered.**
- Severity-by-type lookup: simple but loses context.
- Single boolean (urgent / not): too coarse.

**Implications.** The escalations table has a `severity` column. The HTML demo surface colour-codes by severity. The agent's severity-assignment logic is itself logged.

---

### D50 — Escalation replies are parsed using a subject-line token, with fuzzy matching as fallback

**Decision.** Outgoing escalation emails include a token `[PADEA-ESC-{id}]` in the subject line. Incoming email replies are matched to escalations by extracting the token from the subject. If the token is missing or malformed (e.g. the human stripped it, or replied from a different thread), fuzzy matching on subject prefix and body keywords is the fallback.

**Derived from.** R §Visible operation (escalation lifecycle must be trackable).

**Reasoning.** Token-based matching is fast and unambiguous when the reply chain is clean. Fuzzy matching catches the messy real-world cases. Together they cover ~99% of reply scenarios.

**Alternatives considered.**
- Token only: brittle to human reply patterns.
- Fuzzy only: slower and less reliable.

**Implications.** Outgoing email composition must include the token. Incoming email processing has a two-stage matcher.

---

# 10. Incoming email handling

### D51 — Incoming emails are stored with full raw headers and bodies; attachments are metadata-only

**Decision.** The `incoming_emails` table stores `raw_headers` (full RFC822 headers as text), `body_text` and `body_html` (both forms preserved where available), `from_address`, `to_address`, `received_at`, `subject`, and `parsed_intent` (the agent's classification). Attachments are recorded by `filename`, `size`, `mime_type`, and `attachment_index`, but not by content.

**Derived from.** A20 (email-primary intake) · R §Graceful failure (input captured verbatim before interpretation).

**Reasoning.** Raw headers and bodies are essential for forensics — without them, interpretation failures lose the source data. Attachment bytes are expensive and rarely needed for the operational loop. The metadata preserves the link if V2 needs the bytes.

**Alternatives considered.**
- Parsed body only (drop raw): loses forensics.
- Attachments stored as bytes: bloats storage; most attachments are irrelevant signatures and images.

**Implications.** The agent's email-handling tool reads from this table. The decision log shows the interpretation of each email separately from the storage.

---

### D52 — Incoming emails are classified by intent at ingest

**Decision.** When an email is ingested, the agent (using the cheaper routing model) classifies its intent against a fixed set: `absence_notification`, `exclusion_notification`, `feedback`, `caterer_response`, `parent_question`, `unsolicited_feedback`, `other`. The classification is stored on the email row.

**Derived from.** A20 (email-primary intake) · R §The coordinator out of the bottleneck (system owns routing).

**Reasoning.** Classification at ingest means downstream processing (the absence handler, the feedback router) reads a small filtered set rather than scanning all emails. The classification is itself a decision logged in the operational record.

**Alternatives considered.**
- Per-handler classification: each handler scans all emails; wasteful and slow.
- No classification, single handler: doesn't scale to multiple intent types.

**Implications.** The `incoming_emails.parsed_intent` column is populated at ingest. Each downstream handler queries with `parsed_intent = X`.

---

# 11. Architecture and tooling

### D53 — SQLite for local development, Supabase for shareable mirror

**Decision.** The development database is SQLite, kept in-repo or in the local working directory. A Supabase Postgres instance mirrors the SQLite schema for sharing with Dylan, demo access, and any external consumer.

**Derived from.** R §Visible operation (demo surface reachability) · (operational judgement: zero-setup dev loop is worth the dialect-translation cost).

**Reasoning.** SQLite gives a zero-friction dev loop — the entire database is one file. Supabase provides the shareable URL and the Postgres compatibility needed for cloud demo access. The dialect translation between SQLite and Postgres is small (the schema uses common types and avoids vendor-specific features).

**Alternatives considered.**
- Postgres locally and remotely: requires running a local Postgres instance, more friction.
- SQLite only: no shareable URL.

**Implications.** Schema definitions must use SQLite-Postgres-compatible syntax. The mirror script handles dialect differences.

---

### D54 — Agent uses Anthropic API tool-calling with Haiku/Sonnet split

**Decision.** The agent is built on the Anthropic API's tool-calling primitive. Haiku 4.5 handles routing decisions (classification, simple branching, tool selection). Sonnet 4.6 handles harder reasoning (variety selection, escalation drafting, MOQ analysis). The split is configured per-tool, with each tool declaring which model it expects.

**Derived from.** R §Visible operation (genuine agentic behaviour, not prompt chains) · (operational judgement: cost vs quality tradeoff).

**Reasoning.** Tool-calling is the actual agentic primitive — the agent decides what to do next, not a hand-coded workflow. Splitting models keeps cost down on routine routing (Haiku is ~5x cheaper than Sonnet) while preserving quality on reasoning steps. The per-tool declaration makes the cost model auditable.

**Alternatives considered.**
- Sonnet for everything: simpler but expensive.
- Haiku for everything: cheap but reasoning quality degrades on complex tasks.
- Custom routing layer: over-engineered.

**Implications.** Each tool function declares its model. The agent run records which model was used at each step. Cost reports can be generated from the decision log.

---

### D55 — Agent run loop is capped at ~15 tool calls

**Decision.** Each agent run terminates if it has made more than 15 tool calls without reaching a terminal state. The terminating run is marked `abandoned` and an escalation is generated.

**Derived from.** R §Graceful failure (system must not hang indefinitely) · (operational judgement: runaway loops are the most common failure mode for agent systems).

**Reasoning.** 15 is large enough for the complex weekly composition (which makes ~10 calls in normal operation) and small enough to bound cost and time. An abandoned run produces an escalation explicitly — the human approver sees what the agent was attempting and can intervene.

**Alternatives considered.**
- Unbounded loop: runaway risk.
- Smaller cap (5-10): too tight for complex tasks.
- Cost-based cap: harder to predict and explain.

**Implications.** Tools that need many sub-operations (e.g. iterating over students) batch internally so they count as one tool call. The decision log shows the call count.

---

### D56 — Demo surface is a regenerated HTML file per run

**Decision.** After each agent run, a static HTML file is generated showing the run's timeline of decisions. The file lives at `decision_logs/run_{id}.html` and is the primary demo surface. It is regenerated on each run; old files are kept for history.

**Derived from.** R §Visible operation (legible, real-time inspectable) · (operational judgement: HTML is universal and replayable).

**Reasoning.** Static HTML works in any browser without infrastructure. Per-run files mean each demo segment is self-contained. The regeneration approach keeps the surface fresh without complex live-update plumbing.

**Alternatives considered.**
- Live web app: heavyweight, requires hosting.
- Markdown logs: less visual structure.
- Plain text: loses the colour coding and tree structure.

**Implications.** The HTML generator is a tool the agent invokes at end-of-run. The HTML template uses CSS for colour-coding and indentation for tree structure.

---

### D57 — Email I/O is simulated via text files for V1

**Decision.** Incoming and outgoing emails live in `emails/incoming/` and `emails/outgoing/` as text files. No real Gmail or SMTP integration. The agent reads from incoming/ and writes to outgoing/.

**Derived from.** R §Graceful failure (deterministic demo) · (operational judgement: real email deferred until system is proven).

**Reasoning.** Simulated email lets the demo be replayable and removes the risk of real outbound emails being sent during development. The text-file format is human-readable for debugging and version-controllable for test fixtures.

**Alternatives considered.**
- Real Gmail integration in V1: OAuth, deliverability, blast-radius risk.
- Mock SMTP server: more realistic but adds infrastructure.

**Implications.** The agent's email tool reads/writes filesystem paths, not network endpoints. V2 may add real email integration; the tool interface is designed to absorb that change.

---

# 12. Schema patterns

### D58 — Event-storing as the default; current state is derived

**Decision.** Where a piece of information has a history, the schema stores events (timestamped rows) rather than current state. Examples: `absences` records each absence event with `received_at`; `caterer_school_capabilities` would, in a future-perfect design, record assignment events rather than current status. Exceptions exist where event-storing would over-engineer (D24 margin pool config, D7 capability current-status).

**Derived from.** R §Visible operation (forensic capability) · (operational judgement: event sourcing is the durable default).

**Reasoning.** Storing events preserves history. Storing current state alone loses the "why is it that way?" question. Where event-storing would be excessive (the margin pool doesn't have a meaningful history), state-storing is allowed as a documented exception.

**Alternatives considered.**
- Full event sourcing: too much ceremony for V1.
- State-only: loses history.

**Implications.** New entities default to event-storing. Exceptions are documented in the decision register entry that creates them.

---

### D59 — Every primary key is an auto-incrementing integer

**Decision.** All primary keys in the schema are `INTEGER PRIMARY KEY AUTOINCREMENT` (SQLite) / `BIGSERIAL PRIMARY KEY` (Postgres). No UUIDs, no composite keys, no natural keys.

**Derived from.** D53 (SQLite + Postgres dialect compatibility) · (operational judgement: integer keys are the path of least surprise).

**Reasoning.** Integer keys are universally understood, performant, and easy to reference in logs and demos. UUIDs are overkill for a single-system V1; composite keys complicate joins; natural keys (e.g. email addresses) introduce mutation risk when the natural key changes.

**Alternatives considered.**
- UUIDs: useful for distributed systems; over-engineered for V1.
- Composite keys: useful when (a, b) is the natural identifier; complicates joins.

**Implications.** Every table has an `id` column. References between tables use foreign keys to the integer id.

---

### D60 — JSON columns are used where the shape is genuinely variable

**Decision.** Where a column's content shape varies meaningfully between rows (escalation referenced_entities, agent_runs model_identifiers, decision_logs tool_input and tool_output), JSON columns are used and queried via SQLite's JSON1 extension or Postgres native JSON.

**Derived from.** D43 (decision_logs holds mixed types) · D46 (model_identifiers is a small variable object).

**Reasoning.** Variable-shape data either gets columns (one per possible field, mostly null) or JSON. JSON is honest about the variability. The JSON1 extension makes queries reasonable; Postgres JSON is native.

**Alternatives considered.**
- One column per possible field: schema bloat.
- Free text: loses structure.

**Implications.** Some queries on JSON content are slower than columnar equivalents. V2 may extract heavily-queried JSON fields into proper columns.

---

# 13. Open questions

### OQ1 — Late-cancellation policy

What the human approver does when a whole session is cancelled after the order has been sent. Options: pre-commit to a policy (always recall; always accept and donate; pay caterer regardless), or leave as case-by-case judgement. Affects whether the agent drafts a specific recall message or a neutral context summary.

**For Dylan meeting:** Yes. Wednesday 27 May.

---

### OQ2 — Student rating intake channel

How students physically submit ratings. Options: reply-to email parsed by the agent; web form posted to an endpoint; integration with an existing tool (Fillout Forms). Each has different identity-resolution, spam, and timing properties.

**For Dylan meeting:** Yes. Wednesday 27 May.

---

### OQ3 — Default manager pattern prediction

Whether the agent should predict which manager will run a session when the roster is incomplete. The 7 named managers in the data have stable patterns (Lucian: ISHS Mon+Tue; Ethan: ISHS Thu + CHAC Mon; etc.). Whether this prediction is needed at all is itself unclear. Lean toward removing unless evidence emerges.

**For Dylan meeting:** Possibly. Confirm whether manager assignments are always known well in advance in practice.

---

### OQ4 — Weekly preference email response rate expectations

D32 commits to weekly parent emails. We don't have a baseline response rate to calibrate the default-acceptance behaviour. V1 commits to "all options acceptable" as the default for non-responders, but if response rates collapse to 20%, the system is effectively running on default for 80% of meals.

**For Dylan meeting:** No, but worth surfacing in the memo as a known V1→V2 risk.

---

### OQ5 — Caterer scorecard appetite

D38 commits to weekly caterer-visible scorecards. Whether Dylan and Padea's caterers would actually engage with this surface, or perceive it as adversarial, is not established. If the answer is "they wouldn't read it," the scorecard is dead weight.

**For Dylan meeting:** Yes. Wednesday 27 May.

---

# 14. V2 Cut Candidates

The following decisions are explicit candidates for V2's pedantic stripping pass. Each could be argued for as V1-ambitious-but-not-strictly-required. The V2 work will examine each and decide. Some will go entirely; some will go and return in V3.

- **D5** (shared dietary vocabulary across entities) — V1 only uses it for students; the shared structure is overhead.
- **D11** (dietary meals excluded from MOQ) — V2 may collapse to "count everything against MOQ" if simpler.
- **D18** (junction table for tutor assignments) — V1 only stores the manager; the junction is empty otherwise.
- **D25** (10% partial-exclusion attendance buffer) — V2 may set this to zero pending real data.
- **D32–D34** (parent weekly selection + student rating) — the entire V1 feedback mechanism. V3 will likely replace with manager + tutor + term-survey model.
- **D35** (rater-baseline normalisation + timing weighting) — too sophisticated for V1 if rating data is sparse.
- **D36** (1-SD rotation trigger) — may simplify to an absolute threshold.
- **D38** (caterer-visible scorecards) — ambitious and not strictly required for the V1 demo.
- **D39** (24-hour caterer non-response escalation with backup-caterer drafting) — V2 may collapse to a simpler chase-only escalation.
- **D40** (capability re-confirmation triggers) — proactive surfacing that V2 may make reactive only.
- **D45** (tool output summaries) — V2 may store full payloads for forensics.
- **D52** (intent classification at ingest) — V2 may classify per-handler to keep the routing simpler.
- **D55** (~15 tool call cap) — may tighten or loosen based on observed run lengths.

---

*End of decision register. The next document is `schema.md` (V1), which embodies these decisions in concrete tables, columns, and relationships. The schema's primary job is to make these decisions executable.*
