# Decision Register — Padea Operations Agent

**Purpose:** A record of the operational realities that drove every meaningful schema decision in this design.

Each entry below starts with an observation about how Padea actually runs — something that has to be true in the world for the catering process to work. The design consequence is what falls out of that reality.

This document is the audit trail for the schema in `schema_complete.md`. Where that document describes what the schema is, this one describes why it had to be that way.

**Compiled:** 23 May 2026
**Companion documents:** `schema_complete.md`, `log_2026-05-22_requirements-and-scaffold.md`, `log_2026-05-23_schema-design.md`, `log_2026-05-23_build-phases.md`

---

## How to read this document

Entries are grouped by the area of the system they affect, roughly in the order the decisions were made during design. Each entry has three parts:

1. **The reality** — what's true about how Padea operates that forced the decision.
2. **Design consequence** — what the schema does as a result.
3. **What was rejected** — alternatives that didn't survive contact with the reality, when relevant.

Some decisions cluster (multiple realities pointing to one design choice; one reality forcing multiple design choices). Where that happens, entries cross-reference each other.

---

# Goal-shaping realities

## DR-1: Catering exists to drive student satisfaction, not just to feed students

**Reality:** The task hint says the goal is not just that meals are ordered and delivered. The real purpose of catering at Padea is to keep students happy enough that families re-enrol next term. Re-enrolment is the revenue mechanic; catering is one input to it.

**Design consequence:** The system is designed as a satisfaction loop, not an ordering tool. Feedback is treated as the engine, not a nice-to-have add-on. Per-caterer rolling ratings, rotation triggers, and quality-decline detection are first-class. The schema includes a feedback table family because closing the loop matters more than just sending orders.

**What was rejected:** A simpler ordering-only schema with no feedback layer. Would have shipped faster but would have answered the wrong question.

---

## DR-2: Feedback collection cannot be relied upon to be complete

**Reality:** Padea students are minors. Their parents are busy. Even with the best intentions, response rates on weekly feedback surveys degrade over a term. The satisfaction loop has to keep working even when most feedback never arrives.

**Design consequence:** The system is designed so that the order workflow runs correctly with no feedback at all. Feedback enriches future orders but isn't required for current ones. Caterer rotation can be triggered by any of three independent signals (manager session feedback, tutor self-feedback, term surveys) — partial coverage from one channel is acceptable.

**What was rejected:** A design where feedback drives the ordering algorithm directly (e.g. per-student preference learning that requires per-meal ratings). That design fails the moment response rates dip below 60-70%, which is realistic operational territory.

---

## DR-3: The same catering process problem will recur for sick tutor cover, attendance, hiring, and other ops bottlenecks

**Reality:** Padea is hiring an Operations Engineer to fix bottlenecks plural, not just catering. Dylan already demoed a sick-tutor-replacement agent. Any system built for catering will be one of several agentic modules sharing data about students, sessions, schools, and tutors.

**Design consequence:** The schema is built as a general tutoring operations database with catering as one set of tables sitting on top. Operational tables (`agent_runs`, `decision_logs`, `escalations`, `incoming_emails`) are explicitly module-agnostic — designed to support any agent activity, not just catering. Tools and ingest interpretations are documented so future modules read the same contract.

**What was rejected:** A catering-specific schema with catering-shaped logging and catering-specific tools. Would have been simpler for this competition but would have forced rework when the next module gets built.

---

# Entity realities

## DR-4: Students attend specific sessions, not just "their school"

**Reality:** A student enrolled at ISHS doesn't automatically attend every ISHS session. They might be enrolled for Monday but not Tuesday. They might be enrolled in different sessions for different subjects. They might move schools mid-term but retain access to a specific session for continuity.

**Design consequence:** Students have no school FK. The school relationship is captured through enrolments — each enrolment row links a student to a specific session over a date range. School is derived through enrolments → sessions → schools. Enrolments are explicit (their own table), not collapsed into students.

**What was rejected:** A simpler design with `students.school_id` directly. Would have made queries faster but couldn't represent students attending some sessions at a school but not others. Also couldn't represent mid-term school changes without losing history.

---

## DR-5: Students sometimes share names

**Reality:** In a dataset of ~290 students across 6 schools, name collisions are real. "Noah Hall" appears at both ISHS-Thursday and CHAC-Monday. Almost certainly different humans. Could occasionally be the same human in a transfer scenario.

**Design consequence:** Every student gets an auto-incrementing integer `student_id` generated at ingest. Names are descriptive fields, not identifiers. The ingest default rule is: same name at different schools = different students unless explicit evidence proves otherwise.

**What was rejected:** Composed keys using name + school. Brittle if students change schools or year levels.

---

## DR-6: Year level changes term to term, and is contextual to a time period

**Reality:** A student is in Year 11 at the start of one term and Year 12 at the start of the next. A year-level exclusion ("Year 12s on exam block this Tuesday") needs to know the student's year level *at the time of the exclusion*, not their current year level.

**Design consequence:** Year level lives on `enrolments`, not on `students`. Each enrolment captures the year level for that period. When a student moves up a year, the old enrolment ends and a new one starts with the updated year.

**What was rejected:** Year level as a column on `students`. Would have made year-level exclusions ambiguous and required overwrites that destroy historical data.

---

## DR-7: Managers are tutors with extra responsibility on specific sessions

**Reality:** A "manager" isn't a separate kind of person. It's a role assigned to a tutor on a specific session. The same person — Jessie — might tutor on Monday and manage on Tuesday. Managers can change at the last minute when someone's away.

**Design consequence:** No separate `managers` table. The session row carries `expected_manager_id` and `actual_manager_id` columns, both pointing to `tutors`. Other tutors working the session live in the `session_tutor_assignments` junction.

**What was rejected:** A managers table with its own identity. Would have duplicated tutor data and required maintaining parallel records when the same person plays both roles.

---

## DR-8: The expected manager and actual manager are sometimes different

**Reality:** Most sessions go as planned. Occasionally someone is sick or covering for someone else. Caterer logistics need to know who'll be there ahead of time; analysis after the fact needs to know who actually was there.

**Design consequence:** Two separate manager fields on sessions, `expected_manager_id` (set ahead of time) and `actual_manager_id` (confirmed from the post-session app data). Pre-session communications use expected. Post-session analysis uses actual. The difference between them captures cover events without needing a separate absence-of-manager table.

**What was rejected:** A single manager field that gets overwritten when reality diverges from plan. Destroys evidence of the change.

---

## DR-9: Tutors and students can share dietary restrictions, conceptually

**Reality:** "Vegetarian" means the same thing whether the person is a student or a tutor. Same for "Nut Free", "Halal", and the other dietary tags. The vocabulary is universal.

**Design consequence:** One shared `dietary_tags` table. Two junction tables (`student_dietary_tags` and `tutor_dietary_tags`) point into the same vocabulary. Adding a new tag adds one row to `dietary_tags` and immediately applies to both populations.

**What was rejected:** Separate dietary vocabularies for students and tutors. Would have created drift over time and made cross-cohort queries impossible.

---

## DR-10: Dietary requirements are not free text in operation, even if they look that way on paper

**Reality:** Source data shows dietary requirements as free text strings like "Nut Free, No Shellfish, Opted out of Catering". For the system to enforce dietary safety, these strings must be parsed into a controlled vocabulary. A vegetarian student matched to a meal because a typo in the vocabulary made the system fail to catch the conflict is a real risk.

**Design consequence:** Dietary tags are a controlled vocabulary in `dietary_tags`. Ingest parses source strings into vocabulary tokens with documented mappings. Junction tables enforce that only existing tags can be assigned to students or menu items.

**What was rejected:** Dietary requirements stored as comma-separated text on the student row. Would have allowed typos to silently disable safety matching.

---

## DR-11: Opt-out from catering is operationally different from a dietary restriction

**Reality:** A student who opts out of catering doesn't get a meal at all. A student with a dietary restriction gets a meal that fits the restriction. These are different facts. An opted-out student might also have dietary tags (in case they un-opt-out later), but the opt-out always takes precedence in ordering logic.

**Design consequence:** `enrolments.opted_out` is a boolean column, separate from the dietary tags junction. Opt-out is per-enrolment (so a student can opt out at one school but stay in at another, and term-to-term flips are clean), not per-student.

**What was rejected:** Treating opt-out as a dietary tag. Would have conflated two unrelated facts and made the ordering logic muddier.

---

# Menu and caterer realities

## DR-12: "Vegetarian Option" on a menu means the caterer can swap a non-veg item for a veg version, not that the item itself is vegetarian

**Reality:** Lakehouse's menu lists "Chicken/Bacon/Avo Wrap" with a "VO" tag. The chicken-and-bacon wrap is not vegetarian. The caterer will prepare a vegetarian version on request. This is a capability of the item, not a property of it.

**Design consequence:** `menu_items.vegetarian_swap_available` is a boolean column. When matching vegetarian students to menu items, the agent matches items tagged `vegetarian` OR items with the swap flag set. Order lines record both the original `menu_item_id` and an `is_vegetarian_variant` flag for unambiguous caterer instruction.

**What was rejected:** Treating VO as a dietary tag (`vegetarian`) on the source item. Would have caused vegetarian students to be assigned chicken-and-bacon wraps because "the system saw it was vegetarian-tagged."

---

## DR-13: All non-pork meals at our caterers are halal

**Reality:** Source menu PDF states this as a rule applicable to all listed caterers. The operational fact is pork-presence; halal-eligibility is the absence of pork.

**Design consequence:** The dietary vocabulary includes `contains_pork`. Items with pork, bacon, or ham in the name get this tag at ingest. Halal-eligible matching is done as an exclusion query: "items NOT tagged `contains_pork`."

**What was rejected:** A direct `halal` tag on every halal-eligible menu item. Would have required tagging 8-9 of every 10 items at ingest and would have failed in the future if more nuanced halal certification became required (the current model can extend to a `halal_certified` tag for stricter cases without losing the existing logic).

---

## DR-14: Caterers change their menus over time

**Reality:** Restaurants add seasonal items, drop unpopular ones, change prices, retire dishes. Past orders need to reference what the menu looked like *at the time*, not what it looks like now.

**Design consequence:** `menu_items` have `effective_from` and `effective_to` dates. When a caterer changes their menu, the old item gets an end date and a new row is created. Past order lines reference accurate menu state.

**What was rejected:** Mutating menu items in place. Would have rewritten history every time a caterer updated their menu — making cost analysis, popularity tracking, and rotation decisions unreliable.

---

## DR-15: Caterer pricing has three layers: rules, snapshots, and actual paid amounts

**Reality:** When the agent generates an order, it uses the caterer's current pricing rules. When the order is sent, the prices quoted are locked in. When the invoice arrives, the actual amounts may differ slightly (price changes, refunds, surcharges).

**Design consequence:** Three places store financial information. `menu_items.base_price` and `caterers.delivery_fee` are Layer 1 (current rules). `order_lines.unit_price_at_order_time` is Layer 2 (snapshot at order time). `orders.actual_paid_cost` is Layer 3 (actual). Layer 3 is fabricated for the demo to show variance tracking; in production it would be populated from invoices.

**What was rejected:** Storing only the current price and recomputing order costs on the fly. Would have made past order analysis incorrect any time prices changed.

---

## DR-16: Caterer "minimum order quantity" is per-caterer-per-week, varying by menu variety

**Reality:** The MOQ note in the source data says order quantity is "total number of ordered meals for the week across all schools" and scales with menu variety — order 4 menu items, low MOQ; order 6 items, higher MOQ. This is a contractual commitment, not a recommendation.

**Design consequence:** `caterer_moq_rules` is its own small table with one row per (caterer × menu_variety_count) pair. Twelve rows total for our four caterers. The agent queries this when constructing orders and aggregates weekly totals across orders to verify MOQ is met.

**What was rejected:** Fixed columns on `caterers` like `moq_at_4_items`, `moq_at_5_items`, `moq_at_6_items`. Wouldn't have extended cleanly to caterers with different variety levels.

---

## DR-17: Each caterer can only serve one school per day

**Reality:** A caterer's kitchen produces meals in a specific timeframe; their driver delivers them; the operation can't be physically in two places at once during dinner. We have no caterer in our data with multiple delivery vehicles. The simplest reading of the operational constraint covers every case.

**Design consequence:** Not a column in the schema. Enforced in agent order-generation logic: for each caterer being assigned, check whether they're already assigned to a session on the same date. If yes, reject the assignment and surface alternatives.

**What was rejected:** A 30-minute-window time-overlap calculation. More precise but more brittle, and doesn't reflect how kitchens actually plan their day.

---

## DR-18: Caterer capability is conditional on the conditions when it was granted

**Reality:** Lakehouse said "yes" to serving MBBC at the current enrolment size and current dinner time. If MBBC doubles in size or shifts dinner to two hours earlier, that "yes" might not still apply. Capability is a commitment, not a permanent fact.

**Design consequence:** `caterer_school_capabilities` includes `effective_from`, `effective_to`, and `day_of_week`. When operating conditions change significantly (enrolment growth, schedule shift, MOQ pressure), an escalation is generated rather than the capability silently continuing.

**What was rejected:** A simple "can serve" boolean. Would have masked situations where the original capability commitment was no longer realistic.

---

## DR-19: A caterer can serve a school on some days but not others

**Reality:** The capability matrix in the source data shows that current "serves" relationships are day-specific. If MBBC adds a Wednesday session and Lakehouse currently only serves them on Tuesdays, Lakehouse hasn't agreed to Wednesdays — that's a new conversation.

**Design consequence:** The capability matrix is keyed on (caterer × school × day_of_week), not just (caterer × school). One row per day a caterer can serve a school. Adding a new session day requires explicit new capability rows.

**What was rejected:** Caterer capability at the (caterer × school) level only. Would have caused the system to silently assume day-agnostic capability and route orders to caterers on days they hadn't committed to.

---

## DR-20: Some caterer contacts want to be CC'd, others explicitly don't

**Reality:** The source data is explicit: Medium Giraffe at GYG wants to be cc'd on order emails. James Chern at Terrific explicitly doesn't. Both are chefs. CC preference is a per-person preference, not a per-role rule.

**Design consequence:** Four orthogonal booleans on each contact: `is_order_taker`, `is_chef`, `is_primary_contact`, `cc_on_orders`. Any combination is valid. Adding a new contact who plays a new combination of roles requires no schema change.

**What was rejected:** A single `role` column with values like "orders_only", "chef_only", "orders_and_chef", "primary_orders_with_cc_chef". Would have created a proliferation of role names and required schema changes for new combinations.

---

# Order workflow realities

## DR-21: Caterers receive one delivery per session, not per week

**Reality:** Even when a caterer serves multiple sessions for the same school in the same week (Kenko at ISHS Mon/Tue/Thu), each session is its own delivery event with its own driver run, its own setup, its own dinner break. The caterer plans cook and delivery per occurrence, not per week.

**Design consequence:** Orders are per-session, not per-week. One row in `orders` per (caterer × session). One email per order. Weekly aggregates (for MOQ verification, cost reporting) are queries over orders, not stored as a separate weekly table.

**What was rejected:** One order per (caterer × week). Would have collapsed multi-session weeks into a single record, making per-session cancellations and rotation decisions awkward.

---

## DR-22: Each meal has a name on it for safety and accountability

**Reality:** Dietary mistakes can be dangerous. A vegetarian student receiving a chicken wrap because the labels got swapped is a real risk. Per-student labelling means the wrong box can't go to the wrong student. It also speeds up on-site handout and ties feedback to specific meals.

**Design consequence:** `order_lines` represent one meal for one specific student (or one buffer/contingency meal). Each line has a nullable `student_id`. The caterer-facing manifest is organised per-session per-student. Order line count equals meal count — no `quantity` column.

**What was rejected:** Aggregated lines with quantities ("20 Korean Beef Bulgogi for ISHS Monday"). Cheaper in row count but lost per-meal traceability for safety, feedback, and absence handling.

---

## DR-23: Orders are sent three days before the session, not on a fixed weekday

**Reality:** Caterers need lead time to procure ingredients, plan kitchen capacity, and schedule drivers. Three days is the minimum demonstrated by the current Thursday-as-order-day operation for the earliest Monday session. Sending on a single weekday (the way a human coordinator does) doesn't reflect what's actually required — it reflects how a tired human keeps their week organised.

**Design consequence:** Orders are generated and sent three days before each session's start time. The order send day varies by session date but is consistent per session. The hybrid agent cadence runs daily and decides which orders need to be generated each day.

**What was rejected:** Thursday-as-order-day, inherited from the human process. Would have packed the agent's work into one day of the week and given the latest session of the week far more lead time than the earliest.

---

## DR-24: Tutors need consistent meals as part of their role, not as leftovers

**Reality:** Tutors are central to Padea's product. Their working conditions affect retention, hiring, and quality. A consistent tutor meal alongside students improves the role and reduces the awkward "what do we do with extras" judgement that managers currently make. It also creates a clean operational primitive for absence absorption.

**Design consequence:** Tutor meals are first-class buffer lines in every order, sourced from a "common, broadly-appealing" menu pool. Not preference-matched per tutor — the buffer needs to be flexible enough to absorb walk-ups too.

**What was rejected:** Tutors eating leftover student meals. Inconsistent for tutors, undignified, and creates a perverse incentive to over-order. Or buffer meals matched to per-tutor preferences — which would prevent buffer flexibility for walk-ups.

---

## DR-25: A small contingency buffer of meals at every session pays for itself

**Reality:** Walk-up students happen. Tutors occasionally bring a parent or sibling. A manager hands a meal to someone unexpectedly. A small contingency (two meals per session) absorbs these without becoming wasteful.

**Design consequence:** Each session order includes two `contingency` line types beyond the per-tutor and per-student meals. Contingency lines are unlabelled common meals. The `line_purpose` column on order_lines distinguishes student/tutor/contingency for reporting and analysis.

**What was rejected:** No contingency. Cheaper per session but creates "we ran out" failures that damage the experience. Or larger contingency. Wasteful at the per-week level.

---

## DR-26: Year-level cancellations within a session still produce some walk-up students

**Reality:** When a school sends a bloc statement ("Year 12 is on exam block, Year 10 is at camp"), most of those students don't come. But some always do — a kid who skipped the camp, a student who didn't get the message. They show up to a session that's still running for other year levels and expect food.

**Design consequence:** Partial exclusions trigger a 10% attendance buffer added to the order (rounded up to whole meals). The 10% is a sized-to-social-reality estimate, not measured. It lives in agent code, not as a configurable column on schools (those refinements are v2).

**What was rejected:** No exclusion buffer. Walked-up students from excluded cohorts would have no meal. Or a configurable per-school exclusion rate, which has no data to support a non-default value in v1.

---

# Absence and exclusion realities

## DR-27: The Thursday-style order cadence creates a known leak: late absences can't be retracted

**Reality:** Parents email absences when they remember. Some arrive a week early; some arrive the morning of the session. Once the order has been sent to the caterer (3 days before session start), the meal is committed. The caterer cooks; we pay.

**Design consequence:** Pre-send vs post-send is computed at query time from `absences.received_at` against `orders.sent_at`. Pre-send absences influence order construction (the meal isn't made). Post-send absences are recorded but don't cancel meals. Late walk-backs (parent reverses an earlier cancellation) are absorbed by the buffer.

**What was rejected:** Pretending we can amend orders after they're sent. Some caterers might accept amendments, but building this assumes a flexibility we can't guarantee, and the operational cost of attempting amendments at the wrong time outweighs the benefit.

---

## DR-28: Dietary-restricted students always get a meal made, even if they cancel

**Reality:** Students and parents pay for the session. A missed meal because of a parent's cancellation that they later regret is a refund request. More importantly, a dietary-restricted student who shows up after cancelling can't substitute from the common-meal buffer — nothing in the buffer matches their restriction.

**Design consequence:** The order construction rule overrides pre-send cancellation for dietary-restricted students. Their meal is made regardless. Recorded in the assumptions list as a deliberate commercial guarantee and walk-up insurance.

**What was rejected:** Treating all cancellations equally. Would have created the failure mode where a vegetarian student turns up after their cancellation reversal and has nothing safe to eat.

---

## DR-29: Absences and exclusions are different events from different sources

**Reality:** An absence is an individual student decision (or a parent decision on their behalf) communicated via email. An exclusion is a school-level decision affecting one or more year levels or the whole session, communicated by school administration. They have different sources, different rates of arrival, different lifecycles.

**Design consequence:** Two separate tables: `absences` and `exclusions`. Both can have `received_at` and a nullable `source_email_id`. Exclusions have a `scope` field (`whole_session` or `year_level`) and a `scope_value` (the year level affected, if applicable). They never get collapsed into a single "non-attendance" table because the operational handling is different.

**What was rejected:** A unified "non-attendance" table on the grounds that "either way, the student isn't there." Would have made querying by source impossible and would have made the year-level partial-exclusion case awkward to model.

---

## DR-30: A whole-session exclusion is the one case where dietary students don't get a meal

**Reality:** If the entire session is cancelled, nobody is physically at the school to receive food. A dietary student turning up to a cancelled session would find a locked building, with or without a meal waiting.

**Design consequence:** Whole-session exclusions prevent any order from being constructed at all, including for dietary-restricted students. This is the one explicit override of the dietary-always-made rule. Documented as a deliberate exception.

**What was rejected:** Treating dietary students consistently across both partial and whole-session exclusions. Would have generated unattended orders for cancelled sessions.

---

## DR-31: Parents reverse absences sometimes

**Reality:** A parent emails to say their child is sick on Tuesday. By Tuesday morning the child feels better and is going. The parent rarely emails again to confirm — they just send the kid. The original absence stops being true. The walked-back case is rare but real.

**Design consequence:** Absences carry a nullable `walked_back_at` timestamp. When a parent emails a reversal, the agent finds the matching absence row and sets the timestamp. The original absence is preserved for audit. If a walk-back gets walked back, a new absence row is created — chained walk-backs are out of scope.

**What was rejected:** A separate `absence_reversals` table. Over-engineered for an event that happens rarely and has no own attributes beyond timing.

---

## DR-32: The same parent emails the same absence multiple times

**Reality:** Anxious parents send confirmations. Some forward the original email back to themselves with an addition. Some resend if they don't get an acknowledgement. The system needs to handle duplicates without creating duplicate database rows or rejecting valid second-thoughts.

**Design consequence:** Absences are written without a unique constraint on `(student_id, session_id)`. Duplicate parent emails write duplicate rows. The agent uses the most recent active absence per (student × session) when reasoning. The source emails are all preserved in `incoming_emails`. Audit trail preserved; reasoning uses latest.

**What was rejected:** A unique constraint that rejects duplicate rows. Would have created edge cases when parents send corrected versions of an earlier absence email (e.g. fixing a date typo).

---

# Feedback realities

## DR-33: Per-student weekly feedback surveys would have low response rates and biased sampling

**Reality:** A weekly "rate every meal" survey to 290 students degrades to 20-40% response rates after a few weeks, with the responders skewing toward the picky and the engaged. Building rotation decisions on that data is unreliable.

**Design consequence:** Feedback is collected via two trusted channels instead. Managers submit one rating per session with structured comments (high signal, comprehensive coverage). Tutors submit per-session self-feedback (anonymous in external aggregates, identified internally for reliability scoring). A periodic term survey to parents and students cross-checks the manager and tutor data.

**What was rejected:** Per-student per-meal weekly surveys. Higher fidelity in theory; degraded in practice. The current model trades direct per-student data for comprehensive coverage.

---

## DR-34: Managers will rate sessions with different baselines depending on personality

**Reality:** Some people rate everything 4-5 unless something goes badly wrong. Others rate strictly. A 4 from a generous rater is different from a 4 from a strict rater. Without compensation, caterer comparisons are confounded by manager personalities.

**Design consequence:** Caterer rolling rating computation includes rater-baseline normalisation. Each manager's historical average is computed; their individual ratings are adjusted relative to that baseline before aggregation. Implemented as a query-time computation, not stored.

**What was rejected:** Treating all ratings as directly comparable. Would have created systematic errors in rotation decisions whenever a high-baseline rater happened to be the only feedback source for a particular caterer.

---

## DR-35: Feedback submitted faster is more reliable

**Reality:** A manager submitting feedback during or just after the session is reporting on direct observation. One submitting the next morning is reporting from memory. One submitting three days later is reporting from vibes.

**Design consequence:** Feedback weighting includes a submission-timing factor. The `submitted_at` timestamp is compared to `sessions.session_end` at query time to compute delay. Faster submissions get higher weight.

**What was rejected:** Treating all feedback equally regardless of timing. Or rejecting late feedback entirely. The decay function preserves data while discounting it appropriately.

---

## DR-36: Walk-up students who aren't enrolled are a safety and insurance issue

**Reality:** If a student turns up at a session and isn't on the enrolment list, they shouldn't be there. They might be an outsider, a transferred student whose paperwork hasn't been processed, or a student from a different school. Either way it's an immediate issue.

**Design consequence:** Walk-up events with no matching student record trigger an immediate escalation. Walk-up events matching a student marked absent are tracked separately — a second such event for the same student triggers a parent-call escalation about attendance communication.

**What was rejected:** Treating walk-ups as a quiet operational note. Would have left a real attendance-integrity issue unsurfaced.

---

# Operational realities

## DR-37: The agent will make decisions wrong sometimes; humans need an audit trail

**Reality:** Every agent run involves judgement calls — which meal to pick, when to escalate, how to interpret an ambiguous email. Some of those calls will be wrong. To trust the system, humans need to be able to look at what the agent did and reconstruct why.

**Design consequence:** Every meaningful agent decision generates a row in `decision_logs`. Branch decisions include reasoning text. Tool calls log inputs and output summaries. Decision trees support nested reasoning via `parent_decision_id`. The HTML decision log is a first-class demo surface.

**What was rejected:** Logging only errors. Would have made successes invisible — but the question "why did the agent pick this caterer over that one" matters as much as "why did the agent fail."

---

## DR-38: Dylan can't be paged about everything

**Reality:** Dylan runs a tutoring business. Escalating every minor ambiguity to him would make the agent worse than useless. But silently making bad calls would erode trust faster than a few annoying notifications.

**Design consequence:** Escalations have severity (`info`, `warn`, `urgent`), set per instance by the agent. The agent uses the severity to decide whether to email immediately, batch with other escalations, or just log. Auto-resolvable escalations close themselves when the trigger condition is gone, without involving Dylan.

**What was rejected:** A flat "alert Dylan" mechanism for everything ambiguous. Would have created notification fatigue and trained Dylan to ignore the system.

---

## DR-39: The same escalation trigger fires multiple times; humans shouldn't be paged twice for the same issue

**Reality:** MOQ shortfall for the same caterer-week is the same issue every time the agent runs that week. Sending Dylan a fresh email every time would be noise.

**Design consequence:** Each escalation carries a `match_key` computed by the agent using a code-side convention per type (e.g. `moq_shortfall:caterer_5:week_2026-05-25`). Before creating a new escalation, the agent checks for open escalations with the same key. If found, `last_observed_at` updates instead of a new row.

**What was rejected:** Database-enforced uniqueness on `(escalation_type, match_key)`. Too rigid — sometimes the same logical event is genuinely a new occurrence (e.g. an MOQ shortfall in a new week with the same caterer).

---

## DR-40: Escalations close in two different ways depending on type

**Reality:** Some escalations close themselves when the underlying issue is resolved (e.g. enrolment exceeded MOQ → MOQ now met). Others need a human to actively close them (e.g. caterer rotation approval → Dylan replies yes or no). The closing mechanism is different.

**Design consequence:** Escalations have a `resolution_mode` field (`auto` or `human`). The agent re-evaluates open auto-mode escalations every run and closes any whose triggering condition is gone. Human-mode escalations stay open until Dylan replies — identified by a `[PADEA-ESC-{id}]` subject token, with fuzzy matching on subject+sender+timestamp as fallback.

**What was rejected:** A single closing mechanism for all escalations. Would have either left auto-resolvable issues open unnecessarily or made Dylan manually close things that should self-clear.

---

## DR-41: Drafted-action escalations are the same lifecycle as informational ones

**Reality:** Some escalations carry a proposed action with them — "I want to swap CHAC's caterer to Lakehouse; here's the draft email to both caterers; should I send?" The lifecycle is still open → resolved/dismissed. The only difference is that Dylan's reply approves or rejects the drafted action.

**Design consequence:** No special "awaiting approval" state. The escalation body carries the drafted action content; Dylan's reply (`approved` or `dismissed`) closes the row and the agent acts (or doesn't) based on which keyword the reply contained.

**What was rejected:** A separate approval workflow with its own states. Same data, fewer states, cleaner model.

---

## DR-42: Agent runs sometimes crash, and the next run needs to know

**Reality:** A crashed run leaves a row in `agent_runs` with `status = 'running'` and no `finished_at`. If we relied on the running agent to clean up after itself, crashes would leave orphaned rows. We can't run a separate watchdog process for v1.

**Design consequence:** Every new agent run checks for `running` rows older than 30 minutes at startup and marks them `crashed`. No external watchdog needed. Trade-off: if the agent runs more than once every 30 minutes, the threshold needs adjusting; if it runs less often, crashed runs sit visible for longer.

**What was rejected:** A separate watchdog process. Out of scope for v1; adds operational complexity.

---

# Email and intake realities

## DR-43: Every email arriving at Padea is potentially operational input

**Reality:** Parent absence notifications, school exclusion announcements, caterer replies, Dylan's escalation responses — all of these arrive as emails. Treating them as a stream of structured events is what makes the agent autonomous.

**Design consequence:** `incoming_emails` is a first-class event log. Every email landing in `emails/incoming/` (simulated in v1) gets a row. Classification is a separate step (the first-pass classifier writes to the `classification` column). Processing is a separate step (downstream tables like `absences` and `exclusions` reference the source email via FK).

**What was rejected:** Treating emails as ephemeral input parsed and discarded. Would have made re-parsing impossible when classification logic improved.

---

## DR-44: Email classification can be wrong, and the system needs a path for that

**Reality:** A parent emailing about an absence might phrase it ambiguously. A school admin might send a message that looks like an exclusion but isn't. A caterer's reply might be classified wrong. The system can't assume classification is always correct.

**Design consequence:** `incoming_emails.classification` can be set to `unclassified`. The `processing_status` field tracks whether the email has been acted on. Unclassified emails generate escalations for human review. Re-classification is possible (the field is mutable for this purpose).

**What was rejected:** Treating classification as final. Would have meant every misclassification became a silent bug.

---

## DR-45: Outbound emails are sent by the agent's action layer, not the data layer

**Reality:** When the agent sends an order email, an escalation notification, or a reply, the email gets written to `emails/outgoing/` and dispatched. Storing every outbound email in a database table competes with the file-based simulated I/O and adds operational complexity without benefit for v1.

**Design consequence:** No `outgoing_emails` table in v1. Outbound emails live as files. If the system later needs an audit trail of outbound communication, the table gets added with the action layer. The data layer doesn't yet need it.

**What was rejected:** A symmetric `outgoing_emails` table mirroring `incoming_emails`. Would have been pleasingly symmetric but unused in v1.

---

# Cost and payment realities

## DR-46: Catering invoices arrive weekly, not per order

**Reality:** Caterers don't invoice per delivery. They invoice weekly for the total committed. Our per-session orders need to roll up into a weekly view for invoicing.

**Design consequence:** Weekly per-caterer totals are computed as queries over `orders`, not stored. The Monday EOD payment workflow runs the query, compares against MOQ rules, computes `max(committed_total, MOQ_floor)`, and outputs the payment due figure. If MOQ shortfall is detected, an escalation requests extras at the week's final session.

**What was rejected:** A `payments` table storing weekly per-caterer payment records. Duplicates information already derivable from `orders` + `caterer_moq_rules`. Recording that payment actually happened (post-banking integration) is a v2 concern.

---

## DR-47: Actual paid amounts sometimes differ from quoted amounts

**Reality:** Invoices occasionally include adjustments — a missing meal refund, a late surcharge, a small price update. The system needs to be able to record variance between Layer 2 (quoted) and Layer 3 (actual).

**Design consequence:** `orders.actual_paid_cost` is a nullable column populated when the invoice arrives. For v1 demo, this gets fabricated data near the end of build to demonstrate variance tracking. In production it would come from invoice intake (a v2 capability).

**What was rejected:** No actual-paid tracking. Would have given up on a real operational signal that distinguishes a working ops system from a forecasting tool.

---

# Architectural principles

## DR-48: Record events, derive state

**Reality:** When the question "what was Lakehouse's rating in week 3" comes up, the answer needs to be reconstructable from the data we have. If we'd stored only "current rating" and updated it weekly, we'd have lost the historical record forever.

**Design consequence:** The default design principle is event-storing. Every meaningful operational event has its own row with timestamps. Current state (current rating, current caterer, current absence count) is derived on demand, not stored. Documented exceptions where derivation cost is real: `feedback_extracted_signals` (LLM-cost cache), `escalations.state` (lifecycle by nature), `escalations.last_observed_at` (mutable for dedup).

**What was rejected:** Storing current-state columns on entities for query convenience. Faster queries but destroys history. Adopted as a hard default with documented exceptions.

---

## DR-49: Ingest interpretations are first-class documented decisions

**Reality:** The source data is messy. Every ingest decision (how to parse "Nut Free, No Shellfish, Opted out of Catering", whether two students with the same name are the same person, how to determine if a menu item is halal-eligible) is an interpretation we made. Without documentation, those interpretations are invisible bugs waiting to confuse future maintenance.

**Design consequence:** Every interpretation is documented in three places: code comments at the ingest site, schema notes, and the running assumptions list (61 entries). The assumptions list becomes memo material in its own right.

**What was rejected:** Treating ingest as a mechanical translation. Would have left interpretations as silent assumptions, impossible to audit or revisit.

---

## DR-50: The schema serves multiple agents, not just catering

**Reality:** Dylan is hiring for ops engineering broadly. The catering agent is one of several agents that will share data about students, sessions, schools, and tutors. The agent operational tables (`agent_runs`, `decision_logs`, `escalations`, `incoming_emails`) need to support any agent, not just catering.

**Design consequence:** Operational tables are module-agnostic. `agent_runs.intended_purpose` is text, taking any agent's purpose label. `escalations.escalation_type` is an open enum that can grow with new agent types. `decision_logs` doesn't presume catering — it logs any agent's reasoning.

**What was rejected:** A catering-shaped operational layer with `agent_runs.purpose` constrained to catering values. Would have forced rework when the next agent comes online.

---

## DR-51: Forward references are noted explicitly during design

**Reality:** Tables get designed in an order that doesn't always match their dependency order. The feedback design references walkup_events, which references escalations, which weren't designed until later. Without explicit tracking, forward references can be lost.

**Design consequence:** Three forward references existed during design: `absences.source_email_id`, `exclusions.source_email_id`, `walkup_events.escalation_id`. Each was declared with a TBD note when first written and resolved when the referenced table was designed. The schema doc tracks them in the "Conventions used throughout" section.

**What was rejected:** Designing tables strictly in dependency order. Would have prevented the natural flow of design conversation (start with what's familiar, build outward).

---

## DR-52: Some data is captured but deliberately not built into v1

**Reality:** A working v1 demo doesn't need to handle every operational eventuality. Feedback comment extraction via LLM, walk-up reconciliation as a first-class table, end-of-term parent and student surveys — all are designed but the v1 build doesn't need them yet. The architecture supports them; the implementation doesn't ship them.

**Design consequence:** Build phase plan documents which tables are built fully, which are stubbed, which are infrastructure-only, and which are deferred to v2. The memo's deletion story is "I designed 26 entities, built X, stubbed Y, deferred Z, here's why each."

**What was rejected:** Building every designed entity. Or pruning the schema design to v1-only entities. Neither preserves the deliberate v1/v2 split that the build needs.

---

*End of decision register. This is the audit trail for the schema in `schema_complete.md` and the design captured across the day logs. Every decision recorded here was made in dialogue during design — this document is the consolidated retrospective view.*

*Decisions are intentionally framed reality-first. Where multiple realities point to the same design consequence, the consequence appears once and cross-references the realities. Where one reality forces multiple design consequences, the reality appears once and the consequences appear in their own entries with backward references.*

*This document does not replace `schema_complete.md`. The schema doc says what the schema is; this doc says why it had to be that way.*
