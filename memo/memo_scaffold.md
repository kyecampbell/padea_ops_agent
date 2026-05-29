# Memo Scaffold — Padea Operations Agent

**Purpose:** Structural scaffold for the final memo. Not polished prose — anchors,
headings, and the core sentences that belong in each section, drawn directly from
memo_material.md, the design ledgers, and chat_history. Distil this into the actual
submission memo; do not copy it verbatim. Every claim here is traceable to a source doc.

---

---

# PART I: TIMELINE

## How to frame the timeline for the reader

The timeline is non-linear by construction. The design conversations that produced
the V3 architecture predate the project repository. The V1–V3 documents in docs/ are
a **retrospective overlay** — applied to make the journey examinable, not a faithful
chronological record. The V1→V5 progression was planned; V4 and V5 were cancelled
under time pressure. Understanding this is required to read the memo honestly.

---

## Phase 0 — Pre-repo design (pre-2026-05-25, ~20 hours)

**What happened:** The schema was designed through conversation with a Claude instance
before any file was written. Approximately 20 hours of conversational design produced
what is retrospectively labelled V1 through near-V3. The 26-table V1 architecture
and the V2 cut-and-rationalise pass both happened in this phase.

**What was NOT done first:** The source data files were not opened until after the
schema was substantially designed. That order was wrong and is acknowledged explicitly
(see Key Lessons).

**Critical output:** The six priorities that locked on Day 1 (from memo_material.md):
1. Safety and correctness — non-negotiable floor
2. Coordinator out of the bottleneck
3. Feedback loop closes
4. Rotation has teeth
5. Build is legible
6. Fails gracefully
Cost optimisation explicitly demoted to "constraint, not goal." Every downstream
decision flows from this ordering.

**The brief's hinge moment:** One line in the brief — *"the goal of this system is
not just that meals are ordered and delivered each week"* — determined everything
downstream. Reading it literally would have produced an order-generation script.
Reading the implication produced a satisfaction-loop system with quality monitoring
and caterer rotation mechanics. The memo's opening should anchor here.

---

## Phase 1 — Design materialised: the V1→V3 arc (2026-05-25–26)

**What happened:** The conversational design was extracted into structured documents.
V1 → V2 → V3 documents produced. Decision ledger written. Assumptions documented.
Data observations made.

**V1 (26 tables):** Ambitious first-draft architecture. Included ML-predicted absence
margins, a full caterer-school capability matrix, payment tables, order economics
scenario snapshots, menu effective-date history, and a full escalation lifecycle state
machine.

**V2 (strip pass):** Pedantic deletion — everything cut that couldn't survive the
"does this earn its place at Padea's current scale?" test. ~14 tables survived.

**V3 (add-back with justification):** Ten documented add-back decisions (V3-FB-01
through V3-AI-01). Every addition has written reasoning. Deletions stay deleted.
The process makes thinking visible; that visibility directly serves the Learning
criterion.

**Key moment:** The V1→V5 plan (V1 ambitious → V2 cut → V3 add back → V4 simplify
→ V5 accelerate). V4 (simplification pass) and V5 (cycle-time acceleration) were
both cancelled when it became clear the build phase needed to start. This was a
deliberate trade-off, not an oversight. See Key Lessons.

---

## Phase 2 — Project scaffolding and tooling setup (2026-05-27, Session 001)

**Date:** 27 May 2026

**What happened:**
- Absorbed all design context (V1–V3) from prior design conversations
- Cancelled V4/V5 passes; deleted their placeholder folders
- Build stack confirmed: Supabase Postgres + Claude Sonnet 4.6 + Gmail API + uv/Python 3.12
- venv created (uv + Python 3.12)
- agent_context/ folder built from scratch: system_prompt.md, domain_knowledge.md,
  runtime_config.yaml, tools_reference.md
- config/settings.py implemented with Pydantic settings loader
- requirements.txt built with real package list

**What was NOT done at end of session:**
- Supabase project not created
- Gmail credentials not obtained
- Source data (xlsx/pdf) not parsed
- Database schema not deployed
- src/ directory still stubs

---

## Phase 3 — Schema review and V4 optimisations pass (2026-05-28, Sessions 002–004)

**Date:** 28 May 2026

**What happened:**
- v3_summary.md reviewed with 17 annotated NOTEs; all resolved. Material changes:
  - "other" free-text allergy field added to enrolments (→ operator escalation flow)
  - Manager checklist expanded from 2 boolean columns to 5 specific boolean questions
  - Per-session order vs. Monday summary split made crystal clear
  - Walk-back paragraph documented explicitly
  - Meal request picker described accurately (separate box, full dietary-safe menu)
- Two schema additions identified and queued: other_allergy_notes on enrolments,
  three checklist columns on feedback
- V4 optimisations pass (OPT-01 through OPT-07) run against the V3 schema:
  - OPT-01: updated_at trigger function (V3 default-only was silently stale)
  - OPT-02: three text-CHECK columns promoted to Postgres enum types
  - OPT-03: gmail_message_id partial index upgraded to UNIQUE constraint
  - OPT-04: caterer_id denormalised onto feedback (rolling-mean hot path)
  - OPT-05: gst_rate_percent snapshotted onto orders (accounting correctness)
  - OPT-06: menu_items' 8 dietary boolean columns replaced with junction table (shared vocabulary with student dietary_tags)
  - OPT-07: enrolment_session_slots junction table added (multi-session schools — critical correctness bug in cohort query)
- Supabase project created, DATABASE_URL confirmed, V4 schema deployed and verified
- Smoke test: PostgreSQL 17.6 confirmed, all tables visible

**Critical find during V4 pass:** OPT-07 was a correctness bug masquerading as an
optimisation. Without the enrolment_session_slots junction, the cohort query for
any session at a multi-session school (ISHS has three sessions: Mon/Tue/Thu) would
return all enrolments at the school rather than only the session-specific subset.
For ISHS Monday (36 students), the uncorrected query would have returned all 120 ISHS
students — tripling the order count. This would have been caught at integration test
time, but it was better caught here.

---

## Phase 4 — Source data ingest and DB population (2026-05-28, Sessions 005–007)

**Date:** 28 May 2026

**What happened:**
- All 7 source files reviewed: students.xlsx, sessions.xlsx, caterers.xlsx,
  caterer-menus.pdf, caterer-contacts.pdf, absences.pdf, exclusions.pdf
- data_inventory.md written: Phase 2 ingest planning + 10 locked decisions
- 14 seed scripts written in src/ingest/ (10 core + 4 dummy demo scripts)
- DB core data seeded: 11 dietary_tags, 6 schools, 4 caterers, 7 tutors, 40 menu_items,
  205 dietary tag links, 11 session_slots, 11 session_tutor_assignments, 320 enrolments,
  61 enrolment_dietary_tags, 10 absences, 4 exclusions, 320 enrolment_session_slots
- DB dummy demo data seeded: term_meal_preferences, term_meal_preference_items,
  canonical_menu_order on caterers, 55 historical orders (5 weeks, Apr–May 2026),
  55 manager feedback rows (Terrific on engineered declining trend), 9 upcoming
  exclusions (ISHS camp + school holidays), ~11 upcoming absences

**Deliberate scope cut documented:** order_lines seeded as 0 rows. The core
quality-decline arc (detect → warn → RFP) runs entirely on session-level manager
ratings. The tutor-pattern escalation path (per-meal tutor feedback) requires
order_lines data to fire; with zero rows, it cannot demonstrate. This is a deliberate
deprioritisation — one escalation path demonstrable, not two. See "Things explicitly
documented as missing."

**Structural find from data review:** Lakehouse at MBBC — 18 students vs. 25 MOQ
at 6 items. This isn't a theoretical capability; it's a guaranteed demo moment. The
data makes MOQ shortfall escalation demonstrable rather than hypothetical. Would
have been found earlier had data been reviewed before design. See Key Lessons.

**Pricing anomaly deliberately not corrected:** Kenko at $5.50/item vs. Lakehouse
at $35/item. Real-world plausibility says Kenko is implausibly low. Decision: treat
source data as accurate. The ops engineer's job is not to second-guess inputs.
Flagged for Dylan, documented in data_observations.md.

---

## Phase 5 — Tool layer (2026-05-28, Sessions 008–012)

**Date:** 28 May 2026

**Tools built:**
- src/tools/enrolments.py — get_enrolments_for_session (with other_allergy_notes),
  get_enrolment_dietary_tags
- src/tools/meals.py — item_is_safe_for_enrolment, auto_pick_dietary_meal,
  get_meal_request, consume_meal_request, get_next_rotation_meal (bug fixed:
  ol.created_at → MAX(o.session_date) via JOIN)
- src/tools/orders.py — compose_session_order, create_order, compose_order_email
- src/tools/infrastructure.py — create_agent_run, complete_agent_run, log_agent_step,
  check_and_resolve_crashed_runs
- src/tools/sessions.py — get_sessions_needing_orders, get_session_slot
- src/tools/absences.py — get_absence, upsert_absence, get_exclusions,
  get_year_level_exclusions
- src/tools/quality.py — get_feedback_for_session, compute_rolling_mean,
  get_feedback_since
- src/tools/caterers.py — caterers_within_range, project_weekly_cost, check_weekly_moq

**Critical safety hole closed:** compose_session_order originally checked
item_is_safe_for_enrolment only on the dietary_auto_pick path. A student could receive
an unsafe meal via the rotation or request paths without any safety check. Fixed:
item_is_safe_for_enrolment runs on ALL three paths (rotation, request, dietary_auto_pick).
Verified with test that catches safe=False on a request-source violation.

**Safety_records design:** compose_session_order returns a safety_records list — one
dict per assigned student with meal_name, dietary_tags, safe, other_allergy_notes,
source, enrolment_id, student_name, menu_item_id. The loop reads this list and logs
urgent steps independently of the model. Dietary safety logging is loop-owned, not
model-owned — it fires regardless of whether the model notices.

**Geocoding shortcut acknowledged:** Production would use pgeocode or a postcodes API
with coordinates stored on the schema. For the demo: 8 QLD postcodes (6 schools + 4
caterers, all known) hardcoded as dict derived from ABS locality data. geopy geodesic
runs offline against those centroids. Raises ValueError on any unrecognised postcode.
The correct production fix is one schema change (lat, lon on schools and caterers);
the dict is the correct demo shortcut. Consciously documented.

---

## Phase 6 — Agent loop (2026-05-28, Sessions 013–016)

**Date:** 28 May 2026

**What was built:**
- TOOL_SCHEMAS (21 schemas), TOOL_REGISTRY (20 tools), _PARAM_TYPES (12 types),
  _serialise(), dispatch() — the mechanical layer that bridges Claude's JSON
  tool-use response to Python function calls
- run() with 5-step pipeline (get_sessions_needing_orders → exclusion check →
  compose + order → quality check → complete_agent_run)
- Hard-cap logic: max_tool_calls_per_run enforced at dispatch; max_calls_reached
  logged as urgent; final summary injected regardless
- STEP 3c: safety_records unconditional logging after any compose_session_order
  dispatch — dietary_safety_violation and allergy_note_unverified steps logged by
  the loop, not the model

**Tests written:**
- scripts/test_dispatch.py — 32 unit tests, mocked, no DB
- scripts/test_loop_cap.py — 16 tests (13 cap + 3 shortfall urgency)
- scripts/test_safety_records.py — 231 tests (19 mocked unit + 212 integration, real DB)

**Key detail on STEP 3c integration test:** The integration test against the real DB
caught a field mismatch — the mock fixture used a "reason" field that the real
compose_session_order does not return. Reasoning f-strings were updated to use
meal_name, dietary_tags, source instead. This is the kind of bug that only surfaces
at integration, not unit, test level.

---

## Phase 7 — First live run and prompt correction (2026-05-29, Sessions 017–018)

**Date:** 29 May 2026

**STEP 4 first attempt (run_id=5):**
- Target: slot 3 (JPC Wed, Terrific) + slot 11 (CHAC Wed, GYG), session 2026-06-03
- Result: CAP HIT at 15/15. No orders written. No mutations.
- Root cause: system_prompt.md's "Order composition pipeline" section described
  the internals of compose_session_order step-by-step. The model followed those
  instructions literally, calling get_exclusions, get_enrolments_for_session,
  get_year_level_exclusions individually, then beginning to fan out get_meal_request
  for all 72 students in parallel, never reaching compose_session_order itself.
- Infrastructure verdict: cap logic, urgent logging, final summary all worked correctly.
  The loop was correct; the prompt was wrong.

**Prompt rewrite:**
- 8 steps → 5 (compose_session_order direct; 6 forbidden internals listed)
- One session per run
- Quality 24h skip-out
- max_tool_calls_per_run raised from 15 to 20 (worst-case single-session ≈ 13, 7 headroom)

**STEP 4 re-run — both targets banked:**
- run_id=6 (slot 3, JPC Wed, Terrific): 9 tool calls, 2:56 runtime. Order 132:
  33 students, $676.50. 2 urgent no_safe_meal escalations (Aanya Desai enr 63,
  Edward Cook enr 77 — both vegetarian; Terrific has no inherently-vegetarian items)
- run_id=7 (slot 11, CHAC Wed, GYG): 8 tool calls, 3:06 runtime. Order 133:
  38 students, $570.00. Zero escalations, zero dietary violations.

---

## Phase 8 — Discovered gap and Option C design (2026-05-29, Session 019)

**Date:** 29 May 2026

**Finding:** The 2 urgent no_safe_meal escalations from slot 3 are not bugs. They are
correct per Decision D7 (data_inventory.md): VO items are not tagged vegetarian.
"VO = Vegetarian Option" in the caterer PDF means "can be made vegetarian on request"
— it is not an inherent dietary property of the item.

**The gap:** A vegetarian student at a school served by Terrific receives a "no safe
meal" escalation every week because Terrific's menu has no inherently-vegetarian items,
only VO items. The correct behaviour is: attempt to serve a VO item as a safety
fallback for vegetarian students, rather than immediately escalating.

**Option C design (approved, not yet built):**
- Schema: two additive ALTER TABLE statements + UPDATE (no enum change — enum
  ADD VALUE is irreversible on Supabase)
- Selection chain: inherent-safe → VO fallback (item.tags ⊇ student.tags − {'vegetarian'}
  AND has_vegetarian_option=true) → escalate
- Safety invariant: safe computed from the selection condition, not hardcoded True.
  Any non-vegetarian dietary gap still fires UNSAFE MATCH.
- VO is invisible to non-restricted students; it is a fallback only, never a preference.

---

---

# PART II: KEY DECISIONS

## D1 — Brief interpretation: satisfaction loop vs. order script

**The decision:** Read the brief as asking for a satisfaction-loop system (meal
quality, caterer rotation, feedback, student satisfaction) rather than an
order-generation script.

**What anchored it:** "The goal of this system is not just that meals are ordered
and delivered each week." That one line changed everything.

**What was rejected:** A literal reading would have produced a simpler system:
compute cohort minus absences, pick meals, email caterer. Functional, but not what
the brief was actually asking for.

**Why it matters for the memo:** This is the moment where the design either earns
its ambition or misses the point entirely. Everything downstream — the feedback
ecosystem, the rolling mean, the decline detection, the caterer rotation chain —
is a consequence of this interpretation. Get the interpretation wrong and none of
the complex architecture is warranted.

---

## D2 — The six priorities locked Day 1, cost explicitly demoted

**The decision:** Six ordered priorities. Cost optimisation explicitly ranks below
all operational goals.

**What was rejected:** V1 had cost as a first-order optimisation target — variety
tiering at order composition, MOQ surplus calculations, order economics scenario
snapshots. All of these optimised cost at the expense of student satisfaction and
system simplicity.

**The reframe:** Cost is a constraint, not a goal. The system orders what students
need; cost falls out of that. Where MOQ is not met, pay the difference and notify.
"We removed every margin concept because each margin solved a problem we don't have
data to model." The system grows into cost awareness; it doesn't start there.

---

## D3 — Delete by default: V2 as the pedantic strip pass

**The decision:** V2 was the aggressive deletion phase. Everything cut unless it
could survive: "does this earn its place at Padea's current scale?" Not "is this
useful" — "does the value justify the build cost now."

**What survived:** 14 core tables (of 26). Dietary safety, order composition,
enrolment lifecycle, basic escalation infrastructure.

**What was cut:** Caterer capability matrix, ML prediction, payment tables, order
economics snapshots, menu history, escalation lifecycle state machines, parent
contact tables, cross-school identity resolution.

**Why documented:** "The rejected alternatives are documented in the decision register;
pruning happened iteratively during design, not in a single deletion pass." V3 adds
back with justification. The process makes thinking visible.

---

## D4 — V3 add-backs: ten justified reinstated features

**The decision:** Ten V3 decisions (V3-FB-01 through V3-AI-01) add back features
that survived the value-vs-complexity test applied at V2's deletion phase. Every
addition has written reasoning.

**Key reinstated features:**
- Multi-source feedback ecosystem (V3-FB-01) — the most complex, highest-value add.
  Without this, V3 has no quality signal and no rotation trigger.
- Region-based RFP targeting (V3-CR-01) — replaces V1's 10-column capability matrix
  with 3 columns and a distance query.
- Per-session cadence (V3-AI-01) — replaces V2's Thursday-for-all-week (a human
  calendar artifact) with 72-hours-before-each-session (a system-native cadence).
- Three-date enrolment lifecycle (V3-EL-01) — derives active state from dates, never
  stores it.
- Three-tier escalation urgency (V3-OE-01) — flat decision log with urgent/notable/
  informational, no lifecycle state machines.

---

## D5 — Per-session cadence as the architectural design call

**The decision:** Replace Thursday-for-all-week with T-72hrs-per-session.

**What was wrong with Thursday-for-all-week:** It was an artifact of the human
coordinator's schedule, not a system requirement. Different caterers serve different
days; they don't all deserve the same Wednesday-morning-order just because the
coordinator worked Thursdays.

**What the new cadence delivers:** Every caterer gets equal prep time regardless of
which day they serve. Monday session → Friday order. Tuesday → Saturday. Wednesday
→ Sunday. Thursday → Monday. System-native instead of human-calendar-derived.

**Consequence for the demo:** The agent runs 5–7 times per week, not once. The
decision log accumulates events across the week in a visible, traceable way.

---

## D6 — Managers are tutors: a reframe that deleted a whole table

**The decision:** Managers are not a separate identity class — they are tutors with
a per-session role flag. Two booleans on the tutor row: is_tutor, is_manager.

**What was cut:** A dedicated managers table, a separate managers endpoint, all the
FK maintenance that would have come with it.

**Why it mattered:** A person can be a manager, a tutor, both, or neither at any
session. Booleans naturally express all four states; a role enum would force awkward
"both" semantics. A dual-role person submits two feedback channels (manager-level
session report + per-kid tutor ratings) and the rolling-mean counts them as two
independent rater perspectives.

**The memo line:** "The cleanest reframe of the entire project — replaced an entity
with a relationship."

---

## D7 — OPT-06: dietary vocabulary unification via junction table

**The decision:** Replace 8 boolean columns on menu_items with a junction table
(menu_item_dietary_tags) using the same dietary_tags vocabulary as enrolment_dietary_tags.

**What was wrong with booleans:** Adding a new dietary requirement required an ALTER
TABLE, a migration, and code changes across every safety check. The boolean approach
was also asymmetric — student requirements lived in structured tags, item properties
lived in raw booleans, creating two different mechanisms with different failure modes.

**The semantic rule introduced:** item is safe for student ⟺ item.tags ⊇ student.tags.
A clean set operation replaces a growing list of boolean ANDs.

**Why extensibility matters:** At Padea's scale, each school year may bring new
enrolments with requirements not seen before. Adding no_sesame is a single INSERT
INTO dietary_tags; the safety logic doesn't change.

---

## D8 — OPT-07: enrolment_session_slots (correctness, not optimisation)

**The decision:** Add a junction table linking enrolments to specific session_slots,
not just schools.

**What was wrong before:** ISHS has three sessions (Mon/Tue/Thu) with separate
student cohorts. Without the junction, the cohort query returned all ISHS enrolments
for any session — tripling the Monday count (36 actual students → 120 returned).

**Why it was caught in the schema review instead of later:** The design pass happened
before tool code was written. If this had survived to integration testing, the order
for ISHS Monday would have listed 120 students' meals for a 36-student session.

**Lesson:** Schema review before tool code pays. This was the most consequential
correctness find of the V4 pass.

---

## D9 — Automation boundaries: autonomous vs. queued-for-approval

**The decision:** Commercial-change emails (warning, RFP, cancellation, rfp_loser_courtesy)
go to queued_for_approval status and never send without one-click operator approval.
Routine emails (session orders, weekly summaries, opt-back-in parent emails) send
autonomously.

**The reasoning:** "The 30-second saving on auto-send doesn't outweigh the
commercial-relationship damage if the tone misfires." Rotation-stakes decisions stay
human-initiated; the system does the data work, the human owns the commercial stakes.

**The competitive RFP framing:** Used rather than serial enquiry because it
parallelises response time and creates implicit pricing pressure without explicit
negotiation. "Out of those who agree we'll pick" is commercial leverage embedded in
the process.

---

## D10 — Zero operational margin: deliberate, not oversight

**The decision:** No walk-up buffer, no tutor buffer, no ML-predicted absence margin.
Order exactly what is known to be needed.

**What was cut:** V1 had ML-predicted absence margins (argued for: training on
absences, weather, exam timetables, sport, term position). Cut because: ~440 sessions
per year divided per-school gives thin training data; 5-10% absence base rate creates
a small ceiling on savings; Thursday cadence breaks forecast horizon; buffer
mechanism self-defeats trust.

**The accepted cost:** Walk-backs (kid marked absent who turns up) receive no meal
that session. The session manager redistributes any surplus from other absences, or
the student misses. One-week friction is the forcing function keeping opt-out as a
real choice.

**The ML residue:** Calendar-aware rules (deterministic attendance effects of
end-of-term, exam fortnight, public holidays) retained. Same outcome, simpler tool.
"When operations scale 5-10x, the rule engine graduates to a learned model with the
rules as the prior."

---

## D11 — Dietary safety wins on all paths: closing the safety hole

**The decision:** item_is_safe_for_enrolment runs on ALL three order-line source
paths (rotation, request, dietary_auto_pick), not only on the dietary_auto_pick path.

**The bug that existed before:** A student with dietary restrictions could receive an
unsafe meal via the rotation path (if their approved set contained a meal that was
somehow unsafe) or via the request path (if a tutor filed a request for a meal
outside the safe set). The safety check was missing on those paths.

**Why it matters:** Safety is the non-negotiable floor. The test that confirmed this
is specifically designed to catch safe=False on a request-source violation. The fix
was structural — dietary safety as a post-selection check on every path, not a
selective check on one path.

---

## D12 — Option C: VO as safety fallback only (not a preference)

**The decision:** VO items are never a preference, never a rotation item, never
visible to non-restricted students. They exist solely as a safety fallback for
vegetarian students when no inherently-vegetarian item exists on the current caterer's
menu.

**What was rejected:** Treating VO as a dietary property of the item (tag the items
as vegetarian). Rejected because: caterers prepare them as meat dishes by default;
the system cannot guarantee a VO meal is correctly prepared unless the caterer is
explicitly instructed; tagging them as vegetarian would allow non-restricted students
to select them via rotation.

**The alternative rejected at memo_material.md:** Splitting VO items into two
menu_items rows (original + auto-generated vegetarian variant). Rejected on safety
grounds — if customisation surfaces ever opened, the variant being a real row meant
non-vegetarian students could select it. The boolean column gates variant generation
to the vegetarian matching path only.

**Safety invariant (locked):** safe=True on VO lines is computed as
item.tags ⊇ (student.tags − {'vegetarian'}), never hardcoded. Any non-vegetarian
dietary gap still fires UNSAFE MATCH. The loop's dietary_safety_violation check
fires if the selection logic ever bugs out and an unsafe VO line appears.

---

---

# PART III: KEY LESSONS

## L1 — Data first, schema second

**What happened:** Designed a 26-table schema before opening the resource files.
When the source data was finally read, a structural MOQ violation was found (Lakehouse
at MBBC, 18 students vs. 25 MOQ). This turns MOQ-shortfall escalation from a
theoretical capability into a guaranteed demo moment.

**The lesson:** "Should have read the data first." The data review revealed real
constraints that the schema needed to model; designing the schema blind meant those
constraints weren't in scope from the start.

**How to apply:** Present this openly. The discovery still improved the demo — the
escalation now has a concrete, repeatable trigger rather than a hypothetical one.
The miss is documented honestly; the memo's Learning criterion rewards this.

---

## L2 — The ML reversal

**What happened:** Proposed training a model on absences, weather, exam timetables,
sport, term position to predict attendance and right-size orders.

**Why it was wrong:** Five reasons specifically identified:
1. Data volume too thin (~440 sessions/year, divided per-school)
2. Base rate too low to act on (5-10% absence → ~$15-30k/year ceiling savings)
3. Thursday cadence breaks the forecast horizon
4. Buffer mechanism self-defeats trust (buffering regularly creates a prediction that
   is always "about right," destroying signal quality)
5. Wrong layer of optimisation (cost is a constraint, not the goal)

**What replaced it:** Calendar-aware deterministic rules for attendance effects that
don't need ML (end-of-term dips, exam fortnight, public holidays).

**The memo framing:** "I considered something ambitious, identified why it was wrong
for this stage, and built the foundation that grows into it later." This is a stronger
Learning-criterion signal than proposing ML without interrogating it.

---

## L3 — The preference capture reversal

**What happened:** Proposed weekly opt-in preference emails to students. Pushed back on.

**Why it was wrong:** Real-world response rates collapse to 20-40% after a few weeks.
More importantly: preferences are durable, meals are variable. Asking the same stable
question weekly replaces one guess with a guess that *feels* informed but isn't.

**What replaced it:** Preferences captured once per term at enrolment as durable data.
Optional weekly customisation surface (the meal request mechanism) for motivated users.
The distinction: durable preferences (parent-captured at term start), one-off requests
(tutor-filed for next session), not weekly re-asks.

**The insight:** "Preferences are durable, meals are variable; the data structure has
to match." The system captures the stable fact once and derives the variable instance
from it.

---

## L4 — The food quality decline reframe

**What happened:** Initially proposed incentives that read as "loss of work for
caterers who decline." Got reframed.

**The correct framing:** The "able to serve" overlap list IS the leverage. Caterers
know there are alternatives. Visible measurement is the discipline mechanism — no
threats needed. "We run a real performance management system" rather than threatening
caterers.

**Why it matters:** The framing change produced a commercially defensible system. A
system that threatens caterers is coercive and legally questionable. A system that
makes alternatives visible and performance measurable achieves the same incentive
structure without coercion.

---

## L5 — The pricing layers conversation

**What happened:** Proposed a separate payments table for per-caterer weekly payments.
Got held to the "derive, don't store" principle that was already established in the
design.

**Why the table was wrong:** Payment is derivable from orders + MOQ rules. It is not
a separate event. Storing it creates a second source of truth that can drift.

**The memo line:** "A 'you held me to my own rules' moment that strengthened the
design." The principle was stated at the start; it was allowed to be used against
its own proposer when the proposal contradicted it.

---

## L6 — The over-engineering vs. deletion tension — the real pivot

**What happened:** The schema reached 26 tables. Two paths: (a) cut hard to 8
bare-bones tables (collapse dietary tags into text, drop operational logging), losing
meaningful capability; or (b) keep the 26-table architecture but build in phases,
applying the deletion test at the phase level rather than the table level.

**The choice:** (b). The value test was applied to whether each table earned its
place at build-phase level. Phase 4's optional tables were deferred to V2 with
reasoning.

**The memo framing:** "I designed 26 entities; I built them against the workflow's
actual demands; deferred tables were deferred with reasoning." Not "I tried to build
26 tables and ran out of time." The distinction matters for the evaluation criterion.

---

## L7 — The V4/V5 cancellation and the time trade-off

**What happened:** The original plan was V1→V5 (ambitious → cut → add back → simplify
→ accelerate). V4 (simplification) and V5 (cycle-time acceleration) were cancelled
under time pressure when the build phase needed to start.

**The honest framing (from memo_material.md):** "I spent from Thursday to Tuesday
working through the hardest part of the task: interpreting a deliberately vague brief,
grounding the requirements in messy source data, building an ambitious first architecture,
stripping it back, and then carefully rebuilding the parts that actually mattered.
By the time V3 was complete, I felt the core design had been tested deeply enough to
start building for heats, even though V4 and V5 were compressed. This was a deliberate
trade-off rather than an oversight: further simplification would have improved the
polish of the system, but delaying implementation further would have put the working
demonstration at risk."

**V4/V5 should be called out explicitly in the memo:** The design reached V3; V4
(which became the V4 optimisations pass on the schema) addressed structural correctness
but not the full simplification pass that was originally planned. V5 was never reached.
The system is not the fastest or most elegant possible version. It is the one that
reflects the most important thinking done.

---

## L8 — The first live run: prompt engineering is not separate from the build

**What happened:** First live agent run (run_id=5) hit the tool call cap at 15/15
without writing any orders. Root cause: system_prompt.md described the internals of
compose_session_order step-by-step. The model followed those instructions literally
instead of calling compose_session_order as a black box.

**The lesson:** The system prompt is part of the build, not documentation. A prompt
that accurately describes what a tool does internally will cause the model to
replicate that logic manually rather than delegating to the tool. The prompt must
describe the intended usage pattern (call compose_session_order directly after the
exclusion check), not the tool's internal mechanics.

**What was confirmed:** The cap logic, urgent logging, and final summary all worked
correctly on a genuine failure run. Infrastructure was solid; the mistake was in the
instructions given to the model, not in the plumbing.

---

## L9 — Schema review before tool code: OPT-07

**What happened:** The V4 optimisations pass caught that enrolments linked to
schools, not session_slots. For multi-session schools (ISHS, LC, CHAC), the cohort
query would have returned all school-level enrolments instead of session-specific ones.

**Why the timing mattered:** Catching this during schema review (before tool code
was written) meant the fix was an ALTER TABLE. Catching it during integration testing
would have meant rewriting every tool that queries enrolments, plus potentially
corrupt orders in the DB.

**The lesson:** Reviewing the schema as a working document (not just as a design
artefact) before building tool code is not extra work — it prevents compounding
mistakes. The V4 optimisations pass was scheduled for this reason, and it earned its
cost.

---

## L10 — Integration tests catch what unit tests cannot

**What happened:** The safety_records integration test (test_safety_records.py Part 2)
ran compose_session_order against the real DB and confirmed the 8-field shape of
safety_records. It caught that the real function returns no "reason" field, while the
mock fixture used one. The reasoning f-strings in the loop's STEP 3c were updated
accordingly.

**Why it mattered:** A mocked unit test that assumed "reason" was present would have
passed. The integration test against the real function's actual return shape failed.
This is the test-design lesson: mock tests verify that the code does what you *think*
the dependency does. Integration tests verify what the dependency *actually* does.

---

---

# PART IV: KEY PROBLEMS OVERCOME

## P1 — Multi-session school cohort correctness (OPT-07)

**The problem:** ISHS, LC, and CHAC each have multiple sessions per week with
separate student cohorts per day. The V3 schema linked enrolments to schools, not
session_slots. This meant the cohort query for any session at ISHS would return all
120 ISHS students instead of the correct 36 for Monday.

**The solution:** enrolment_session_slots junction table with joined_date/left_date
lifecycle, two supporting indexes, and a cohort query that joins through the junction.
One session slot → correct cohort size.

**How it was caught:** V4 schema review pass before tool code was written.

---

## P2 — dietary safety hole: all three source paths

**The problem:** The dietary safety check (item_is_safe_for_enrolment) only ran on
the dietary_auto_pick path. Rotation and request paths were unchecked.

**The solution:** Safety check applied as a post-selection validation on every path.
compose_session_order now returns safety_records for every assigned student, and the
loop logs urgent dietary_safety_violation steps for any safe=False record regardless
of source.

**The test:** scripts/test_compose_session_order.py includes a case that explicitly
proves safe=False is caught on a request-source violation.

---

## P3 — The updated_at staleness bug (OPT-01)

**The problem:** Six tables carried updated_at with DEFAULT now() only. On any
subsequent UPDATE the column froze at insert time, returning stale data to any code
that reads it. Incremental sync patterns, cache invalidation, and audit queries would
all silently read wrong timestamps.

**The solution:** A single shared trigger function (set_updated_at()) attached as
a BEFORE UPDATE trigger to all six affected tables. One function, six triggers,
zero silent failures.

**Why it was silent:** The column looked correct in the schema. The bug was invisible
without an UPDATE test.

---

## P4 — VO handling: vegetarian students with no inherent-safe items

**The problem:** Vegetarian students at a school served by Terrific received
"no safe meal" escalations every week because Terrific's menu has no inherently-
vegetarian items, only VO items (which are meat dishes prepared vegetarian on request).

**The solution (designed, not yet built):** Option C — has_vegetarian_option boolean
on menu_items + variant text column on order_lines + VO fallback in compose_session_order.
Selection chain: inherent-safe → VO fallback → escalate. Safe computed from the
selection condition (item.tags ⊇ student.tags − {'vegetarian'}), not hardcoded.

**The discovery:** Two orders had to run first before the gap surfaced as a live
escalation. The STEP 4 re-run produced the evidence that drove the Option C design.

---

## P5 — Agent prompt causing manual decomposition of a single tool call

**The problem:** The system prompt described compose_session_order's internals
(get_enrolments_for_session, get_exclusions, get_year_level_exclusions, etc.) as if
the model should call each sub-step manually. The model did exactly that.

**The solution:** system_prompt.md rewritten to describe the pipeline in terms of
what the model should call, not what each tool does internally. Forbidden internals
listed explicitly. One session per run.

**The lesson this encodes:** The agent's system prompt is a user interface. The user
of that interface is the model. A prompt that describes what a tool does internally
is giving the model implementation details it doesn't need and will act on literally.

---

## P6 — Geocoding without a geocoding dependency

**The problem:** Distance queries between schools and caterers require geocoordinates.
pgeocode requires a local data file; postcodes APIs add a network call at query time.

**The solution:** 8 known QLD postcodes (all 6 schools + 4 caterers) hardcoded as a
dict of centroid coordinates derived from ABS locality data. geopy geodesic runs
offline. Raises ValueError on any unrecognised postcode so the required extension is
immediately obvious if new locations are added.

**Why this is the correct production plan, not a hack:** The correct long-term fix
is one schema change (add lat, lon to schools and caterers). The dict is the correct
short-term shortcut for a closed set of known postcodes. Both approaches are
documented.

---

## P7 — GST rate historical correctness (OPT-05)

**The problem:** GST rate lived only on caterers, not on orders. Computing the
correct GST for any historical order required joining back to caterers and reading
the current rate — which may have changed since the order was composed.

**The solution:** Snapshot gst_rate_percent onto orders at composition time. The
order row is now a complete self-contained accounting record — cost and the rate
used to compute it are both immutable once the order is sent.

**Why this is standard accounting practice:** Cost is historical fact; the rate at
which it was computed is also historical fact. Storing only the current rate and
deriving from it would produce wrong historical calculations if the rate ever changes.

---

---

# PART V: EDGE CASES NOT OVERCOME

## Unovercome EC1 — Dietary tag history / audit gap

**What it is:** A parent claims Padea served their child food they were allergic to.
The dietary tag was updated three weeks before the incident. The system cannot answer
"what was Sam's dietary tag on March 14th" because dietary tags overwrite in place.

**Why it was accepted:** (a) Kids generally know what they can and can't eat and
self-protect at the point of meal service. (b) The operator-mediated email exchange
initiating the change is itself a record outside the system. (c) The build cost of
a dietary history table for one rare-case dispute doesn't earn its place at V3 scale.

**What would trigger building it:** A real dietary-incident dispute where the
overwrite-in-place model failed to provide the required evidence.

**What the memo should say:** "We accepted a known audit gap on dietary history and
documented it explicitly. The production fix is a dietary_tag_history table; we
chose not to build it because the rare-case value doesn't justify the ongoing
maintenance cost at the current operational scale."

---

## Unovercome EC2 — Tutor-pattern escalation path (no order_lines seeded)

**What it is:** The system supports two escalation arcs for caterer quality decline:
(a) session-level manager ratings (the primary arc, fully demonstrable), and (b)
per-meal tutor feedback attached to order_lines (the secondary arc). order_lines were
not seeded, so the tutor-pattern escalation has no data to fire on and is not shown
in the demo.

**Why it was accepted:** The primary arc (session-level manager ratings detecting
decline → warning → RFP) runs entirely on manager feedback, which was seeded with
an engineered declining trend. The secondary arc adds signal but doesn't change the
primary demo story. Seeding order_lines and the corresponding tutor feedback would
have added build time without strengthening the demo's core narrative.

**What the memo should say:** "We built the schema to support both feedback levels
but seeded only the session-level path. The meal-level path is a contained, additive
extension — the schema accommodates it. The decision was to demonstrate the primary
arc cleanly rather than dilute it with a half-seeded secondary arc."

---

## Unovercome EC3 — Multiple return cycles (enrolment periods)

**What it is:** A student who departs and returns more than once has their
current_period_start_date overwritten on each return. The second departure's start
date is lost as structured data (it lives in the agent_steps audit trail but is not
directly queryable).

**Why it was accepted:** Rare at Padea's current scale. Single departure and return
is handled correctly.

**V4 trigger:** Add an enrolment_periods table storing each (start_date, end_date)
pair per enrolment if multiple returns become routine.

---

## Unovercome EC4 — V4 simplification and V5 acceleration passes

**What they were:** V4 (post-V3 simplification and cycle-time optimisation) and V5
(acceleration, performance tuning) were planned but cancelled under time pressure.

**What was done instead:** A targeted V4 schema optimisations pass (OPT-01 through
OPT-07) addressed structural correctness. The broader simplification and acceleration
work was not done.

**What the memo should say:** "The design philosophy was V1→V5; the execution reached
V3 plus a structural optimisations pass. V4 simplification and V5 acceleration would
have improved the polish and performance of the system, but delaying the build to
complete them would have put the working demonstration at risk. The final system
reflects the most important thinking done, not the most optimised version."

---

## Unovercome EC5 — Gmail credentials / live email

**What it is:** Gmail API credentials (OAuth2) were not obtained during the build
sessions. src/tools/gmail.py does not yet exist. All email functionality is
documented, designed, and architecturally complete, but not wired to real Gmail.

**The impact on the demo:** Email send/receive cannot be demonstrated live. The
outbound_emails table, the email status lifecycle, the address-rewrite demo flag —
all exist in the schema and agent design, but there is no Gmail tool to trigger them.

**What the memo should say:** "Gmail integration is architecturally complete —
the schema, the email type enum, the status lifecycle, the demo-mode address rewrite
flag — but the Gmail OAuth credentials were not obtained during the build window.
This is the last remaining unbuilt component. The demo shows the agent reasoning,
order composition, and database writes; it does not show real email being sent."

---

## Unovercome EC6 — Payment mechanism

**What it is:** V3 models the financial crystallisation moment (Monday 3:30 PM
consolidated summary: GST-normalised, MOQ-floored total per caterer). The actual
payment mechanism (bank transfer, Stripe, accounting software) is explicitly not
modelled.

**Why it was accepted:** The brief does not specify how Padea pays caterers. The
consolidated summary is the canonical spending document; how payment is made is
a layer above what the system needs to model.

**V4 trigger:** Payment integration if operator labour for payment handling becomes
a bottleneck.

---

## Unovercome EC7 — Monday consolidated summary workflow

**What it is:** The Monday 3:30 PM consolidated summary (aggregates the week's
individual orders into one per-caterer summary with MOQ floor and GST applied) is
designed but not yet built in loop.py. The STEP 4 re-run demonstrated per-session
order composition; the Monday summary workflow is the next major build phase.

**Status:** Option C build → Monday consolidated summary workflow, in that order.

---

## Unovercome EC8 — PII, data retention, multi-operator

**What they are:** Three accepted production preconditions that are not modelled:
- PII redaction and data retention policies (required for real deployment with real
  parent data)
- Multiple simultaneous operators (V3 assumes one operator; no conflict resolution
  or role-based access)
- Attendance system integration with schools (Padea runs independently; no sync)

**Why they were accepted:** None are required for the competition demo. All three
have documented V4/production build triggers.

---

---

# PART VI: ASSUMPTIONS THE SYSTEM RELIES ON

## A1 — Tutor and manager training as a system precondition

**What the system assumes:** Tutors understand the 1–5 scale anchoring (5 = perfect,
3 = satisfactory). They probe rather than accept first numbers from kids. They
understand the request mechanism is a one-off override, not a durable preference
change. They lead the preference-reset workflow on caterer-change weeks. Session
managers understand the structured checklist.

**Why this matters:** The entire quality feedback signal depends on raters being
calibrated. An uncalibrated rater who gives 5s for everything destroys the rolling
mean's discriminating power. The system has no normalisation for rater drift in V3
(deferred to V4).

**What the memo should say:** "The system surfaces the data; staff must collect it
well. We chose to build the collection infrastructure and defer rater normalisation
rather than build normalisation without enough data to calibrate it."

---

## A2 — Source data accuracy: prices, dietary flags, postcodes

**What the system assumes:** The source files (caterers.xlsx, caterer-menus.pdf,
students.xlsx) are accurate. Dietary flags on menu items are correctly assigned.
Postcodes are current. Prices reflect what caterers actually charge.

**Known anomaly:** Kenko at $5.50/item (implausibly low vs. Lakehouse at $35/item).
Decision: treat source data as accurate. The ops engineer's job is not to second-guess
inputs. Flagged for Dylan. Documented in data_observations.md.

**The VO decision:** VO items explicitly NOT tagged as vegetarian per Decision D7.
"VO = Vegetarian Option" means prepared on request, not inherently vegetarian. This
assumption drives Option C.

---

## A3 — One operator, operator discipline

**What the system assumes:** A single operator who checks email over weekends (orders
go out Saturday and Sunday), who approves commercial emails before they send, who
sets enrolment end dates when kids leave, who handles mid-term enrolments manually.

**What happens if this fails:** An urgent item sits unhandled; no caterer receives
an approved warning email; a kid who left keeps getting meals ordered for them. The
system fails gracefully (logs urgents, doesn't auto-send commercial messages) but
cannot compensate for persistent operator absence.

**The honest assessment:** "The system trusts operator discipline at every non-routine
decision point. That's appropriate for a single-operator demo; production hardening
would add retry notifications, escalation routing, and role-based access."

---

## A4 — Caterers behave honestly and predictably

**What the system assumes:** Caterers receive and read order emails. They prepare
what was ordered. They reply to order confirmations and RFPs in a timely way.
Price-change notifications arrive via email reply.

**What the system does when this fails:** Unclassified inbound → escalation.
Non-confirmed order → operator handles at T-24hrs check. Last-minute cancellation
→ unclassified inbound, operator handles. None of these are automated recovery
paths; they are human-escalation paths.

---

## A5 — Gmail as the communication layer

**What the system assumes:** A dedicated Gmail account exists. The OAuth token is
renewed weekly (7-day limit on unverified apps). All inbound parent and caterer
communication arrives at that account.

**Known operational quirk:** The 7-day OAuth token expiry means a weekly re-auth on
the dev machine before demo day. Documented explicitly. "Production verification
removes the limit but requires Google's verification process — not worth doing for
the competition."

---

## A6 — Single time zone, stable school calendar

**What the system assumes:** Australia/Brisbane (UTC+10, no DST). All six schools run
on the same term calendar. The T-72hrs trigger is computed from a single reference
time zone.

**DST behaviour:** Queensland does not observe DST, so UTC+10 is stable year-round.
The system wouldn't need to handle DST transitions even in production.

---

---

# PART VII: THINGS EXPLICITLY DOCUMENTED AS MISSING

This section is a compact reference to every gap that was deliberately named and
logged rather than silently skipped. Documenting a miss is better than not —
it shows acknowledged scope management, not ignorance.

| Gap | Where documented | Production trigger |
|---|---|---|
| Dietary tag history | edge_cases.md, memo_material.md | Real dietary-incident dispute |
| Tutor-pattern escalation (no order_lines seed) | CLAUDE.md, memo_material.md | Extend seed + wire tutor-pattern escalation |
| Multiple return cycles | edge_cases.md, v4_summary.md | Add enrolment_periods table when case becomes routine |
| V4 simplification pass | CLAUDE.md, Session 001 | Time allowed it |
| V5 acceleration pass | CLAUDE.md, Session 001 | Time allowed it |
| Gmail credentials | CLAUDE.md build status | Obtain OAuth credentials, implement src/tools/gmail.py |
| Payment mechanism | edge_cases.md, v3_decisions_ledger.md | Payment integration if operator labour becomes bottleneck |
| Monday consolidated summary workflow | CLAUDE.md | Next build phase after Option C |
| Option C (VO fallback) | Session 019, CLAUDE.md | Build in next session |
| PII / data retention | edge_cases.md | Real deployment |
| Multiple operators | edge_cases.md | Team grows |
| Per-rater normalisation | v3_decisions_ledger.md V3-FB-01 notes | 30+ ratings per rater stable |
| Invoice ingestion + variance escalation | v3_decisions_ledger.md V3-OC-01 notes | Caterer invoice volume |
| Cross-school student identity | edge_cases.md | Real cross-school case emerges |
| Menu price history | v3_decisions_ledger.md V3-OC-01 notes | Pricing dispute needs pre-overwrite history |
| Attendance system integration | edge_cases.md | School partnership scope |
| Mid-term enrolment automation | edge_cases.md | Frequency rises above ~5/term |
| Auto-send warning email without approval | v3_decisions_ledger.md V3-FB-01 notes | Commercial risk threshold changes |
| Templates in database | v3_decisions_ledger.md V3-CM-01 notes | Non-engineering operators need to edit copy |
| Production OAuth verification | v3_decisions_ledger.md V3-CM-01 notes | Real deployment |
| Caterer emergency RFP flow | edge_cases.md | Last-minute cancellations become non-rare |

---

---

# PART VIII: WHAT MAKES THE PROBLEM-SOLVING STAND OUT

## S1 — The brief reading as the design anchor

The entire system architecture is a consequence of a correct reading of one line in
the brief. A literal reading would have produced an order-generation script — simpler,
faster, less interesting. The insight that the brief was asking for a satisfaction-loop
system (not just a logistics system) produced every piece of the feedback ecosystem,
the rolling mean, the decline detection, and the caterer rotation chain.

This is the kind of brief-level interpretation that separates a narrow solution from
one that addresses the underlying problem.

---

## S2 — Reversal documentation as a signal of thinking quality

The memo_material.md file contains seven explicit reversals: ML absence prediction,
preference capture cadence, food quality decline framing, pricing table, VO splitting,
tutor meals as a primitive, and the brief reading itself. In each case: a proposal
was made, it was interrogated, it was refined or rejected.

These reversals are more valuable as memo content than the surviving decisions.
Any competent designer can produce a final design. A designer who documents what
they proposed, why it was wrong, and what replaced it is showing their reasoning
process, not just its output. The Learning criterion explicitly rewards rate of
improvement; these reversals are the evidence.

---

## S3 — Process honesty about the V1–V3 arc

The V1–V3 documents are retrospective overlays applied to make the design journey
examinable. The actual chronological work produced something near-V3 in the first
design conversations. This is acknowledged explicitly rather than presented as if
a clean sequential V1→V2→V3 progression happened over three separate periods.

The Learning criterion rewards "honest retelling > polished essay." Acknowledging
the reconstructive nature of the V1–V3 arc is more credible than pretending the
journey was perfectly sequential.

---

## S4 — Every cut has a documented V4 trigger

No feature is silently absent. Every deferred item carries the operational signal
that would justify building it later. This distinguishes active scope management
from passive omission. "We cut this because it doesn't earn its place at V3 scale,
and here is what would tell us to build it" is a stronger design statement than
"we ran out of time."

The edge_cases.md document lists 20+ edge cases with status (handled/out of scope)
and V4 build triggers for every deferred item. This is the design artefact that
demonstrates systematic scope management.

---

## S5 — The architecture is traceable: one decision register, one schema, one code layer

The system has a single authoritative path from requirements to running code:
- requirements_v1.md → what the system must do
- v3_decisions_ledger.md → how each requirement is satisfied (10 decision blocks)
- v4_summary.md → plain-English operational description
- v4_schema.sql → the authoritative database schema
- agent_context/system_prompt.md → the model's instructions
- src/tools/ → the deterministic tool layer the model calls
- src/agent/loop.py → the orchestration layer

A judge can pick any requirement from requirements_v1.md, find it in a decision block,
trace the decision to a schema table, and verify the tool code that implements it.
Traceability across a complex system is a Taste criterion signal.

---

## S6 — Safety is a loop-owned property, not a model-dependent one

The dietary safety logging (STEP 3c in loop.py) fires unconditionally for every
compose_session_order call, regardless of what the model does or does not notice.
The model can write well-reasoned observations; the loop writes the audit record
regardless.

This is the architectural principle that "the system's responsibility to flag dietary
risk cannot be delegated to the reasoning layer." A model that misses a safety flag
in its reasoning doesn't get to suppress the urgent log entry. Safety is a
deterministic, code-owned guarantee, not a probabilistic, model-owned observation.

---

## S7 — The canonical meal order as soft cluster alignment

The popularity-ranked canonical order on caterers is a single stored field per
caterer (JSON list of menu_item_ids), recomputed only at term start and caterer
change. It achieves two things simultaneously: kids with overlapping preferences
tend to land on the same meal in any given week (natural MOQ relief, no explicit
clustering), and widely-liked meals appear early in the sequence (kids cycle through
what they actually want, not random items).

This replaced a V1 proposal for explicit clustering algorithms and MOQ-tier
optimisation at composition time. The same outcome with one stored field and no
runtime computation.

---

## S8 — The shared dietary vocabulary (OPT-06)

The dietary safety check is a single set operation: item.tags ⊇ student.tags.
This works because menu items and student enrolments share the same dietary_tags
vocabulary. There is no "contains X" vs. "is free from X" direction flip; there is
no mixed-direction logic; there is no growing list of boolean ANDs.

Adding a new dietary requirement (say, no_sesame) is one INSERT INTO dietary_tags.
The safety check function does not change. The schema does not change. The tool
layer does not change.

This is the kind of extensibility that comes from designing the vocabulary correctly
at the start, not from retrofitting it later.

---

## S9 — The demo data is real: the MOQ shortfall will fire

The 55 historical orders seeded for Terrific include a declining quality trend
(engineered to trigger the sustained-decline detection). Lakehouse at MBBC genuinely
has 18 students against a 25-meal MOQ. These are not hypothetical demo moments —
they are structural properties of the real source data that guarantee specific
escalation paths will fire when the agent runs.

A demo that shows fabricated data proving a fabricated edge case is not as credible
as a demo where the real data contains the structural properties that cause the
system's mechanisms to trigger naturally.

---

## S10 — Operational reality drives schema

The terminology reversal in memo_material.md — "when proposals led with database
terminology, I couldn't push back effectively. We changed format: operational reality
first, database pattern second" — is the design philosophy that produced the rest
of the work.

Every table in the schema exists to answer an operational question that Padea actually
asks. The entities are: schools, caterers, tutors, students (via enrolments), sessions,
menus, orders, feedback. No table exists to solve a database modelling problem that
doesn't correspond to an operational reality.

---

---

# APPENDIX ANCHORS

Items to include as appendix material if permitted:

1. **docs/v3_reinstatements/v3_decisions_ledger.md** — the 10 decision blocks with
   full reasoning. The most complete design document.

2. **docs/v4_optimised/v4_summary.md** — plain-English system description. Readable
   without technical background.

3. **docs/v3_reinstatements/edge_cases.md** — the full edge case inventory (30+
   entries, handled vs. accepted gap vs. out of scope). Demonstrates systematic
   coverage.

4. **Selected chat history excerpts** — specifically the sessions that contain the
   key reversals (ML, preference capture, food quality framing). These show the
   reasoning process in real time.

5. **CLAUDE.md build status block** — shows the full scope of what was built,
   sequenced, and verified.

6. **docs/v4_optimised/Schema/v4_schema.sql** — the authoritative schema DDL,
   deployed to Supabase. 

---

*End of scaffold. Word limit: none. This document exists to be distilled, not submitted.*
