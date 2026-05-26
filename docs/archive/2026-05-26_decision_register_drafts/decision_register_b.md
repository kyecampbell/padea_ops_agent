# Decision Register — Padea Operations Agent (V1)

**Purpose:** What we are choosing where assumptions and requirements alone do not determine the answer. A requirement says what the system must do; an assumption fills a gap in what we know; a decision commits to *how* a requirement is satisfied given those assumptions. Each entry below is one such commitment.

**Compiled:** 26 May 2026
**Companion documents:** `data_observations.md`, `assumptions.md`, `requirements_v1.md`, `schema.md`.

---

## How to read this document

Each decision is a commitment between operationally workable options. The decision is stated concretely, the derivation cites the assumptions (A-numbers), observation sections, and requirement sections it depends on, the reasoning explains why this version was chosen, alternatives note what else was considered, and implications name the downstream consequences for schema and agent behaviour.

This register is the **V1 ambitious** version. V2 will strip; V3 will reinstate selectively from the ledger of cuts. Where a choice could go either way, the more ambitious option is preferred so that the strip-and-reinstate journey has real material to work on. A list of V2 Cut Candidates appears at the end, predicting which decisions are most likely to be the first to go under a pedantic stripping pass.

Decisions are grouped by domain. Numbering is global (D-01, D-02, ...) so that cross-references survive section reorganisation.

---

# Data model and identity

### D-01 — Surrogate keys for every entity; natural keys nowhere primary

**Decision:** Every entity (student, enrolment, school, session, caterer, contact, menu item, order, absence, exclusion, feedback, agent run, decision, tool call) uses an opaque UUID primary key. Natural identifiers (student name, caterer name, school code) live in indexed columns but never as primary or foreign keys.

**Derived from:**
- Observation: §Cross-file consistency — files reference entities by name/label, but the data is "messy in formatting (...) coherent in identity"
- Assumption: A5 (two students sharing a name are different by default)

**Reasoning:** Cross-school name collisions (13 cases in the source data) mean any natural key on `student_name` collapses distinct identities. UUID keys make the non-collapse default mechanical rather than a thing we need to be careful about. Caterer-name fields with placeholder values (`Big Mom`, `Big Chicken`) and email addresses with cross-routed domains reinforce the same point: natural identifiers in this data are not stable.

**Implications:** Every join and reference is through UUID. Ingest scripts mint UUIDs; the source name/label is preserved as a `display_name` field for human-readable surfaces.

---

### D-02 — Enrolment is a first-class entity that owns year-level, dietary, and opt-out

**Decision:** A `student` row holds identity (name, contacts) only. An `enrolment` row links (student × school × term) and carries `year_level`, dietary attribute fields (D-04), `catering_opted_out` (D-05), and any other context that varies by where a student is enrolled. A student progressing year-to-year, or attending two schools, materialises as multiple enrolment rows rather than mutating a student record.

**Derived from:**
- Observation: §Students — dietary, year-level, parent contacts all appear per-sheet-row, not per-student
- Observation: §Duplicate names across sheets — Benjamin Wilson and Zachary Anderson have differing dietary disclosures at their two schools
- Assumption: A6 (year level is a property of enrolment)
- Assumption: A7 (catering opt-out is a property of enrolment)

**Reasoning:** The source data records these fields per sheet-row, and the operational reality permits divergence (Benjamin Wilson is `No Beef` at JPC, blank at ISHS). Storing them on the student would force reconciliation we cannot perform safely. Storing them on the enrolment lets the same person hold different disclosures at different schools, and lets year-level changes term-to-term flow naturally.

**Alternatives considered:** Storing dietary on the student with a "schools where it applies" subset; storing year-level on the student with a "current year level" attribute. Both require mutation on a record that conceptually shouldn't mutate, and neither handles the divergent-disclosure case.

**Implications:** Matching, ordering, and feedback all join through enrolment, not student. A student record is sparse — name, contact details, optional birth year, nothing operational. The merge mechanism (D-03) operates at student-record level without affecting enrolment-level data.

---

### D-03 — Students remain non-collapsed by default; an explicit `student_identity_merge` table records confirmed same-person links

**Decision:** Each sheet-row at ingest creates a distinct student record. A separate `student_identity_merge` table records (student_id_a, student_id_b, confirmed_by, confirmed_at, evidence_notes) where an operator has positively asserted the two records refer to the same person. Both original records remain; queries that need a unified view resolve through the merge table.

**Derived from:**
- Observation: §Duplicate names across sheets — 13 cross-school name matches, 6 with year-level match (plausibly same person), 7 differing (almost certainly different)
- Assumption: A5 (default treatment is non-collapse)

**Reasoning:** Auto-merging the 6 same-year cases risks false positives where two different students share a name and were both enrolled at age 17. Not merging risks treating the same person as two for variety, feedback aggregation, and absence prediction. Surfacing the merge as an operator action with evidence captured gives us the option of consolidation without the risk of doing it wrong silently.

**Alternatives considered:** Auto-merge on (name, year_level) match — rejected per A5. Heuristic merge with confidence score — increases system surface area and creates a probability layer the operator must reason about.

**Implications:** A `student_unified_view` SQL view applies the merge table to produce canonical-student rollups for analytics and predictive features (per-parent absence rate, taste compatibility). The view is non-destructive — the underlying rows remain. Schema must support a merge being reversed later.

---

### D-04 — Dietary requirements decomposed into atomic boolean attributes per enrolment

**Decision:** The freeform `Dietary` column is replaced at ingest by explicit per-enrolment attributes: `requires_halal`, `requires_vegetarian`, `requires_gluten_free`, `requires_dairy_free`, `excludes_nuts`, `excludes_pork`, `excludes_beef`, `excludes_red_meat`, `excludes_fish`, `excludes_seafood`, `excludes_shellfish`. Plus `nut_allergy_severity` enum (`preference` / `allergy` / `anaphylaxis`).

**Derived from:**
- Observation: §Dietary information — 11 distinct dietary concepts mixed in free text, 18 distinct cell values, comma-grouped multi-tags
- Assumption: A3 (blank means no requirements)
- Requirement: §The non-negotiable safety floor — "every menu item the system reasons about must have its dietary properties resolved in advance"

**Reasoning:** Matching against a free-text column requires a parser at every match point. Decomposing once at ingest moves the parser to the boundary and lets the matching engine read booleans. The atomic attributes also make per-attribute analytics tractable (D-66) — "how many enrolments require halal" becomes a `COUNT WHERE requires_halal`, not a text search.

The severity enum on nuts (not on other excludes) is deliberate: the operational consequence of a missed match on a peanut allergy is different from a missed match on "no beef". Other excludes default to preference-level handling.

**Alternatives considered:** Keep the freeform column and parse at match time — fragile, slow, duplicates work. JSON column with normalised tags — better than freeform but loses query indexability.

**Implications:** Ingest needs a robust tag parser (e.g. `"Nut Free, No Shellfish, Opted out of Catering"` → `excludes_nuts=true, excludes_shellfish=true, catering_opted_out=true`). The dietary controlled vocabulary (D-17) governs which tags are recognised; anything outside the vocabulary escalates rather than being silently dropped.

---

### D-05 — `Opted out of Catering` becomes its own `catering_opted_out` field, not a dietary attribute

**Decision:** The dietary parser at ingest extracts the `Opted out of Catering` marker (alone or in a comma-grouped cell) and stores it in an enrolment-level `catering_opted_out` boolean field, separate from any dietary attribute.

**Derived from:**
- Observation: §Dietary information — `Opted out of Catering` appears alongside dietary requirements (6 alone, 1 combined with other tags)
- Assumption: A7 (catering opt-out is a property of enrolment)

**Reasoning:** Opt-out is not a dietary requirement; it changes whether the student is in the order at all. Treating it as a dietary attribute means the matching engine has to special-case it; treating it as a top-level enrolment field means the order composer reads it and short-circuits before matching runs. Lei Li at ISHS Tuesday (the combined-tag case) demonstrates the data already entangles them — the parser separates them.

**Implications:** Order composition excludes opt-out enrolments before any dietary or variety logic runs. They are not counted toward MOQ. They do not receive parent meal-option emails. They still appear in attendance reconciliation (an opted-out student who attends and walks up to the meal table is an event the system records, but they are not provisioned for).

---

### D-06 — Nut-allergy severity is captured as a three-level enum

**Decision:** The `nut_allergy_severity` enum on enrolment takes one of three values: `preference` (default for any enrolment with `excludes_nuts=true`), `allergy` (manually elevated), `anaphylaxis` (manually elevated). The source data does not distinguish these; the field starts at `preference` and is elevated by operator action with a recorded source.

**Derived from:**
- Observation: §Data expected but not present — "Allergy severity. Dietary tags such as `Nut Free` do not distinguish preference from anaphylaxis-level allergy"
- Requirement: §The non-negotiable safety floor — "A nut-allergic student cannot be served a meal containing or contacting nuts"

**Reasoning:** Requirement §Non-negotiable safety floor names nut allergy explicitly. Anaphylaxis-level allergy implicates not just whether a meal contains nuts but whether the caterer can certify against cross-contamination. The system needs a way to express "this enrolment requires cross-contamination certification, not just nut-absence". Defaulting all `Nut Free` entries to `preference` matches the conservative reading of the source data (no severity was specified) while making the elevation pathway explicit.

**Implications:** For enrolments at `allergy` or `anaphylaxis`, the matching engine requires an additional caterer attestation field on the matched item. Where that attestation is absent, the match escalates rather than completing. The elevation event is an operator-initiated action with audit trail (D-72).

---

### D-07 — Halal status is pre-resolved at menu ingest as an explicit `is_halal` attribute, not derived at runtime

**Decision:** At menu ingest, each item is resolved to a fixed `is_halal` boolean (and the full set of dietary attributes — `is_vegetarian`, `is_gluten_free`, `is_dairy_free`, `contains_nuts`, `contains_pork`, `contains_beef`, `contains_red_meat`, `contains_fish`, `contains_seafood`, `contains_shellfish`). Halal is computed from `contains_pork=false` per A8 and then stored as an explicit attribute alongside the source `contains_pork` flag.

**Derived from:**
- Observation: §Menus — legend states "Assume all non-pork meals are halal"; pork appears in 4 of 40 items
- Assumption: A8 (non-pork is halal)
- Requirement: §The non-negotiable safety floor — "menu item the system reasons about must have its dietary properties resolved in advance"

**Reasoning:** Resolving at runtime would mean every halal match re-evaluates the rule. Storing the resolved attribute makes the match a single boolean read, makes the audit trail explicit ("this match found `is_halal=true` because `contains_pork=false` was recorded at ingest on date X by source Y"), and lets us update the resolution rule centrally if the policy ever changes — for example, if Padea later requires positive halal certification rather than non-pork inference, the resolution at ingest changes, and the matching engine is untouched.

**Alternatives considered:** Compute `is_halal` as a derived column / SQL expression. Loses audit clarity — there's no record of when the rule was applied. Compute at match time. Requires the matching engine to know dietary semantics.

**Implications:** Ambiguous-protein items (Terrific's `Spaghetti meatballs`, etc.) cannot be resolved at ingest without a positive ingredient list. They flag as `dietary_resolution_pending` and route to the operator before being made available for matching.

---

### D-08 — `VO` (vegetarian option) is modelled as a per-item caterer capability flag; substitutions become a distinct item identity in the order

**Decision:** Each menu item has a `vegetarian_option_available` boolean. When a vegetarian enrolment is matched to a `VO`-flagged item, the resulting order line carries an explicit `vegetarian_substitution` flag, and feedback against the substituted meal is recorded as a separate item-identity (`<item_id>::vo`) for the purposes of rating aggregation.

**Derived from:**
- Observation: §Menus — "The `VO` annotation describes a caterer capability to substitute a vegetarian variant on request rather than a property of the item as listed"
- Assumption: A9 (VO is a caterer capability)

**Reasoning:** Treating the substitution as the same item conflates feedback — a rating on the vegetarian substitute applies to a recipe that has not been delivered as listed. The substituted item is operationally a different meal. The double-identity `<item_id>::vo` preserves the link to the parent item (so a caterer's overall scorecard is not fragmented) while keeping the rating signals separable.

**Implications:** Caterer scorecards (D-62) need to roll up parent and `::vo` variants in displays but keep them separable in analytics. Order communication to the caterer makes the substitution explicit in the order line text.

---

### D-09 — Tutors and managers are a single population; the manager role is a property of a session assignment

**Decision:** A single `tutor` table holds identity (name, email, mobile). A `session_assignment` table links (tutor × session) with `role` enum (`manager` / `tutor`), `status` enum (`expected` / `actual`), and timestamps. A session has one manager-role expected assignment and one manager-role actual assignment, which may reference different tutors when cover occurs.

**Derived from:**
- Observation: §Session managers — 7 distinct names across 11 sessions, no separate manager population in the data
- Assumption: A17 (managers are tutors carrying a per-session manager role)
- Assumption: A18 (tutor record holds only what catering needs)
- Assumption: A19 (expected vs actual manager)

**Reasoning:** A single population avoids a second tutor-like entity. Role-as-assignment-property avoids encoding role on the tutor record (which would force special handling when a tutor managed one session and tutored at another). Expected/actual on the assignment captures cover events without inventing a separate "tutor absence" concept.

**Implications:** Cover events are detectable by querying for `expected.tutor_id != actual.tutor_id` on the same session. The list of session managers in the dashboard is derived from `session_assignment WHERE role='manager' AND status='expected'`. Where the data ingested gives only the manager's first name (e.g. "Triet"), the tutor table holds the resolved identity and the ingest carries a `source_label` to support reconciliation.

---

### D-10 — Caterer capability is modelled at (caterer × school × day-of-week) granularity with effective-from / effective-to dating

**Decision:** A `caterer_capability` table holds rows of the form `(caterer_id, school_id, day_of_week, status, effective_from, effective_to, source)`. `status` is an enum: `currently_serves` / `able_to_serve` / `previously_served` / `confirmed_unable`. A capability fact is queried as "the row valid on date D for (caterer, school, dow)". "Currently serves" rows are a subset of capability where the date window contains today and `status='currently_serves'`.

**Derived from:**
- Observation: §Caterer capability and current assignments — "currently serves" and "also able to serve" sets per caterer
- Assumption: A10 (capability applies to current operation, not hypothetical)
- Assumption: A12 (capability is granular to caterer × school × day-of-week)
- Assumption: A13 (distance/capacity/time-window absorbed into the capability statement)

**Reasoning:** A12 makes day-of-week granularity load-bearing. Effective-dating makes the historical view auditable: when a caterer is added to a school's capability set, the date and source of the addition are preserved. The four-state enum captures the operational reality that a caterer that previously served a school but no longer does is materially different from one that never has.

**Alternatives considered:** Two boolean columns `currently_serves` and `able_to_serve` on a single (caterer, school) row. Loses day-of-week. Loses effective-dating. Forces the schema to support `currently_serves=true, able_to_serve=false` which is incoherent.

**Implications:** Adding a new school session day requires a fresh capability check (per A12) — the system can recognise this by checking whether `(caterer, school, new_dow)` rows exist, and if not, surface the gap. The capability record is what the rotation alternative-evaluator (D-59) reads to identify viable substitutes.

---

### D-11 — Caterer contacts carry an independent role-bitmap rather than a single role enum

**Decision:** Each `caterer_contact` row has four independent boolean fields: `is_order_taker`, `is_chef`, `is_primary_contact`, `is_cc_on_orders`. Multiple contacts per caterer are permitted; any combination of role booleans is permitted on any contact.

**Derived from:**
- Observation: §Caterer contacts — 4 distinct role combinations across 6 contacts, with both single-role and multi-role contacts represented
- Assumption: A16 (any combination of four roles is permitted)

**Reasoning:** A single role enum forces a choice the data shows is unnecessary — Big Mom is both order-taker and chef; that's two roles, not a new enum value. Independent booleans naturally express what the data carries, including the four observed combinations.

**Implications:** Outbound order emails (D-43) read `is_primary_contact AND is_order_taker` for the `To:` line and `is_cc_on_orders` for the `Cc:` line, supporting the data's existing routing intent (GyG chef Medium Giraffe CC'd, Terrific chef James Chern not).

---

### D-12 — Caterer pricing is decomposed into explicit fields for unit price, GST treatment, and delivery fee structure

**Decision:** The `caterer` table carries `price_per_item_cents`, `price_includes_gst` (boolean), `delivery_fee_structure` enum (`none` / `per_trip` / `per_school_per_trip` / `per_item`), `delivery_fee_cents`, and `gst_rate_percent` (default 10 for AU but field-stored). Order economics reads these explicitly.

**Derived from:**
- Observation: §Caterers — Kenko $5.50 (incl GST), Lakehouse $35.00 (excl GST), GyG $50 per trip, Terrific $30 per school per trip, Kenko $10 per school per trip
- Observation: §Caterers — "GST treatment varies: two caterers quote inclusive of GST, two exclusive. Delivery fee structures differ in kind, not just amount"

**Reasoning:** Delivery fees differ in *kind* — flat-per-trip versus per-school-per-trip changes the calculation entirely on a same-day multi-school delivery (GyG Monday: Loreto + CHAC). Collapsing this into a single "delivery fee" field produces silent pricing errors on the cases where the structure matters most. GST treatment varies item by caterer, so a "tax-adjusted price" derived field needs to know whether each input is inclusive or exclusive.

**Implications:** Order economics computes per-caterer-per-week total as `(item_count × price_per_item_cents) + delivery_fee` where the delivery fee resolves through the structure enum and the per-school-per-trip case sums one fee per school. GST-inclusive items are passed through; GST-exclusive items add the GST rate at calculation time. Stored in cents to avoid float arithmetic.

---

### D-13 — MOQ is modelled as a tier table (caterer × variety_level → min_units) with weekly evaluation against full-week demand

**Decision:** A `caterer_moq_tier` table holds rows of the form `(caterer_id, menu_item_count, min_weekly_units)`. For Lakehouse: (4, 15), (5, 20), (6, 25). The order composer queries: "at our chosen variety level, what is the minimum weekly unit count we must order?" and compares to projected weekly demand.

**Derived from:**
- Observation: §Minimum order quantity (MOQ) — three-tier MOQ values per caterer
- Observation: §Minimum order quantity (MOQ) — "MOQ scales with menu variety — ordering more menu items requires a higher weekly minimum"
- Assumption: A23 (weekly composition with full week in view)

**Reasoning:** MOQ varies by variety level, so a single per-caterer min value cannot represent it. Weekly evaluation against the full week (per A23) means the MOQ check runs once per order composition, not per session, which matches the operational reality: Padea sends one order per caterer per week and meets MOQ across the week's combined sessions.

**Implications:** Variety pruning (D-22) reads MOQ tiers to determine the highest variety level achievable within current demand. Caterers with `menu_item_count` records below 4 or above 6 are extensible without code change.

---

### D-14 — Menu items at ingest are tagged with `dietary_resolution_status` and ambiguous items block matching until resolved

**Decision:** Each `menu_item` row has a `dietary_resolution_status` enum (`resolved` / `pending` / `escalated`). Items resolve automatically when all dietary attributes can be inferred from the item name and legend. Items with ambiguous protein (e.g. "Spaghetti meatballs", "Asian Noodles & Chicken") flag `pending`. Items the operator cannot resolve flag `escalated`. Matching reads only `resolved` items; `pending` and `escalated` items cannot be served.

**Derived from:**
- Observation: §Menus — "Per the legend's halal rule, the halal status of any ambiguously-named item depends on whether the actual recipe contains pork"
- Requirement: §The non-negotiable safety floor — "dietary properties resolved in advance"

**Reasoning:** Requirement is explicit that dietary properties cannot be inferred at match time. Items the system cannot resolve are explicitly held back rather than silently included. The three-state enum makes the resolution state queryable for the operator's menu-quality dashboard.

**Implications:** New caterer onboarding includes a menu-resolution step. The operational dashboard surfaces `pending`/`escalated` item counts per caterer. An order that would have used a `pending` item escalates rather than substituting silently.

---

### D-15 — Sessions are stored as concrete dated instances; recurring patterns are derived, not stored as templates

**Decision:** Each calendar instance of a session is one row in `session` with concrete `date`, `start_time`, `end_time`, `dinner_time`, `dinner_duration_minutes` (default 30 per A21), `school_id`, `building`, and `manager_assignment_id`. Recurring patterns (e.g. "Loreto runs Monday + Tuesday") are computed by grouping sessions on (school_id, day_of_week) rather than stored as separate template entities.

**Derived from:**
- Observation: §Schools and sessions — sessions enumerated as date+school+manager rows
- Observation: §Session timing — "Session times in the dataset are recorded as strings (...), not as parsed timestamps. Conversion happens at ingest"
- Assumption: A20 (180-minute structural rule)
- Assumption: A21 (30-minute dinner duration)
- Assumption: A22 (no school has more than one session per day)

**Reasoning:** A session-template table would carry recurrence rules and instantiate concrete sessions from them. For Padea's scale and the once-weekly ordering cadence, instantiation is overhead without operational benefit. Patterns are computed when needed (e.g. for the dashboard's "this school's typical days" view). Adding a session day is one row, not a template edit-and-regenerate.

**Implications:** A weekly job materialises sessions for the upcoming week from the prior week's pattern, surfacing changes for operator confirmation before order composition begins. If sessions become irregular enough that derivation breaks, the template entity can be added in V2/V3 without invalidating session history.

---

### D-16 — Same-day same-caterer multi-school delivery is captured as a `delivery_run`, distinct from a session

**Decision:** A `delivery_run` table groups one or more session deliveries by (caterer, date) when the caterer is making one logistical trip to multiple schools, or one trip to one school. Delivery fee computation reads delivery runs, not sessions. A run carries `planned_departure_time`, `planned_arrival_times` (JSON per session), and `confirmed_delivery_timestamps` per session.

**Derived from:**
- Observation: §Building, year levels, and concurrent sessions — "Guzman y Gomez is scheduled to deliver to two schools simultaneously on Monday 1 May 2026 — Loreto College and Cannon Hill Anglican College, both with a 5:00pm dinner time"
- Assumption: A11 (caterer can serve multiple schools same day where logistics permit)

**Reasoning:** The same delivery event affects two sessions in the GyG-Monday case; a per-session model would either double-count the trip or require ad-hoc fee allocation. The run gives the natural shape for confirming delivery (one confirmation event per arrival, two confirmations per run for GyG Monday) and for fee structures that price per trip rather than per school.

**Implications:** Delivery confirmation (D-26 implications) is per session-within-run, not per run as a whole. A run with one confirmed session and one unconfirmed session escalates the unconfirmed session as a partial-arrival event.

---

### D-17 — A dietary controlled vocabulary lives in the schema and governs ingest, escalation, and analytics

**Decision:** A `dietary_tag_vocabulary` table holds the canonical list of dietary tags (`halal`, `vegetarian`, `gluten_free`, `dairy_free`, `nut_free`, `no_beef`, `no_pork`, `no_red_meat`, `no_fish`, `no_seafood`, `no_shellfish`, `opted_out_of_catering`). Each entry has a canonical form, accepted aliases (case variants, punctuation variants), the target attribute on the enrolment record, and a `severity_overridable` flag. Ingest matches source text against the vocabulary; unmatched text escalates rather than being dropped.

**Derived from:**
- Observation: §Dietary information — 18 distinct cell values, 11 distinct concepts, varied capitalisation and spacing
- Requirement: §The non-negotiable safety floor — "the system must not proceed on assumption" where information is missing or ambiguous

**Reasoning:** Without a controlled vocabulary, ingest tolerates new tag spellings silently. A new dietary tag — say "Kosher" — appearing in a future enrolment sheet would be ignored, which violates the safety floor. The vocabulary makes unrecognised tags loud (an escalation, not a drop) and gives the operator a single place to extend recognition.

**Implications:** Schema migration when the vocabulary changes (rare, by design). Ingest produces escalations for unknown tags with the source row and raw value preserved. Analytics queries read from the vocabulary to enumerate dietary cohorts.

---

# Order generation

### D-18 — Weekly order composition runs once per (caterer, week) as a single atomic transaction

**Decision:** An `order_composition_run` row exists per (caterer, week), composed by the agent on a fixed weekly cadence (Thursday for the following week, per current operation). The run captures: input snapshot (enrolment counts, absences, exclusions, dietary, parent meal selections, walk-up predictions), output (per-session per-item quantities, MOQ analysis, total cost), and the decision narrative. The run is atomic: it either completes with a `pending_human_review` order or fails with full state preservation.

**Derived from:**
- Observation: §Order timing references in source materials and project context — current Thursday-for-following-week cadence
- Assumption: A23 (weekly composition with full week in view)
- Assumption: A24 (order not amended for subsequent absences)
- Requirement: §Reliable meal delivery — "send each order with adequate lead time"

**Reasoning:** Composition needs a full snapshot at one moment to make MOQ evaluation correct; piecewise composition risks MOQ checks against partial data. Atomicity makes failure handling straightforward: a failed composition leaves no half-state in the order surface.

**Implications:** A `composition_input_snapshot` JSON column captures the exact inputs at composition time, supporting replay and audit. Late-arriving absences after composition completion route to the post-send absence flow (D-39), not a recomposition.

---

### D-19 — Order storage is per (caterer × week) with per-session line breakdown

**Decision:** A `weekly_order` row per (caterer, week) holds the order-level metadata (caterer, week_start, status, total_cost, MOQ analysis, lead-time deadline). An `order_line` table holds rows of (weekly_order_id, session_id, menu_item_id, quantity, enrolment_links). The outbound caterer email is rendered from these tables.

**Derived from:**
- Observation: §Caterers — caterers serve multiple sessions per week, with weekly MOQ semantics
- Assumption: A23 (weekly composition)
- Requirement: §Reliable meal delivery — "address each order to the correct caterer with the correct contact"

**Reasoning:** Per-session lines support the caterer-facing per-delivery breakdown (D-21) without aggregating away the data we'll need for delivery confirmation, post-session reconciliation, and walk-up tracking. Per-week parent aggregates support MOQ checks and caterer cost summation without per-line re-derivation.

**Implications:** Order amendments (rare, per A24) operate on the weekly order's status field, not on individual lines after send. Per-enrolment match decisions (D-24) attach to order lines.

---

### D-20 — Operational margin is per-school configurable with a learned adjustment derived from trailing reconciliation

**Decision:** A `school_margin_config` table holds (school_id, base_margin_percent, base_margin_floor_units). The order composer reads the base value and adds a learned adjustment computed from the trailing 4-week reconciliation signal (walk-ups minus excess meals). The total adjustment is capped at ±50% of base. Where insufficient history exists (<2 weeks of reconciliation), only the base value is used.

**Derived from:**
- Assumption: A25 (operational margin required)
- Requirement: §Reliable meal delivery — "small enough to keep order economics tractable and large enough to avoid routine shortfalls. Where the margin is regularly exhausted or regularly unused, the system must surface this as a signal for re-sizing"

**Reasoning:** A pure configured value cannot adapt; a pure learned value would be unstable at low data volumes. The base+bounded-adjustment shape captures both. Per-school configuration is necessary because schools differ in walk-up patterns (a school with many late-notifying parents needs more margin than a punctual school).

**Alternatives considered:** Network-wide margin — ignores school-level variation. Per-session margin — too granular to learn at meaningful sample sizes. Margin learned without bounds — produces oscillation under noise.

**Implications:** Reconciliation (D-50) is the data layer; the adjustment is computed from it. The margin sizing dashboard surfaces both the base value and the learned adjustment, so the operator sees where the margin came from.

---

### D-21 — The outbound order email lists per-session breakdown alongside the weekly total

**Decision:** The caterer-facing order email contains: a header with caterer name, week, week's total item count and total cost; a per-session block for each session in the week with (date, school, building/address, dinner time, item-by-quantity table); a footer with delivery instructions, expected confirmation deadline, and Padea contact for queries. The aggregate count appears alongside the per-session breakdown for MOQ reconciliation.

**Derived from:**
- Observation: §Session timing — distinct sessions, distinct buildings, distinct dinner times
- Observation: §Caterer capability — same-day concurrent deliveries (GyG Monday)
- Requirement: §Reliable meal delivery — "meals must arrive at the right place, at the right time, in the right quantities"

**Reasoning:** Caterers prepare per-session. Aggregating to a weekly total without per-session breakdown loses the actionable information. GyG-Monday two-school case requires the email to show two distinct delivery destinations on the same date.

**Implications:** Email template (D-77) has session-block structure. Confirmation handling (D-26) reads per-session arrivals.

---

### D-22 — Variety pruning prioritises by cohort acceptability with dietary coverage preservation as a hard constraint

**Decision:** When MOQ pressure forces variety reduction (e.g. cohort cannot meet 6-item MOQ at current demand), the variety pruner ranks items by `acceptable_to_cohort_count` (number of enrolments in the week's cohort who have positively accepted the item). It removes items in ascending order of acceptability. However, no item may be removed if doing so would leave a dietary cohort (vegetarian, halal, etc.) without at least one acceptable item — a hard constraint that overrides acceptability ranking.

**Derived from:**
- Requirement: §Sufficient variety — "the system must retain the options the most students find acceptable and drop the options the fewest find acceptable"
- Requirement: §Sufficient variety — "system must also preserve dietary coverage for the cohort — cutting a vegetarian option from the menu set when half the vegetarians on the cohort depend on it produces a worse failure than cutting a less-relied-on option"

**Reasoning:** Pure acceptability ranking can violate dietary coverage; pure dietary preservation can keep low-value items. The two-pass approach (acceptability ranking, then dietary-coverage veto) honours both. The coverage rule is "at least one acceptable item per active dietary cohort" — not "all items every cohort might want", which is a different and weaker constraint.

**Implications:** The composition narrative records which items were considered for cutting, which were cut, and which were preserved by the dietary coverage rule. If even the coverage rule cannot be satisfied at any feasible MOQ tier, the composition escalates with the trade-off made explicit.

---

### D-23 — Order drafts default to `pending_human_review`; auto-send is opt-in per (caterer, school) with a graduated trigger

**Decision:** Every composed weekly order enters `pending_human_review` state with a complete reasoning surface (margin breakdown, MOQ analysis, dietary edge cases, variety choices, parent acceptance coverage). The operator approves (one click), revises, or escalates. Auto-send may be enabled per (caterer, school) once that combination has produced 6 consecutive operator-approved orders with no revisions. Auto-send remains revocable.

**Derived from:**
- Requirement: §The coordinator out of the bottleneck — "the system must take the routine flow off their desk while leaving them in clear ownership of decisions that genuinely require their judgement"
- Requirement: §The coordinator out of the bottleneck — "the system must track its own escalation patterns. As cases accumulate in the operational record, the human approver gains evidence about which categories could be handled automatically"

**Reasoning:** The requirement explicitly distinguishes routine from non-routine, and asks the system to evolve the dividing line as evidence accumulates. Defaulting all initial orders to human review honours the V1 "fail loudly" preference; the 6-clean-orders threshold operationalises the "evidence accumulates" requirement. Per-(caterer, school) granularity prevents an operator's confidence in one caterer from auto-enabling all caterers.

**Alternatives considered:** Auto-send always — violates V1 ambition's accountability stance and risks bulk failure. Auto-send never — does not honour the requirement to take routine off the operator's desk.

**Implications:** Schema records `auto_send_eligible` per (caterer, school) with consecutive-clean-orders counter. The operator dashboard surfaces orders currently in auto-send mode for transparency. A revision resets the counter to zero.

---

### D-24 — Order lines preserve the per-enrolment matching decision in a separate `order_line_enrolment` table

**Decision:** An `order_line_enrolment` table links each ordered meal to the specific enrolment provisioned for it: (order_line_id, enrolment_id, match_reasoning_id). The order line itself carries quantity (which equals the count of matching enrolment links plus margin allocation). Margin meals carry a `margin_allocation` flag and have no enrolment link.

**Derived from:**
- Requirement: §Sufficient variety — "the system must hold knowledge of what each student has been served recently"
- Requirement: §Meals students want to eat — per-student understanding
- Requirement: §The non-negotiable safety floor — audit and traceability

**Reasoning:** Per-enrolment provenance is what makes variety enforcement, per-student satisfaction tracking, and dietary audit possible. Aggregating to "quantity 17" destroys the link we'll need at the next composition to ask "what did this student eat last week?" Margin meals are deliberately unlinked — they are provisioned to cover unspecified attendance.

**Implications:** Variety prevention reads from order_line_enrolment history to know per-student recent items. Feedback aggregation links per-rating to the order_line_enrolment to know which item the rating refers to. Margin reconciliation post-session matches actual walk-ups to margin allocations.

---

### D-25 — Walk-up prediction is computed per (school, session) and feeds the margin sizing for that session

**Decision:** A walk-up predictor produces, for each session in the composition window, an expected walk-up count. Features: trailing 8-week walk-up rate at the school, per-parent false-absence rates for parents in the session's cohort, day-of-week indicator, calendar-week-of-term, exam-period flag, public-holiday-adjacent flag, end-of-term flag. The prediction is added to the operational margin (D-20) for that session.

**Derived from:**
- Observation: §Absences — 10 absences across the week, all confirmed enrolled
- Assumption: A25 (margin absorbs walk-backs and notification unreliability)
- Assumption: A28 (parents sometimes send duplicate absences, indicating notification noise)
- Requirement: §Reliable meal delivery — "recurring false-absence patterns can be identified and addressed"

**Reasoning:** Pure margin treats all sessions identically; walk-up prediction adjusts margin to the specific cohort's history. The per-parent false-absence rate is the signal that captures which parents are over-reporters — pooling to school-level loses the granularity. Calendar features capture systematic patterns (exam weeks reduce absences, end-of-term increases them).

**Alternatives considered:** Margin only, no prediction — ignores the available signal. Per-student walk-up prediction — too granular at current data volumes; per-parent is the right resolution because false-absence is a parent behaviour, not a student one.

**Implications:** The predictor retrains weekly from the rolling history. A `walkup_prediction` table stores each session's prediction with features so future audits can reproduce the reasoning. Low confidence triggers a fallback to base margin only.

---

### D-26 — Each weekly order generates an order-economics simulation showing alternatives

**Decision:** Alongside the chosen composition, the order composer computes the cost at: (a) current variety level with chosen quantity, (b) one variety level higher (if MOQ permits), (c) one variety level lower with surplus relative to demand, (d) at the current variety level meeting next MOQ tier (with explicit overage cost). The simulation is part of the order's reasoning surface for the operator.

**Derived from:**
- Assumption: A14 (falling below MOQ has financial penalty)
- Requirement: §Reliable meal delivery — "the system must surface the shortfall to the human approver with the cost implication made explicit"
- Requirement: §Sufficient variety — variety trade-offs visible

**Reasoning:** Implicit trade-offs become explicit ones. The operator sees "we chose 5 items at $X total; 6 items would cost $X+50 with surplus 10 meals; 4 items would cost $X-30 with reduced variety". The simulation makes the decision auditable rather than a derived consequence of MOQ logic.

**Implications:** Composition narrative includes the simulation. The dashboard surfaces the simulation alongside the composed order for review.

---

### D-27 — Recent-repeat prevention enforces a rolling-window unique-item constraint per enrolment

**Decision:** For each enrolment, the matching engine tracks the last N items served (default N=3, configurable per school). Variety selection prefers items not in the recent-served set. Where the dietary-compatible set is smaller than N, the constraint relaxes to "not the most recent" rather than "not in last N".

**Derived from:**
- Requirement: §Sufficient variety — "palate fatigue must be prevented. Students who eat the same item repeatedly come to want it less"

**Reasoning:** A per-enrolment recent-served window operationalises the fatigue-prevention requirement. Hard exclusion of last-N risks no-match cases at small dietary intersections (a halal-vegetarian student at a caterer with one suitable item). The graceful relaxation handles the edge.

**Implications:** Per-enrolment match decisions read order history. The variety dashboard shows per-enrolment item rotation, surfacing students whose dietary intersection is too small to support meaningful rotation — a signal for caterer fit re-evaluation.

---

### D-28 — Dietary-restricted enrolments receive a meal even when MOQ pressure would otherwise cut variety below their requirements

**Decision:** Variety pruning (D-22) cannot remove the last item satisfying a dietary cohort's requirements. If the MOQ constraint cannot be met without violating dietary coverage, the order composition escalates rather than cutting. The escalation surfaces the trade-off: pay MOQ overage, or remove a non-coverage item, or escalate to caterer for accommodation.

**Derived from:**
- Requirement: §The non-negotiable safety floor — "the system must never serve a meal that violates a student's documented dietary requirements"
- Requirement: §Sufficient variety — dietary coverage preservation
- Assumption: A29 (whole-session exclusions are the only override of dietary safety; MOQ pressure is not)

**Reasoning:** The safety floor is non-negotiable per requirement. MOQ pressure cannot override it implicitly. An explicit escalation puts the trade-off in front of the operator, who can pay the overage, negotiate with the caterer, or decline the order.

**Implications:** A failed composition due to dietary-coverage-vs-MOQ conflict creates a specific escalation type with a pre-drafted enquiry email to the caterer about accommodating an additional dietary-suitable item.

---

# Dietary safety

### D-29 — Dietary matching runs as a constraint-satisfaction step that returns the full candidate set, not a single selection

**Decision:** For a given (enrolment, week, available menu), the matching function returns the ordered list of all items satisfying the enrolment's dietary attributes. Downstream stages (parent acceptance, variety prevention, MOQ-driven pruning) select from the candidate set. The candidate set is materialised in the order composition snapshot.

**Derived from:**
- Requirement: §The non-negotiable safety floor — dietary properties resolved in advance, matching reads them
- Requirement: §Meals students want to eat — parent acceptance is a separate stage
- Requirement: §Sufficient variety — variety logic operates on the candidate set

**Reasoning:** Separating filtering from selection lets each stage operate on the right input. The candidate set feeds the parent acceptance flow (which presents items the student *could* eat) and the variety enforcement (which selects within the acceptable items). A single-return matcher couples decisions that should be staged.

**Implications:** Schema stores `dietary_candidate_set` per (enrolment, week) for audit. The parent meal-options email (D-49) reads from this set.

---

### D-30 — A pre-flight safety check runs immediately before order send and blocks if any enrolment has lost dietary safety

**Decision:** After operator approval and before the outbound email is sent, the composition re-runs the dietary safety floor against the current state (in case dietary data or menu data changed between composition and send). Any safety floor violation halts the send and escalates to the operator.

**Derived from:**
- Requirement: §The non-negotiable safety floor — "for the safety floor to hold even when other parts of the system fail, the floor cannot depend on the rest of the system working"
- Requirement: §Graceful failure

**Reasoning:** Dietary data can change between composition and send (a parent updates a record; an operator elevates a nut severity). A pre-flight check is the last barrier. It also catches the case where another system change has invalidated the composition's assumptions.

**Implications:** A small added latency on send (sub-second). A `preflight_check_result` row per order with attributes verified. Where the check passes, send proceeds; where it fails, the order returns to review with the specific violation surfaced.

---

### D-31 — Escalations from "no menu item satisfies dietary requirements" name the specific unmet attributes and propose actions

**Decision:** When matching produces an empty candidate set for an enrolment, the escalation record includes: enrolment_id, required dietary attributes, list of items considered, per-item rejection reason (which attribute caused rejection), and pre-drafted action options — (a) enquire with caterer about accommodation, (b) substitute a different caterer for this session, (c) opt this enrolment out for this week with parent notification.

**Derived from:**
- Requirement: §The non-negotiable safety floor — "the system must escalate when no available menu item satisfies a student's dietary requirements"
- Requirement: §The non-negotiable safety floor — escalation with adequate context

**Reasoning:** The escalation must be actionable. Naming the unmet attributes (rather than "no match") lets the operator act without recomputing. Pre-drafted actions reduce the cognitive load of response.

**Implications:** Escalation lifecycle (D-72) handles these as a distinct severity tier (`dietary_no_match` — high). Resolution requires explicit operator action; an escalation cannot be auto-closed by time.

---

### D-32 — Anaphylaxis-elevated enrolments require explicit caterer cross-contamination attestation per matched meal

**Decision:** An order line for an enrolment with `nut_allergy_severity='anaphylaxis'` cannot ship without a `caterer_attestation` row linking that line to a recorded caterer commitment ("we will prepare this meal in a nut-free environment for this delivery"). The attestation is collected at first match for the (caterer, item) pair and re-confirmed at a configurable cadence (default term-based).

**Derived from:**
- D-06 — severity enum exists
- Requirement: §The non-negotiable safety floor — nut allergy explicit, with cross-contamination implication

**Reasoning:** "Contains nuts: no" is a property of the recipe. "Prepared in a nut-free environment" is a property of the kitchen and the specific preparation. The latter is what anaphylaxis-level allergy requires. Storing an attestation lets the matching engine refuse to send without it, rather than relying on the operator to remember.

**Implications:** Caterer attestation collection is an operator-driven flow at caterer onboarding and at each new menu item. Where attestation cannot be obtained, the matching engine escalates the affected enrolment per D-31.

---

### D-33 — Whole-session exclusions suppress the dietary safety floor for affected enrolments

**Decision:** When an exclusion covers an entire session, the dietary safety floor for enrolments in that session returns "no provisioning required" rather than the usual escalate-on-no-match. The exclusion record carries an explicit `acknowledged_at` timestamp set when the suppression occurs, with the exclusion source preserved.

**Derived from:**
- Assumption: A29 (whole-session exclusion overrides dietary safety)
- Requirement: §The non-negotiable safety floor — explicit handling required

**Reasoning:** A29 commits us to this override. The acknowledgement timestamp prevents accidental application — the system must positively register the exclusion before suppressing the floor. Source preservation makes the override traceable.

**Implications:** Order composition for sessions with whole-session exclusions skips matching entirely. The composition narrative records the exclusion as the reason. Partial exclusions do not trigger this path (D-44).

---

# Disruptions: absences, exclusions, late cancellations

### D-34 — Raw absence notifications are preserved verbatim in `raw_absence_notification`; a canonical `absence` record is derived

**Decision:** Each inbound absence message — email body, web form submission, voice memo transcript — creates one `raw_absence_notification` row containing source channel, timestamp, sender, raw content (text or transcribed text plus audio reference), and parser confidence. A canonical `absence` record per (enrolment, session_date) is derived from one or more raw notifications.

**Derived from:**
- Observation: §Absences — file gives outcomes only, no source/channel/timestamp/reason
- Observation: §Data expected but not present — "Communication history. Absences and exclusions are recorded as outcomes only"
- Assumption: A26 (email-primary intake)
- Assumption: A28 (duplicates occur)
- Requirement: §Graceful failure — verbatim capture before interpretation

**Reasoning:** Verbatim capture preserves data through interpretation failures (per the graceful failure requirement). The canonical-derived shape handles duplicates (multiple raw → one canonical) without rejecting them and supports walk-backs (additional raw notification flips canonical state) without losing the prior raw records.

**Implications:** All downstream logic reads from `absence`, not from raw rows. Audit and reconciliation flows read both. Re-running an extractor with a new version produces a new canonical derivation without touching the raw rows.

---

### D-35 — Absence intake supports four channels: parent email, school email, web form, voicemail transcript

**Decision:** Each `raw_absence_notification` carries a `source_channel` enum: `parent_email`, `school_email`, `web_form`, `voicemail_transcript`. Each channel has its own ingest pipeline that produces structured fields for the canonical record. Email is primary (per A26); other channels capture cases that the email channel cannot.

**Derived from:**
- Assumption: A26 (email is dominant)
- Assumption: A39 (households communicate primarily through email or channels forwarded to email)
- Requirement: §Reliable meal delivery — absence handling

**Reasoning:** Email-only intake leaves edge cases unhandled (a parent who only texts; an absence reported during a Padea phone call). The four-channel surface gets V1 ambition to where the operational reality already is, while keeping email primary in volume.

**Alternatives considered:** Email-only intake — leaves voice and form as out-of-system. Voicemail without transcription — preserves the raw audio but cannot feed structured processing.

**Implications:** Voicemail transcription is a separate ingest path (D-36). Web form is the simplest pipeline (structured by construction). School email is parsed but treated with higher confidence than parent email for cohort-level claims (e.g. "the Y10 cohort is on camp").

---

### D-36 — Voicemail absence notifications transcribe via speech-to-text, then run a dedicated LLM extraction pass

**Decision:** Voicemail audio is transcribed via a speech-to-text service. The transcript runs through an LLM extraction step that pulls: student name, absence date, reason (if given), parent identity (if identifiable from caller ID or voice content). The raw audio and the transcript are both attached to the `raw_absence_notification`. Confidence scores below threshold escalate to the operator before reaching the canonical record.

**Derived from:**
- Assumption: A4 (unstructured input is converted to structured form upstream)
- Assumption: A39 (channels reach the system through some form of conversion)

**Reasoning:** A4 commits to structured-form upstream of the matching layer; voicemail is the canonical "unstructured input" case. Storing both audio and transcript supports later re-extraction if the LLM version changes. The confidence threshold prevents low-confidence extractions from creating false canonical records.

**Implications:** A dependency on a transcription service and an LLM extraction service. Both are tools registered in the agent tool registry (D-68). Cost per voicemail is non-zero, which is the natural pressure that keeps the channel from being abused.

---

### D-37 — Walk-backs of absence notifications are recorded as state transitions with a `walked_back_at` timestamp on the canonical record

**Decision:** The canonical `absence` row has a state enum (`notified` / `walked_back` / `confirmed_absent`) and a `walked_back_at` timestamp set when a walk-back is received. The walk-back notification is added to the same `raw_absence_notification` chain. A subsequent walk-back of a walk-back creates a new canonical `absence` record for the same (enrolment, session_date), not a re-flip of the original.

**Derived from:**
- Assumption: A27 (parent walk-back is the same event with a reversal timestamp)
- Assumption: A28 (a walk-back of a walk-back creates a new absence record)

**Reasoning:** A27 directly commits to this model. The state-and-timestamp shape preserves the sequence of events; a flipping boolean would lose the history. Multiple-record-on-second-flip honours the "new event" semantic in A28.

**Implications:** Walk-up risk flagging (D-39) reads `walked_back_at` relative to order send time. Per-parent false-absence rate (D-40) reads the walk-back history.

---

### D-38 — Duplicate absence notifications are folded into the same canonical record by (enrolment_id, session_date) matching

**Decision:** When a new raw notification arrives that matches an existing canonical record on (enrolment_id, session_date), the new raw row is linked to the existing canonical record rather than creating a new one. Conflicting notifications (e.g. one says absent, another says walked back) follow a "latest wins" rule with the prior state preserved in the audit trail; high-conflict cases (multiple flips in short windows) escalate.

**Derived from:**
- Assumption: A28 (parents send duplicates; system handles without rejecting)
- Requirement: §Graceful failure — "the input must be captured verbatim before any interpretation is attempted"

**Reasoning:** A28 commits us to handling duplicates without rejection. Latest-wins is the natural rule for a state machine where the parent's most recent communication is most authoritative. High-conflict escalation prevents the system from chasing rapid state changes silently.

**Implications:** The raw notification chain on a canonical record can grow arbitrarily long; UI surfaces show the chain for transparency. Audit history records each canonical-state change with the triggering raw notification.

---

### D-39 — Absences arriving after order send do not amend the order; they tag the session as walk-up-risk and flow to reconciliation

**Decision:** The `weekly_order.sent_at` timestamp is the cutoff. Absences with `created_at > sent_at` are recorded with `arrived_after_send=true`. The corresponding session is tagged `walk_up_risk_elevated`. The meal count remains unchanged. Post-session reconciliation (D-50) captures whether the meal was eaten by a walk-up or wasted.

**Derived from:**
- Assumption: A24 (order not amended for subsequent absences)
- Requirement: §Reliable meal delivery — "those arriving in time reduce the order's quantity; those arriving after do not"

**Reasoning:** A24 commits us directly. The walk-up-risk tag is the bridge between "we have margin for this" and "this session needs extra attention". Reconciliation captures the actual outcome for future margin tuning.

**Implications:** Per-session dashboards show the risk tag and the underlying late-absence list. Margin tuning (D-20) reads reconciliation outcomes.

---

### D-40 — Per-parent false-absence rate is computed as a materialised view and feeds predictive features

**Decision:** A `parent_notification_stats` materialised view per parent (or per parent_contact, where parent identity is uncertain): (parent_id, absences_notified, absences_walked_back, walk_ups_after_notification, false_absence_rate). The rate is `(walked_back + walk_ups_after_notification) / absences_notified`. Refreshed nightly. Used by the walk-up predictor (D-25) and surfaced on the operator dashboard.

**Derived from:**
- Assumption: A28 (false absences occur)
- Requirement: §Reliable meal delivery — "recurring false-absence patterns can be identified and addressed"

**Reasoning:** Per-parent rate is the natural granularity (a household's reporting behaviour is a household-level feature). Pooling to school-level loses the signal. Materialised view (refreshed nightly) trades some staleness for query speed.

**Implications:** The operator dashboard surfaces parents with high false-absence rate as a prompt for outreach. The walk-up predictor (D-25) reads this view as one of its features.

---

### D-41 — Exclusion scope is a three-state enum: `whole_session` / `year_levels` / `cohort_subset`

**Decision:** The `exclusion` table has `scope_type` enum and `scope_detail` JSON. For `whole_session`, scope_detail is empty. For `year_levels`, it's a list of year-level integers. For `cohort_subset`, it's a list of enrolment_ids or a query expression (e.g. "students taking Physics this term"). The order composer evaluates scope against the enrolment list to produce the affected set.

**Derived from:**
- Observation: §Exclusions — three exclusions, two whole-session, one year-level partial
- Assumption: A31 (cohort-subset exclusions like "Physics students at competition" reach the system as pre-filtered information)

**Reasoning:** Two-state (whole / partial) underfits A31's anticipated subject-cohort case. The three-state enum captures the operational space, with the most general case (`cohort_subset`) holding the list explicitly rather than relying on free-text interpretation.

**Implications:** Adding a new exclusion through the operator form selects scope type, which gates which scope detail fields are visible. The composition narrative records which enrolments were affected and which weren't.

---

### D-42 — Partial exclusions size the order to the remaining cohort with an additional exclusion-attendance margin

**Decision:** For partial exclusions (year-level or cohort-subset), the order quantity for the affected session = `non_excluded_enrolments_count + standard_operational_margin + exclusion_attendance_margin`. The exclusion attendance margin is 15% of the excluded count by default, configurable per school. Tunable from reconciliation data after enough partial-exclusion observations accumulate.

**Derived from:**
- Assumption: A30 (excluded-year students sometimes attend; they're paying for the session)
- Observation: §Exclusions — CHAC Wed Y10+Y12 exclusion with Y11 still attending
- Requirement: §Reliable meal delivery — partial-exclusion order sizing

**Reasoning:** A30 commits us to expecting attendance from excluded cohorts. Hard-coded 15% is a starting estimate; the system learns from reconciliation. Margin is additive to the standard operational margin because the failure modes are independent (one is "absent students who attend"; the other is "students who didn't notify").

**Implications:** Composition narrative records both margins separately. Reconciliation (D-50) captures excluded-but-attended count to tune the figure.

---

### D-43 — Exclusion intake is human-mediated; the system does not auto-parse free-text exclusion announcements

**Decision:** Exclusions enter the system through a structured operator form with mandatory fields (date, school, scope_type, scope_detail, reason, source_school_contact). Inbound emails containing exclusion-like content route to the operator's inbox with a draft pre-filled from extracted entities. The form is the path of record; LLM extraction populates the draft but does not commit.

**Derived from:**
- Assumption: A31 (exclusions arrive pre-filtered by humans)

**Reasoning:** A31 commits us to this model. Free-text school-administration announcements have high variance ("Year 10 students are on excursion Wednesday" vs "Wednesday is Open Day, all classes cancelled"). Auto-parsing risks high-stakes false positives (cancelling an order incorrectly). The human-confirmed draft is the safe operationalisation.

**Implications:** The agent's role in exclusion intake is draft preparation and routing, not commit. The operator's inbox surfaces drafts ready to commit with one click.

---

### D-44 — Whole-session cancellations arriving post-order-send escalate immediately with three pre-drafted response options

**Decision:** A late whole-session exclusion (created after the relevant order's `sent_at`) triggers a high-severity escalation containing three pre-drafted options: (a) email to caterer cancelling the delivery (with cost implication noted), (b) email to caterer accepting delivery and arranging donation, (c) email to escalation contact asking for a pricing-implication decision. Each carries the financial figure attached.

**Derived from:**
- Assumption: A33 (late cancellation requires human intervention)
- Requirement: §Reliable meal delivery — handling sessions that do not run as normal
- Requirement: §Graceful failure — explicit handling of edge cases

**Reasoning:** A33 explicitly says human intervention is required. Pre-drafted options minimise the operator's cognitive load while preserving their authority. The cost-figure attachment is what makes the decision tractable in the moment.

**Implications:** Schema records which option was chosen, when, and the outcome. Over time the pattern of chosen options becomes a signal — if option (a) is always chosen, the system can suggest making it the default proposal.

---

### D-45 — Exclusions do not have a walk-back mechanism; reversal is handled by superseding the exclusion record

**Decision:** No `walked_back_at` field exists on exclusions. A reversed exclusion is handled by the operator creating a `supersedes` link from a new "exclusion withdrawn" record back to the original. The original is preserved; the operational query reads "active exclusions not superseded".

**Derived from:**
- Assumption: A32 (exclusion walk-back is rare; manual handling acceptable)

**Reasoning:** A32 explicitly says building a reversal flow over-engineers for an edge case. Superseding is the simplest mechanism that preserves history without dedicated state-machine machinery.

**Implications:** A small operator workflow for the rare case (a school reverses a decision). Schema has a self-referential `supersedes` foreign key on `exclusion`.

---

### D-46 — Walk-up events are first-class records: a `walk_up` table captures every student who attended despite an absence notification

**Decision:** A `walk_up` table records (enrolment_id, session_date, recorded_at, recorded_by) for every student who attends a session having been notified absent for it. Manager records walk-ups at session end through the same session-report flow (D-52). Walk-up records feed the per-parent false-absence rate (D-40) and the walk-up predictor (D-25).

**Derived from:**
- Requirement: §Reliable meal delivery — "Where a student notified as absent attends anyway, a meal must still be available. The system must capture such walk-up events so recurring false-absence patterns can be identified"
- Assumption: A28 (notifications are imperfect)

**Reasoning:** The requirement explicitly demands walk-up capture. First-class table makes the data structured rather than embedded in session notes; predictive features and per-parent stats are queries against this table.

**Implications:** Session manager workflow includes a walk-up check. Margin reconciliation reads this table alongside attendance.

---

# Feedback in the V1 initials state

### D-47 — V1 feedback is three-channel: parent meal selection (input), student rating (output), manager session report (output)

**Decision:** Three feedback artefacts per session: (1) a parent meal-options selection collected weekly per enrolment before the order composes, (2) per-student post-session ratings collected via a form sent after the meal, (3) a single manager session report submitted within 24 hours of the session, covering item-level observations and walk-up reconciliation.

**Derived from:**
- Requirement: §Quality maintained over time — "Quality signals must come from multiple sources rather than any single channel"
- Requirement: §Meals students want to eat — per-student acceptability understanding
- Assumption: A34 (parents identify acceptable meals on behalf of student)
- Assumption: A36 (students rate the meal)

**Reasoning:** Requirement explicitly demands multiple sources. The three channels capture: future intent (parent selection), realised satisfaction (student rating), operational reality (manager report). Each captures information the others cannot.

**Implications:** Three schema entities: `parent_meal_selection`, `student_meal_rating`, `manager_session_report`. Aggregation logic combines them with appropriate weighting (D-53–D-55).

---

### D-48 — Parent meal-options selection is collected weekly per enrolment via a single form link emailed to the parent

**Decision:** Each week, on a cadence preceding order composition by adequate lead time, the system sends each parent a form link per enrolment showing their child's dietary-compatible items from the caterer's menu. The parent selects which items their child finds acceptable. Selection persists term-to-term as a default, refreshed weekly to capture changes.

**Derived from:**
- Assumption: A34 (parents identify acceptable meals)
- Assumption: A35 (parent-facing list pre-filtered by dietary)
- Requirement: §Meals students want to eat — per-student acceptability data

**Reasoning:** Weekly cadence aligns with order composition. Per-enrolment (not per-student) supports the dual-enrolment case naturally. Persistence-with-refresh balances operator-perceived burden ("yet another form every week") against the requirement to capture preference change over time.

**Alternatives considered:** Per-term parent selection — captures less change. Per-meal parent selection — too granular, fatigues parents. Student-direct selection — A34 commits us to parent-mediated in V1.

**Implications:** A `parent_meal_selection` row per (enrolment, week, menu_item) with `is_acceptable` boolean. Where a parent does not respond, the prior week's selection carries over with a `stale` flag. Where selection is missing entirely, dietary-compatible default is used and the parent is flagged for follow-up.

---

### D-49 — Parent-facing meal options are pre-filtered by the system before reaching the parent

**Decision:** The form sent to each parent shows only items that satisfy the enrolment's current dietary attributes. Items that fail any of the enrolment's dietary attributes are excluded from the form entirely, not shown-but-disabled.

**Derived from:**
- Assumption: A35 (parent-facing list pre-filtered by dietary)
- Requirement: §The non-negotiable safety floor

**Reasoning:** A35 commits us directly. Showing-but-disabled risks confusion and accidental selection of an incompatible item if a UI implementation goes wrong; outright exclusion is the safer mode.

**Implications:** The form-generation step reads the dietary candidate set (D-29) and renders it. The form preserves what was shown for audit (the parent saw items X, Y, Z) so that selection cannot be reconstructed against a different menu.

---

### D-50 — Student ratings are collected per (enrolment, session, item) via a form link sent shortly after the session ends

**Decision:** A per-student form link sends within a configurable window after session end (default 30 minutes). The form asks for a single rating (1–5) and an optional free-text comment per item the student was served (typically one per session). Submission is identified by a one-use token tied to the order_line_enrolment record.

**Derived from:**
- Assumption: A36 (students rate the meal)
- Assumption: A37 (ratings remain Padea's property)
- Requirement: §Quality maintained over time — quality signal collection

**Reasoning:** Short-window post-session collection captures freshness of memory. One-use tokens prevent multiple submissions per student per meal and avoid any need for student authentication.

**Alternatives considered:** Email-based ratings — slower turnaround. Manager-collected ratings — risks bias and adds operator burden.

**Implications:** A `student_meal_rating` row per submission with rating, optional comment, submitted_at, token_used. The submission-timing weight (D-55) reads `submitted_at` relative to session end.

---

### D-51 — Free-text rating comments are run through LLM extraction to recover per-attribute signal (e.g. portion, temperature, taste)

**Decision:** Each rating comment is processed through an LLM extraction pass that pulls structured signal: dimensions (`taste` / `portion` / `temperature` / `presentation` / `freshness` / `other`), sentiment (positive / neutral / negative) per dimension, and any specific item references. The original comment is preserved verbatim; the extraction is stored as a separate row, versioned, and tied to the original by foreign key.

**Derived from:**
- Assumption: A4 (unstructured input converted upstream)
- Requirement: §Quality maintained over time — multi-source signal

**Reasoning:** Per-attribute signal makes "this caterer has been delivering cold meals" detectable as a pattern, where raw 1–5 ratings alone might show a generic decline without explanation. Free-text comments are how students naturally express granular feedback; the extraction recovers what the rating scale doesn't capture.

**Implications:** `rating_comment_extraction` table with versioned extractions. Caterer scorecards (D-62) show per-dimension trends.

---

### D-52 — Manager session reports are free-text; LLM extraction recovers per-item granularity

**Decision:** Manager submits a single text report per session covering: overall session notes, per-item observations (free-form), walk-up reconciliation, photo references (D-56). An LLM extraction step parses item references, sentiment per item, and specific issue tags into structured `manager_feedback_extraction` rows linked to menu items. Original text is preserved verbatim; extraction is versioned.

**Derived from:**
- Assumption: A4 (structured form conversion upstream)
- Requirement: §Quality maintained over time — multi-source

**Reasoning:** Asking managers to fill per-item structured forms would not be honoured at the rate that produces useful signal; free-text plus extraction is the V1-ambitious bridge that gets granularity without operator burden. Versioning lets us re-extract with a better model later.

**Implications:** A small dependency on an LLM extraction service. Manager UI is a single text field plus a few structured fields (walk-up count, missing-meal-count, photo upload).

---

### D-53 — Student ratings are rater-baseline-normalised before aggregation

**Decision:** Each rater (student) has a computed baseline mean over their last 8 ratings. New ratings are normalised by subtracting baseline before contributing to caterer/item aggregates. A student with fewer than 4 ratings uses the network baseline as a fallback until they accumulate history.

**Derived from:**
- Requirement: §Quality maintained over time — "aggregate them across time windows long enough to filter session-to-session noise"

**Reasoning:** Cohort averages without normalisation are dominated by rater-style differences. A student who rates everything 4 vs one who rates everything 2 contribute different baselines; their *deviations* carry the signal. Normalisation makes per-item aggregates comparable across rater populations.

**Implications:** Per-student baseline materialised view, refreshed nightly. Aggregations read normalised values; the raw rating is preserved for transparency.

---

### D-54 — Ratings are time-decay-weighted in caterer/item aggregates with an exponential half-life

**Decision:** In caterer/item aggregate computations, each rating's weight decays exponentially with half-life of 4 weeks. The half-life is per-metric configurable (e.g. shorter for trend detection, longer for absolute-score stability).

**Derived from:**
- Requirement: §Quality maintained over time — "the system must be able to recognise decline early enough to act before students experience prolonged poor service"

**Reasoning:** A simple mean lags trend detection by months. Time-decay weighting puts recent ratings in the foreground for trend purposes while preserving historical context for absolute baselines.

**Implications:** Aggregation queries apply the weight function. The half-life parameter is exposed in the caterer-rotation tuning surface.

---

### D-55 — Ratings carry a submission-timing weight that decays from 1.0 (within 2 hours) to a floor of 0.5 (after 48 hours)

**Decision:** Each rating's effective weight = baseline-normalised value × time-decay (D-54) × submission-timing weight. The submission-timing weight is 1.0 for submissions within 2 hours of session end, decays linearly to 0.5 at 48 hours, floor 0.5 thereafter.

**Derived from:**
- Requirement: §Quality maintained over time — quality of signal

**Reasoning:** Memory degrades — a rating submitted three days later is reconstructed; a same-evening rating is observed. The decay captures this without dropping late ratings entirely (which would lose data from students who legitimately rate later).

**Implications:** Effective weight is computed per rating and stored alongside, supporting both aggregation and audit.

---

### D-56 — Manager opportunistic meal photos are stored against (session, caterer) and surfaced in scorecards as samples

**Decision:** The manager's session-report flow includes an optional photo upload step (zero or more photos per session). Photos are stored with metadata (session_id, caterer_id, captured_at, optional caption) and surfaced on internal caterer scorecards as a periodic sample. They are not exposed in caterer-facing scorecard views. The existence of photo capture is communicated to caterers at onboarding.

**Derived from:**
- Requirement: §Quality maintained over time — caterer-facing accountability, visible measurement

**Reasoning:** The existence of the photo capture, more than the photos themselves, is the deterrent. Caterers told "we periodically photograph delivered meals" have a structural incentive to maintain presentation, portion, and freshness. Photos also support internal forensic review when ratings drop unexpectedly.

**Implications:** Object storage for photos with row references in the schema. Photos viewed only in internal-facing dashboards.

---

### D-57 — A term-end satisfaction survey is OUT of V1; the rolling rating signal is the primary instrument

**Decision:** No term-end survey is implemented in V1. Satisfaction signal comes from the rolling rating channel (D-50) and trend analytics. A term-end survey may return in a later phase if rolling-rating coverage proves insufficient.

**Derived from:**
- Requirement: §Quality maintained over time — continuous signal collection
- Requirement: §Meals students want to eat — per-student understanding (continuous, not point-in-time)

**Reasoning:** A term-end survey duplicates information the rolling channel produces continuously and arrives too late to act on within the term it surveys. V1 ambition is breadth of continuous signal, not periodic batch collection. This is a deliberate non-inclusion, not an oversight.

**Implications:** No survey schema, no operator workflow around survey design and distribution. If a term-end survey is later argued for, it will be evaluated against the rolling signal's actual coverage and gaps.

---

### D-58 — A cross-cohort taste-compatibility matrix supports recommendation when a student has no acceptance history

**Decision:** A `taste_compatibility` matrix is computed from cross-cohort consumption: students who accepted item A also tended to accept items {B, C, D} at rates {r1, r2, r3}. For a new enrolment with no acceptance history, the matrix proposes a starting set of items likely to be acceptable, prefilling the parent meal-selection form with these as suggested options.

**Derived from:**
- Requirement: §Meals students want to eat — per-student acceptability understanding
- Requirement: §Sufficient variety

**Reasoning:** A new enrolment's first parent meal-selection form would otherwise present the full dietary-compatible candidate set with no signal about which to pick. The matrix gives the parent a prior — items that have worked for similar palates. The parent remains the decision-maker; the matrix only orders the options.

**Alternatives considered:** Cold-start with no prior — workable, but loses the cross-cohort signal we already have. Per-school priors only — too coarse; tastes don't sort cleanly by school.

**Implications:** A nightly job computes the matrix from order_line_enrolment × parent_meal_selection. The parent form rendering reads the matrix to order the options.

---

# Caterer relationship management

### D-59 — Caterer quality decline detection runs as a two-condition rolling-window trigger

**Decision:** Per (caterer, school) pair, a weekly aggregate score is computed from the feedback signals (rating, comment extraction, manager report extraction). A decline is flagged when (a) the current 2-week mean is below the prior 4-week mean by more than 1 standard deviation, AND (b) the absolute current score is below a per-caterer configured floor. Both conditions must hold simultaneously.

**Derived from:**
- Requirement: §Quality maintained over time — "aggregate them across time windows long enough to filter session-to-session noise, and surface aggregated decline before students experience prolonged poor service"

**Reasoning:** Single-condition detection produces false positives — a single bad week, or a caterer that's been mediocre all along. The two-condition rule requires both a downward trend (condition a) and an absolute threshold (condition b). Per-caterer floor calibrates to baseline performance differences (Lakehouse and Kenko are not directly comparable).

**Implications:** A `caterer_decline_signal` table records detection events with the contributing window data. The escalation lifecycle (D-72) handles the resulting rotation proposal.

---

### D-60 — Rotation proposals are escalations carrying comparative analysis and pre-drafted enquiry emails

**Decision:** A decline detection raises a `caterer_rotation_proposal` escalation containing: current performance trajectory, alternative eligible caterers (from D-10 capability data), comparative pricing/lead-time/MOQ, pre-drafted enquiry email to the alternative, pre-drafted notification email to the current caterer (if needed). The operator approves, dismisses with reason, or modifies.

**Derived from:**
- Assumption: A42 (rotation is human-judged)
- Requirement: §Quality maintained over time — "the system must surface alternative eligible caterers and draft a swap proposal for the human approver to review. The system must not unilaterally rotate caterers"

**Reasoning:** Requirement explicitly assigns rotation authority to the human. Pre-drafted comparative analysis is what minimises the operator's work while preserving authority. Each draft email is reviewable before send.

**Implications:** Schema records each proposal's outcome (approved / dismissed / modified) and reason. Dismissal feedback tunes detection sensitivity (D-61).

---

### D-61 — Operator dismissals of rotation proposals are recorded with reason and feed back into sensitivity tuning suggestions

**Decision:** When an operator dismisses a rotation proposal, they record a reason from a controlled list (`temporary_issue` / `owner_personal_circumstance` / `we_are_addressing_it` / `false_positive` / `other`). Repeated dismissals for the same caterer trigger a suggestion to the operator that detection sensitivity might need adjustment — surfaced as an information event, not an automatic threshold change.

**Derived from:**
- Requirement: §The coordinator out of the bottleneck — "the system must track its own escalation patterns"

**Reasoning:** Requirement asks for the system to track patterns and let the operator's evidence accumulate. Surfacing suggestions rather than auto-tuning keeps the operator in control of the detection floor. The controlled reason list makes the data analyzable.

**Implications:** Schema records reasons. The tuning suggestion is an operator-dashboard event. Schema does not implement automatic threshold adjustment.

---

### D-62 — Caterers see a scorecard view of their own aggregated performance; individual ratings and student identities are never exposed

**Decision:** A caterer-facing dashboard (accessed via a per-caterer auth-tokened URL) exposes: aggregate score over time (their own data only), per-item score, per-dimension extraction (portion / temperature / etc.), recent trend, comparison to their own historical baseline. Individual ratings, student identities, comment text, and other caterers' scores are not exposed.

**Derived from:**
- Assumption: A37 (ratings remain Padea's property, not visible to caterers in identifying form)
- Requirement: §Quality maintained over time — "visible measurement of their performance"

**Reasoning:** A37 protects student privacy. The requirement asks for visible measurement to create the structural incentive to maintain quality. Aggregated own-data view honours both — caterers see their performance trajectory without breaching student identity.

**Implications:** A separate render path for caterer-facing dashboard. The auth-token is rotatable per caterer; revocation is straightforward. The dashboard's existence is communicated to caterers at onboarding.

---

### D-63 — A cross-caterer comparative dashboard is internal-only and accessible to the operator

**Decision:** An operator-facing dashboard surfaces caterer-by-caterer comparison: aggregate score, trend, per-school score, MOQ utilisation, cost-per-meal-delivered, capability coverage, recent decline signals. This is the surface for rotation conversations and capability extensions.

**Derived from:**
- Requirement: §Quality maintained over time — "alternatives credible"

**Reasoning:** Requirement asks for the alternative caterers to be credible — operator visibility into how alternatives compare is what makes them so. Internal-only access protects competitive boundaries between caterers.

**Implications:** Dashboard read-paths aggregate over the same underlying tables as the caterer-facing scorecards but with full cross-caterer visibility. Operator authentication required.

---

### D-64 — Caterer non-response before order-confirmation deadline triggers an escalation with three pre-drafted options

**Decision:** Each sent order has an `expected_confirmation_by` timestamp computed from the caterer's stated lead-time. When the deadline passes without confirmation, an escalation raises with three pre-drafted actions: (a) follow-up email to the order-taker, (b) call-script for direct phone contact, (c) draft enquiry to an alternative eligible caterer. Operator selects one or composes their own response.

**Derived from:**
- Assumption: A41 (caterers respond in routine case; non-response is escalation territory)
- Requirement: §Reliable meal delivery — "Where a caterer has not confirmed an order in adequate time before the session, the system must escalate with viable options for the human approver"

**Reasoning:** Requirement explicitly demands escalation with options. Three options cover the operational shapes: low-stakes follow-up, direct contact, alternative caterer enquiry. The pre-drafts reduce response time.

**Implications:** Caterer lead-time is a field on the caterer record. Each weekly order computes its expected confirmation deadline. A scheduled check triggers escalation; manual confirmation logging closes the deadline state.

---

### D-65 — Capability re-confirmation is triggered by three events: new session day, term boundary, post-decline-signal

**Decision:** A `capability_reconfirmation_required` event raises when (a) a school adds a new session day not currently covered by any caterer with `currently_serves` status, (b) a new term begins, or (c) a caterer-school pair has triggered a decline signal in the current term. The event surfaces in the operator dashboard with a pre-drafted enquiry to the caterer.

**Derived from:**
- Assumption: A10 (capability applies to current operation)
- Assumption: A12 (DOW-level capability)
- Requirement: §Reliable meal delivery — "None of these can be inferred at runtime; they are facts the system must hold and keep current"

**Reasoning:** Capability data goes stale silently if there's no trigger to refresh it. The three triggers cover the cases where stale capability creates real risk: new sessions (capability untested), new term (relationships shift), post-decline (relationship may have changed).

**Implications:** Capability records carry `last_confirmed_at`. Reconfirmation creates a new `caterer_capability` row with a fresh effective-from; the prior row retains its effective-to.

---

# Agent runtime, observability, and operational record

### D-66 — Agent operations are recorded at three levels: run, decision, tool call

**Decision:** An `agent_run` row per invocation captures (run_id, started_at, completed_at, status, agent_version, trigger). An `agent_decision` row per branching point captures (decision_id, run_id, inputs_considered, alternatives_evaluated, choice_made, reasoning_narrative, severity_tier). An `agent_tool_call` row per tool invocation captures (call_id, decision_id, tool_name, arguments, response, latency_ms, outcome).

**Derived from:**
- Requirement: §Visible operation — "the system must produce an inspectable record of every meaningful decision it makes. Each agent run, each decision within a run, each tool the agent invokes, each rule it applies, each escalation it raises must be captured with enough context"

**Reasoning:** Requirement names the resolution. Three levels (run, decision, tool call) gives the queries needed: "what did the agent do today?" (run-level), "why did it choose X for this student?" (decision-level), "what did the email API actually return?" (tool-call-level).

**Implications:** All agent logic threads decision_id and call_id through its operations. Schema has these three tables with cross-references; queries can navigate "tool call → decision that triggered it → run that contains the decision".

---

### D-67 — Each agent decision carries both a structured `inputs_considered` JSON and a `reasoning_narrative` natural-language field

**Decision:** Every `agent_decision` row records the inputs consulted (JSON: enrolment IDs, menu items considered, MOQ figures, etc.) and a natural-language narrative ("I selected the chicken bowl for Bailey Roberts because his prior ratings show he prefers warm meals and he has no dietary restrictions matching the cold options. The vegetarian bowl was rejected because the cohort had two other vegetarian-acceptable items."). Both stored at the decision.

**Derived from:**
- Requirement: §Visible operation — "the record must be legible, not merely complete"

**Reasoning:** Structured-only loses the why; narrative-only loses queryability. Both together support the dual surface: an operator reading the day's activity wants the narrative; an analyst querying "why was this item never selected for Y10 students" wants the structured data.

**Implications:** Narrative generation is a prompted LLM step at decision capture, not a post-hoc explainer. The narrative records what the agent was reasoning at the time, not a reconstruction after the fact.

---

### D-68 — Tools available to the agent are registered in a `tool_registry` table with permission scopes; new tools require configuration, not code

**Decision:** Each tool the agent can invoke is a `tool_registry` row with `name`, `description`, `input_schema`, `output_schema`, `permission_scope` (read / write / send), `timeout_ms`, `retry_policy`, `enabled` boolean. Adding or revoking agent capabilities is configuration. The dashboard surfaces the current tool surface.

**Derived from:**
- Requirement: §Visible operation — visibility into agent capability
- Requirement: §The coordinator out of the bottleneck — clear ownership of the dividing line

**Reasoning:** Visibility into what the agent can and cannot do is essential for trust. Configuration-not-code makes the dividing line auditable and adjustable without code deploys. Permission scope makes "this tool can read; this one can send to caterers" structurally enforceable.

**Implications:** The agent's tool-call layer reads from this registry; calling a non-registered tool fails by design. Tools added via configuration; risky tools (e.g. send) default disabled.

---

### D-69 — Every tool call captures the full request and response, with secrets redacted at capture time

**Decision:** `agent_tool_call.arguments` and `.response` columns store the structured request and raw response respectively. A pre-storage redaction pass removes secrets (API keys, OAuth tokens, parent contact details where not relevant to the call) by pattern match. Redaction is at capture; replayed views never see the unredacted values.

**Derived from:**
- Requirement: §Visible operation — full record
- Requirement: §Graceful failure — replay capability

**Reasoning:** Full capture supports replay debugging. Redaction at capture (rather than at view) prevents accidental exposure through downstream surfaces or log exports. Secrets that aren't stored can't leak.

**Implications:** A redaction rule set in configuration. New tools that introduce new secret types extend the rule set. Replay tooling reads from the redacted records.

---

### D-70 — Operational events are tiered into routine / notable / escalation

**Decision:** Every recorded event (`agent_decision`, `agent_tool_call`, system event, externally observed event) carries a `tier` enum: `routine` (expected and successful), `notable` (unusual but handled — a walk-back, automated MOQ recovery, fallback to base margin), `escalation` (requires human input). Dashboards default to notable + escalation; routine is queryable but not shown by default.

**Derived from:**
- Requirement: §Visible operation — "Routine activity must be distinguishable from notable activity"

**Reasoning:** Two-tier (routine / escalation) underfits the middle case — events the operator wants to be aware of but doesn't need to act on. Three tiers capture the operational shape better.

**Implications:** Every event-producing path assigns a tier. Dashboards have a tier-filter default. Analytics over the routine tier (e.g. agent throughput) remain available.

---

### D-71 — Two dashboard surfaces — real-time and forensic — read from the same underlying event tier system

**Decision:** A real-time stream view shows current-week activity, agent runs in progress, pending escalations, sessions running today. A forensic browser supports query by date, school, caterer, student, event type, decision type. Both read from the same tiered event tables (D-70).

**Derived from:**
- Requirement: §Visible operation — "forensic surface for the human approver reviewing later and as operational surface for anyone watching the system work in real time"

**Reasoning:** Requirement names both surfaces explicitly. Reusing the tier system avoids two parallel records and ensures the two views are consistent.

**Implications:** Read-only views over the operational tables. Real-time view has a WebSocket feed for live updates; forensic view runs structured queries.

---

### D-72 — Escalations are first-class records with lifecycle: open → assigned → resolved (or auto-closed by superseding event)

**Decision:** An `escalation` table holds (id, type, severity, created_at, source_decision_id, surface_context, suggested_actions, status enum, assigned_to, resolved_at, resolved_by, resolution_action, resolution_notes). Status enum: `open` / `acknowledged` / `in_progress` / `resolved` / `superseded`. Dedup logic prevents duplicate escalations of the same root cause within a window.

**Derived from:**
- Requirement: §Visible operation — "fail loudly rather than silently"
- Requirement: §Graceful failure

**Reasoning:** Escalations are how the agent communicates "I need a human"; treating them as first-class records makes them queryable, dedup-able, and audit-traceable. Lifecycle states match the operational reality (an operator sees an escalation, starts working it, resolves it; or a later event makes the escalation moot).

**Implications:** Schema for the table. Notification routing reads `severity`. Dedup window is per type (e.g. caterer non-response: 4 hours; dietary no-match: 24 hours).

---

### D-73 — Escalation reply protocol uses a structured email subject-line carrying the escalation ID and action token

**Decision:** Outbound escalation emails to the operator carry a subject line of form `[Padea EscX-{id}] {short summary} — Reply: {action_tokens}`. The operator's reply (e.g. "approve") matches against the action_tokens to identify the chosen action. The inbound parser closes the escalation and records the chosen action.

**Derived from:**
- Requirement: §Visible operation — record of decision
- Requirement: §The coordinator out of the bottleneck

**Reasoning:** Replying by email is the operator's lowest-friction interface. The structured subject line makes the agent's inbound parsing reliable without needing the operator to use a UI for every approval. The escalation ID survives email-client mangling better than body text.

**Implications:** Outbound email composer constructs the subject. Inbound email handler parses subject lines first, body second.

---

### D-74 — Every mutable entity has an immutable `_history` table capturing prior values, actor, cause, and timestamp

**Decision:** For each mutable entity (enrolment, dietary, capability, order, caterer, contact, menu_item, etc.), a parallel `<entity>_history` table captures rows of form (history_id, entity_id, changed_at, changed_by_actor enum [`system` / `user` / `agent`], changed_by_id, cause_run_id, cause_decision_id, prior_values JSON, new_values JSON). Mutations cannot bypass history capture — the application layer enforces this.

**Derived from:**
- Requirement: §Visible operation — "an inspectable record of every meaningful decision it makes"
- Requirement: §Graceful failure — partial state and recovery

**Reasoning:** History is the only structure that survives bugs in the mutation path. Cause linkage (run_id, decision_id) ties each change back to the agent decision that produced it, supporting the "why did this change?" query.

**Implications:** Schema gains a parallel history table per mutable entity. ORM or query layer enforces capture; no direct UPDATE without history. Storage cost is real; archival policy retains history for an operational period (initially: indefinite, reviewable later).

---

### D-75 — Soft delete is the default; hard delete requires an administrative action with its own audit trail

**Decision:** "Removing" an entity sets `deleted_at` and `deletion_reason`. The entity remains in history views and is excluded from operational queries by default. Hard delete is a separate administrative function with its own audit row.

**Derived from:**
- Requirement: §Visible operation
- Requirement: §Graceful failure

**Reasoning:** An entity's existence is part of operational history (a former caterer; a withdrawn enrolment). Hard delete creates retrospective ambiguity — "was this caterer ever used?" becomes unanswerable. Soft delete preserves what was there while removing the operational visibility.

**Implications:** Application queries filter `deleted_at IS NULL` by default. Reports that need to count former entities query without the filter.

---

### D-76 — Raw inputs are preserved verbatim before any interpretation, extraction, or routing

**Decision:** Inbound messages (parent absence emails, school exclusion notes, caterer replies), manager free-text submissions, voicemail audio, and external tool responses are stored verbatim with timestamp before being passed to extractors, classifiers, or matchers. Interpretation creates derived records; the raw record remains immutable.

**Derived from:**
- Requirement: §Graceful failure — "Where the system encounters input it does not recognise, the input must be captured verbatim before any interpretation is attempted, so interpretation failures do not lose data"

**Reasoning:** Requirement explicitly demands verbatim capture. Verbatim-then-derive lets us re-run extraction with new versions or rules without losing source data, and protects against the case where an interpretation bug corrupts a derivation.

**Implications:** Schema has raw-input tables for each inbound stream. Re-extraction creates a new derivation row referencing the same raw row. Storage cost rises with input volume but the cost is bounded and the protection is operationally critical.

---

### D-77 — Outbound emails are rendered from versioned templates with the rendered body stored verbatim per send

**Decision:** Each `email_template` has `name`, `version`, `body_template` (with slot placeholders), `subject_template`. Each send produces an `outbound_email` row with `template_id`, `template_version`, `slot_fills` (JSON), and `rendered_body` (final string). Past sends always reproducibly resolve to their original body even if templates change.

**Derived from:**
- Requirement: §Visible operation — reproducibility
- Requirement: §Graceful failure

**Reasoning:** The rendered body is the source of truth for what was sent. Storing it verbatim — rather than reconstructing at view time from template + slots — protects against template changes invalidating historical records.

**Implications:** Schema has both template and rendered-body fields. View tooling reads rendered_body, never recomposes.

---

### D-78 — The agent records its own version (model, prompt set, tool registry hash) per run

**Decision:** Every `agent_run` row carries `agent_version`: model identifier, prompt-set version, tool registry hash. A version manifest table records what each version contained (prompts, tools enabled, configuration values). Replay reads the version manifest to reconstruct the agent's surface at the time of the run.

**Derived from:**
- Requirement: §Visible operation — reproducibility of decisions
- Requirement: §Graceful failure — replay

**Reasoning:** Reasoning is a function of the prompt set and the available tools as much as the data. Without version capture, replay is approximate. Hashing the tool registry catches changes that prompt-version alone misses.

**Implications:** Schema has agent_version_manifest table. Replay tooling reads it. Version transitions are explicit events.

---

### D-79 — The agent's default behaviour on uncertainty is to escalate with the uncertainty explicitly characterised

**Decision:** When the agent encounters input it cannot confidently process, it creates an escalation with: the input (verbatim), what the agent inferred, what made it uncertain, what action it would take if directed. The agent does not proceed on ambiguity.

**Derived from:**
- Requirement: §Visible operation — "the default behaviour for 'I do not know what to do here' must be to ask, not to act"
- Requirement: §The non-negotiable safety floor
- Requirement: §Graceful failure

**Reasoning:** Requirement explicitly defines the default. The four-field escalation gives the operator enough to direct the agent rather than recompute the situation themselves.

**Implications:** Escalation type `uncertainty` is high-priority. The agent's prompt set explicitly enables "ask, don't act" as a primary heuristic.

---

### D-80 — Crashed runs are detected by heartbeat absence and surfaced as a distinct escalation type

**Decision:** Each `agent_run` writes a heartbeat row every N seconds during execution. A separate watcher checks for runs whose heartbeat is stale beyond a configured threshold and marks them `status=crashed`. A `crashed_run` escalation surfaces with the last successful checkpoint and the apparent failure point.

**Derived from:**
- Requirement: §Graceful failure — "the partial state must be captured explicitly so a human can resume from the failure point"
- Requirement: §Visible operation — silent failure is excluded

**Reasoning:** A crashed run that silently never completes is the worst failure mode. Heartbeat absence is detectable without requiring the failing process to report its own failure.

**Implications:** Heartbeat writer in the agent runtime. Watcher as a separate cron-style job. The escalation includes resume guidance from the last checkpoint (D-87).

---

# Architecture and tooling

### D-81 — The schema substrate is SQLite local with a write-through mirror to a hosted Postgres (Supabase) for deployment

**Decision:** Development and demo run against a local SQLite database. The application layer mirrors writes to a hosted Postgres (Supabase) for any deployed environment. Reads at runtime go to local; queries from the operator dashboard go to Postgres. Schema is defined once and applied to both via migration tooling.

**Derived from:**
- Practical V1 environment — local development and a competition demo, with a plausible production migration path
- Requirement: §Graceful failure — local fallback if hosted service unavailable

**Reasoning:** SQLite gives offline dev and fast iteration; Postgres gives multi-user dashboard access and persistence. Write-through (rather than read-through) keeps local fast while Postgres holds the authoritative deployable state. The fallback path is local-only operation when Postgres is unreachable.

**Alternatives considered:** Postgres-only — slower local iteration. SQLite-only — no shared dashboard view across machines.

**Implications:** Schema migrations target both backends. Some Postgres-specific features (JSON operators, materialised views) need SQLite-compatible fallbacks or are gated behind a backend-detection flag.

---

### D-82 — Model selection: Sonnet for reasoning-heavy agent decisions; Haiku for routing, classification, and lightweight extraction

**Decision:** The agent uses Anthropic Sonnet (latest available) as the primary reasoning model for order composition, escalation drafting, and decision narratives. Lightweight tasks (inbound email classification, dietary-tag normalisation, voicemail entity extraction) route through Haiku to manage cost and latency.

**Derived from:**
- Practical V1 — cost / latency / quality balance
- Requirement: §The coordinator out of the bottleneck — agent must be operationally viable

**Reasoning:** Reasoning-heavy decisions justify the cost of a more capable model; lightweight tasks don't. The split is explicit so each task's model choice is reviewable.

**Implications:** Two model clients in the runtime. Model identifier is part of the agent version manifest (D-78). Switching a task between models is a configuration change.

---

### D-83 — Tool-calling loops are bounded with a configured cap and a timeout escalation on cap-reach

**Decision:** Each agent run has a maximum number of tool-call iterations (default 30). On reaching the cap, the run escalates with `cap_reached` type, providing the current state and the next decision the agent was attempting. Per-tool timeouts (D-68) apply within the loop.

**Derived from:**
- Requirement: §Graceful failure — "Where the system runs longer than expected, it must time out and escalate rather than hang"

**Reasoning:** Cap-bounded loops prevent runaway agent runs. Escalation-on-cap-reach surfaces the failure rather than truncating silently.

**Implications:** Runtime tracks iteration count. Escalations from cap-reach are distinct from other types.

---

### D-84 — The demo surface is an HTML decision-log file rendered from the operational tables, regenerated per run

**Decision:** A single HTML file rendered from the schema acts as the demo surface for V1. The file shows agent runs in reverse chronological order with nested decisions, tool calls, and escalations expandable. Generated by a build step from the database; not a live-server view.

**Derived from:**
- Practical V1 — competition demo requirements
- Requirement: §Visible operation — inspectable record

**Reasoning:** A static HTML file is the lowest-friction demo surface: portable, no hosting required, complete in itself. Regeneration per run keeps it current without a live server.

**Implications:** A render script reads the database and writes HTML with embedded CSS and minimal JS for collapse/expand. The file is itself a deliverable artifact alongside the schema.

---

### D-85 — Email I/O is simulated in V1 via inbox/outbox JSON files; real SMTP/IMAP integration is a later phase

**Decision:** For V1, an `inbox/` directory holds JSON files simulating inbound emails; an `outbox/` directory holds JSON files representing outbound emails. The agent reads from inbox and writes to outbox. The schema's outbound_email and raw_absence_notification tables capture the structured content. Real SMTP/IMAP wiring is a later phase that replaces only the file I/O layer.

**Derived from:**
- Practical V1 — competition demo with controlled inputs
- Requirement: §Graceful failure — simulated mode preserves operational continuity for the demo

**Reasoning:** The competition demo needs reproducible inputs and outputs without a real email pipeline. The JSON file format is human-inspectable. Replacing the I/O layer with SMTP/IMAP later is a localised change.

**Implications:** Schema captures the same structured content regardless of I/O backend. Tests run against the file backend. Real-email integration is an architectural extension, not a rewrite.

---

### D-86 — Outbound email send goes through a single `email_out` tool registered in the tool registry

**Decision:** All outbound email send paths route through one `email_out` tool. The tool reads from the outbound_email row, performs the actual send (file write in V1, SMTP later), records the outcome, and updates send status. No other path may send email.

**Derived from:**
- Requirement: §Visible operation
- Requirement: §Graceful failure

**Reasoning:** A single send path makes outbound traffic auditable, rate-limitable, and replaceable. Multiple send paths fragment the audit and risk by-passes.

**Implications:** Schema's outbound_email is the source; the tool is the conduit. Other code never calls send directly.

---

### D-87 — Agent runs progress through named checkpoints; state is persisted at each checkpoint, supporting resume rather than restart

**Decision:** Each agent run has named stages (e.g. `ingest` / `match` / `compose` / `economics_check` / `draft` / `send`). State is persisted at each checkpoint. A failed run can be resumed from its last successful checkpoint after the operator addresses the cause; the run re-enters at that stage with prior state intact.

**Derived from:**
- Requirement: §Graceful failure — "the partial state must be captured explicitly so a human can resume from the failure point"

**Reasoning:** Resumability protects work-in-progress against transient failures. Restart-from-start wastes prior LLM calls (real cost) and prior operator review.

**Implications:** Each stage has explicit input and output schemas. The runtime knows how to enter each stage with persisted state. Some stages are idempotent (re-running produces the same result); others are not and the resume path must handle this.

---

### D-88 — Degraded modes are explicit and labelled when activated; the operator dashboard surfaces them

**Decision:** When external systems fail (email transport unavailable, LLM API down, transcription service slow), the agent enters a labelled degraded mode and operates within reduced capability. Modes include `email_send_queued` (sends deferred until transport returns), `llm_extraction_paused` (raw inputs captured but not extracted), `voicemail_intake_paused`. The mode is visible on the dashboard with affected operations enumerated.

**Derived from:**
- Requirement: §Graceful failure — "the agent must degrade to a reduced mode that preserves operational continuity rather than failing entirely"

**Reasoning:** Explicit labelling lets the operator see when the agent is operating below full capability. Silent degradation is the failure mode the requirement excludes.

**Implications:** Each external dependency has a health check. Mode transitions are events recorded in the operational log. Recovery from a degraded mode triggers a re-process step (e.g. queued sends actually send when transport returns).

---

### D-89 — The workspace is a single repo containing source, data, schema migrations, prompts, the HTML demo render script, and a one-command bootstrap

**Decision:** Repo layout: `/agent` (runtime), `/schema` (migrations and DDL), `/prompts` (versioned LLM prompts), `/data` (source files and ingest outputs), `/inbox` `/outbox` (email simulation), `/demo` (HTML render script and output), `/tests`. A single `make bootstrap` target sets up the environment, applies migrations, and seeds the source data. Git is the version-control substrate; the prompts directory uses semantic versioning per prompt.

**Derived from:**
- Practical V1 — competition deliverable shape
- Requirement: §Visible operation — reproducibility

**Reasoning:** A single-repo, single-command setup is the lowest-friction onboarding for the assessor. Versioned prompts capture the agent surface across iterations.

**Implications:** No multi-repo coordination overhead. Migration tooling is local-friendly (alembic or similar). Prompts are referenced by version from the agent_version_manifest (D-78).

---

# Ambitious additions (predictive, analytical, cross-cohort)

### D-90 — Cross-school dietary trend intelligence runs as a nightly analytical job

**Decision:** A `dietary_trend` analytical view aggregates dietary-attribute prevalence by (school, term) and surfaces shifts in the operator dashboard ("halal-required enrolments at JPC up 40% term-on-term"; "vegetarian rate across the network: 4.2%"). Material shifts (>20% relative change, configurable) raise an information event for operator review. Aggregated counts (no individual identifiers) may be shared with caterers for menu-planning support.

**Derived from:**
- Requirement: §Quality maintained over time — "alternatives credible", "facts the system must hold and keep current"
- Requirement: §Sufficient variety
- Observation: §Dietary information — 18 distinct cell values across 320 enrolment rows

**Reasoning:** Dietary cohorts shift over time. A school whose halal-required enrolments doubled in a term may need menu adjustments from the current caterer or a different caterer entirely. Trend visibility supports this proactively rather than reactively. Aggregated-counts sharing with caterers honours A37 (privacy) while supporting their menu planning.

**Implications:** Nightly analytical job. Dashboard module. Caterer-facing aggregate report with explicit no-identifier guarantee.

---

### D-91 — Calendar-aware absence prediction trains weekly with school-level features and feeds margin sizing

**Decision:** A per-school absence prediction model is trained on a rolling 12-week history with features: trailing absence rate, day-of-week, calendar-week-of-term, exam-period flag, public-holiday-adjacent flag, end-of-term flag, weather forecast. Predictions feed the margin calculation (D-20) alongside the walk-up predictor (D-25). Retrains weekly during composition.

**Derived from:**
- Requirement: §Reliable meal delivery — "small enough to keep order economics tractable and large enough to avoid routine shortfalls"
- Observation: §Absences

**Reasoning:** Calendar features capture systematic patterns the base rate misses. Exam weeks reduce absences (students need study sessions); end-of-term increases them (families travel). Weekly retraining is fast enough to capture recent shifts.

**Implications:** Model training is a tool registered in the tool registry. Predictions are stored per (school, session_date) for audit. Calendar feature lookups need a school-calendar data source.

---

### D-92 — Auto-drafted recovery emails exist for every escalation type; send is never autonomous

**Decision:** For each escalation type with an outbound communication component (caterer non-response, dietary no-match, late cancellation, capability reconfirmation needed, parent follow-up for stale meal-options selection), the agent generates a draft recovery email at escalation creation. The draft is attached to the escalation. The operator approves, edits, or dismisses.

**Derived from:**
- Requirement: §The coordinator out of the bottleneck — routine off the desk, judgement preserved
- Requirement: §Graceful failure

**Reasoning:** Drafting saves the operator time. Never-autonomous send preserves the operator's authority over relationship-critical communications. The draft is itself a useful artefact even when the operator decides on a different course.

**Implications:** Each escalation type has a template (D-77) and a slot-fill specification. The draft is rendered at escalation creation and stored alongside.

---

### D-93 — Agent decision narratives are explicitly designed for natural-language explanation rather than structured-only logging

**Decision:** The agent decision logging step generates a narrative explaining the decision in plain English suitable for an operator reading the dashboard. The prompt that produces this narrative includes the structured inputs, the alternatives considered, and the choice made, and asks for a 2–4 sentence explanation referencing the inputs by name.

**Derived from:**
- Requirement: §Visible operation — "legible, not merely complete"

**Reasoning:** Structured logs require interpretation; narratives are immediately readable. The narrative is what makes the dashboard's notable-events feed useful to an operator scanning their day, where structured-only logs would require active querying.

**Implications:** A separate LLM call per decision (small cost). The narrative is stored as the canonical human-facing summary; the structured fields support querying and analytics.

---

### D-94 — Reconciliation is a structured operator action per session, capturing actual attendance, walk-ups, and excess meals

**Decision:** A `session_reconciliation` table holds (session_id, completed_at, actual_attendance_count, walk_up_count, excess_meal_count, notes, completed_by). The manager submits reconciliation as part of the session report (D-52) within 24 hours of session end. Reconciliation feeds margin tuning (D-20), walk-up prediction (D-25), and partial-exclusion attendance margin (D-42).

**Derived from:**
- Requirement: §Reliable meal delivery — "Where the margin is regularly exhausted or regularly unused, the system must surface this as a signal for re-sizing"
- Requirement: §Quality maintained over time

**Reasoning:** Margin tuning requires per-session ground truth. Reconciliation is that ground truth. Capturing it consistently is the input to the learned adjustment in D-20.

**Implications:** Schema row per session. Manager workflow includes the field. Tuning calculations read this table.

---

# Open Questions

These are commitments I could not lock from the context documents alone. They need operator input before V1 schema-write begins.

**Q-1. What is the MOQ shortfall penalty rate?** A14 commits us to "Padea pays for the MOQ floor regardless of whether the meals are needed" but the data does not state per-caterer terms. Is the shortfall billed at full per-meal price? At a reduced rate? Is there a buffer? The order-economics simulation (D-26) renders the cost figure, so the rate is needed before V1 can run end-to-end.

**Q-2. Do opt-out students pay for the session?** A7 commits opt-out as a per-enrolment property but does not address the commercial side. If they pay, partial exclusions and opt-out treatment differ from each other. If they do not, the system has a financial-status field on enrolment that is currently unmodelled.

**Q-3. What is the lead-time floor per caterer?** Required for the caterer-confirmation deadline computation in D-64. The source data does not include per-caterer lead-time. Either a single network-wide default exists, or each caterer states their own at onboarding.

**Q-4. How is the operator's identity authenticated for dashboard and reply-by-email flows?** D-73 (escalation reply protocol) assumes the inbound email is from a trusted operator. The current data has no operator-identity model. Single email address acceptable for V1, or do we need a user table?

**Q-5. Late-cancellation policy commitment.** The assumptions doc flags this (A33 and the open questions section): the system escalates, but the operator must choose between cancel-caterer / accept-and-donate / pay-anyway. D-44 surfaces the three options. Should one be the default proposal? Should the system pre-favour an option based on cost?

**Q-6. Caterer onboarding workflow.** Several decisions (D-32 caterer attestation, D-65 capability re-confirmation, D-62 caterer-facing scorecard URL) assume a caterer onboarding flow exists. Its shape is unspecified in the context. V1 may need to either build a minimal onboarding flow or document the assumed pre-onboarded state.

**Q-7. Parent identity resolution.** Per-parent false-absence rate (D-40) and walk-up prediction (D-25) read per-parent stats. The source data's parent records are name+email+mobile, but a child can have multiple parent records, and parents at different schools share enrolments under separate parent rows. Should ingest attempt parent-identity merging (analogous to student merging in D-03)?

**Q-8. Voicemail intake source.** D-35 commits to voicemail-as-channel but does not specify how voicemails reach the system. Forwarded to an inbox? A phone number tied to a transcription service?

**Q-9. Term boundaries and calendar source.** D-65 (capability re-confirmation at term boundary) and D-91 (calendar-week-of-term feature) need a term-calendar data source. The source data does not include one. Manual operator entry, or external feed?

**Q-10. Should walk-up insurance ever override absence-suppressed margin reduction?** D-39 says late-arriving absences don't reduce the order. But what about a partial exclusion that arrives mid-week — the cohort shrinks, and a parent then walks back an absence? The composition has not yet sent. The interaction is not fully specified.

---

# V2 Cut Candidates

These are the decisions most likely to be the first to go under a pedantic stripping pass. Each is a place where V1 ambition exceeds what's necessary for the system to function. V2's job is to cut these; V3's job is to argue any of them back in with explicit justification.

**Predicted first to cut (the ten most likely):**

1. **D-36 — Voicemail intake with transcription and LLM extraction.** Email is the dominant channel per A26; adding a voice intake path with two external dependencies (transcription + LLM extraction) is V1-ambitious and operationally rare. V2 strip: email + form only.

2. **D-56 — Manager opportunistic meal photo capture.** The deterrent argument is real but photos aren't load-bearing for any other decision; the channel adds operator burden and storage. V2 strip: ratings + manager text only.

3. **D-58 — Cross-cohort taste-compatibility matrix.** A new enrolment's cold start is solved adequately by a default dietary-compatible candidate set; the matrix is sophistication that V1 doesn't strictly need. V2 strip: cold-start with dietary candidate set, sorted alphabetically.

4. **D-90 — Cross-school dietary trend intelligence.** Useful for proactive caterer conversations but no requirement directly forces it; trend visibility can wait until the data has accumulated enough to make trends meaningful anyway. V2 strip.

5. **D-91 — Calendar-aware absence prediction model.** Trailing rate alone gets us most of the way there. The exam-period and end-of-term features add accuracy that an early-stage operation cannot evaluate. V2 strip: base rate + day-of-week only.

6. **D-40 → predictive component — Per-parent false-absence rate fed into prediction.** Per-school rate is enough for V1 margin sizing; per-parent is granularity we'll likely need later but not at launch. V2 strip the per-parent feature in the predictor; keep the per-parent stats for surfacing high-rate parents on the dashboard (cheap to keep).

7. **D-55 — Submission-timing weighting on ratings.** Adds a multiplicative factor to every aggregation calculation in service of catching memory degradation. V1 can apply baseline normalisation (D-53) and time-decay (D-54) without it. V2 strip.

8. **D-53 — Rater baseline normalisation.** This will hurt to cut because it's the most mathematically principled step in the feedback pipeline, but it requires a per-rater materialised view and assumes enough rating-history to make a baseline. V2 cuts it back to raw averages with time-decay; V3 likely reinstates it.

9. **D-51 — LLM extraction of dimensional signal from rating comments.** Per-attribute extraction (taste / portion / temperature) is V1-ambitious; the raw comment is itself useful operator-facing data. V2 strip: keep comments as freeform text only.

10. **D-26 — Order economics simulation showing alternatives.** The decision-narrative explains the chosen composition; showing four alternatives alongside is decision-support that V1 can demonstrate but doesn't strictly need to ship. V2 strip: composition + reasoning only, alternatives on request.

**Likely second-tier cut candidates (the next five):**

11. **D-58 cousin — Cohort-subset exclusion scope.** Whole-session and year-levels handle the observed cases; cohort_subset (e.g. "Physics students at competition") anticipates a future case A31 mentions but the data doesn't yet show. V2 strip cohort_subset; reinstate when a case actually appears.

12. **D-62 — Caterer-facing scorecard view.** The internal comparative dashboard (D-63) gets us most of the deterrent value through operator-mediated communication. Caterer-self-serve dashboard requires auth, hosting, and design that V1 doesn't strictly need.

13. **D-70 → tier — Three-tier event taxonomy.** Routine / notable / escalation is more granular than V1 strictly needs; two tiers (notable / escalation) capture the actionable distinction. V2 strip the routine tier; let unreported activity be unreported.

14. **D-67 → narrative — Plain-English reasoning narrative per decision.** Structured logging plus a per-run summary is enough for V1 visibility. Per-decision narratives generate an LLM call per branching point and produce text that nobody may read. V2 strip per-decision narrative; keep per-run summary.

15. **D-83 — Tool-calling loop cap of 30 with cap-reach escalation.** Caps are good; 30 may be tighter or looser than needed. V2 might cut the explicit cap-reach escalation flow back to a simpler timeout, with cap-reach folded into the general crashed-run path (D-80).
