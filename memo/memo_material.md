# Memo Material — Working File

**Purpose:** Append-only stream of moments worth remembering for the final memo.
Each entry is dated. Raw thinking, not polished. The memo gets distilled from this on submission week.

**Note:** Honest retelling > polished essay. Capture friction, dead ends, surprises,
near-misses. These are more valuable than triumphs.

---

## 2026-05-25

**Initial framing was schema-first, not requirements-first.** Spent ~20 hours with another Claude instance designing the schema through conversation, then later realised the assumptions and decisions implicit in those conversations needed to be extracted into structured docs. The order documents are presented in is not the order they were produced in. Capturing this because it's the kind of process-honesty the memo's Learning criterion rewards.

**Realised mid-build that data review came too late.** Designed a 26-table schema before opening the resource files. When I finally read them I found a structural MOQ violation (Lakehouse at MBBC, 18 students vs 25 MOQ at 6 items) that turns the MOQ-shortfall escalation from a theoretical capability into a guaranteed demo moment. Should have read the data first. Lesson learned.

**Pricing anomaly noticed, deliberately not corrected.** Kenko at $5.50/item, Lakehouse at $35/item. Real-world plausibility check says Kenko is implausibly low. Chose to treat source data as accurate because the ops engineer's job is not to second-guess inputs. Flagged for Dylan, documented in data_observations.md.

**Cut tutor-meals-as-primitive after considering it seriously.** Argued for tutor meals as a first-class operational primitive — would have removed manager judgement on leftovers and improved tutor working conditions. Cut because Padea didn't ask for it and it changes the business model rather than fixing operations. Contingency buffer (2 meals per session) absorbs the operational need without inventing entitlements.

---

## [next date]

...

## 2026-05-25 — Memo seeds extracted from full_context review

**The hint was the design anchor.** The brief contains one line — *"the goal of this system is not just that meals are ordered and delivered each week"* — that determined everything downstream. A literal reading would have produced an order-generation script; reading the hint produced a satisfaction-loop system. The memo's opening should not be the deliverables, but the moment of recognising what the brief was actually asking for.

**The ML reversal.** I proposed training a model on absences, weather, exam timetables, sport, term position. Was talked through five specific reasons it was wrong for v1 — data volume too thin (~440 sessions/year divided per-school), base rate too low to act on (5-10% absence → ~$15-30k/year ceiling savings), Thursday cadence breaks forecast horizon, buffer mechanism self-defeats trust, wrong layer of optimisation (cost is constraint, not goal). I refined to *calendar-aware rules*: deterministic effects on attendance (end-of-term, exam fortnight, public holidays) that don't need ML. Same outcome, simpler tool. Memo framing: *"When operations scale 5-10x, the rule engine graduates to a learned model with the rules as the prior."* Sharpest demonstration that "I considered something ambitious, identified why it was wrong for this stage, and built the foundation that grows into it later."

**The food quality decline reframe.** I initially proposed *incentives to uphold standards, such as loss of work* — and asked whether this was legally OK. Got reframed: the underlying lever (rotation) is legitimate, but the framing reads as coercive. Final approach: *"the 'able to serve' overlap list IS the leverage. Caterers know there are alternatives. Visible measurement is the discipline mechanism — no threats needed."* Memo line: "we run a real performance management system" rather than threatening caterers.

**The preference capture reversal.** I proposed weekly opt-in preference emails to students. Got pushed back: real-world response rates collapse to 20-40% after a few weeks. Worse — asks the same person the same stable question every week. Replaces one guess with a guess that *feels* informed but isn't. Landed on: preferences captured *once per term at enrolment* as durable data, opt-in weekly customisation surface for motivated users only. Insight: *preferences are durable, meals are variable; the data structure has to match.*

**The VO handling reversal.** I argued for splitting VO items into two menu_items rows (original chicken + auto-generated veggie variant) so matching stayed pure. Pushed back on safety grounds — if customisation surfaces ever opened up, the variant being a real row meant non-vegetarian students could select it. The boolean column kept the variant generation gated to vegetarian matching only. Same outcome at first glance, safer design.

**The "managers are tutors" reframe.** Mid-conversation realisation: managers aren't a separate population, they're tutors with a per-session role. Killed a whole `managers` table. Cleanest reframe of the entire project — replaced an entity with a relationship.

**The pricing layers conversation.** I proposed a separate `payments` table for per-caterer weekly payments. Got correctly held to my own event-storing principle: payment is *derivable* from orders + MOQ rules, not a separate event. Dropped the table. Memo moment: *"a 'you held me to my own rules' moment that strengthened the design."*

**The over-engineering vs deletion tension — the real pivot.** The brief emphasises deletion. The schema reached 26 tables. Two paths considered: (a) cut hard to 8 bare-bones tables (collapse dietary tags into text, payments into JSON, drop operational logging) which lost meaningful capability, or (b) keep the 26-table architecture but build it in *phases*, applying the deletion test at the phase level rather than the table level. Chose (b). Memo line: *"I designed 26 entities; I built them against the workflow's actual demands; phase 4's optional tables were deferred to v2 with reasoning."*

**The terminology meta-moment.** Partway through schema design, I had to call out that database terminology was a translation layer I hadn't fully internalised. When proposals led with it, I couldn't push back effectively. We changed format: operational reality first, database pattern second. This is the design philosophy that produced the rest of the work — *operational reality drives schema, not the other way around.*

**No literal kitchen-sink schema exists.** The pruning happened conversationally during design. The 26 tables are the result, not a post-prune state of some 44-table monstrosity. Honest memo line: "the rejected alternatives are documented in the decision register; pruning happened iteratively during design, not in a single deletion pass."

**The reverse-engineering of V1-V3.** The actual chronological journey produced a near-V3 design in the first chat. The V1-V3 documents in the repo are a reconstructive overlay applied later to make the journey examinable. This is more honest than pretending a sequential timeline. The Learning criterion rewards "rate of improvement" — making the considered-and-rejected ideas explicit shows more thinking than presenting only the survivors.

**The six priorities, locked Day 1.**
1. Safety and correctness (non-negotiable floor)
2. Coordinator out of the bottleneck
3. Feedback loop closes
4. Rotation has teeth
5. Build is legible
6. Fails gracefully
Cost optimisation explicitly demoted to "constraint, not goal." This priority ordering is the spine of every downstream decision.

---


# Memo Notes — V3 Design Decisions

Material drawn from the V3 add-back interview process. Each note maps to a Learning-criterion or Taste-criterion sentence in the final memo. Organised by theme; not chronological.

## On the design philosophy

- **Delete by default, justify additions.** V2 was the pedantic strip pass; V3 adds back only what survives a value-vs-complexity test. Every addition has documented reasoning; deletions stay deleted by default. The process makes thinking visible rather than hiding behind a polished final design.
- **Prioritising freedom over cost optimisation.** Padea's V1 economics scaffolding optimised under constraint (variety tiering, MOQ surplus calculations, scenario snapshots). V3 accepts the constraint as a small ongoing cost and delivers more freedom per dollar instead. Composition is preference-driven; cost falls out of preferences, it doesn't shape them.
- **Derive, don't store.** Where current state can produce the answer to a historical question (cost trajectory, average cost per student), V3 derives rather than snapshotting. Cuts an entire class of history tables and end-dating logic that V1 carried.

## On what the system should ask of whom

- **Tutors and managers carry the feedback signal, not parents or kids.** Voluntary weekly submission from parents or kids is historically unreliable; staff Padea pays have an obligation to fill in their app. V3 routes all per-session signal through tutors (per-kid scoring + comment) and session managers (session-level scoring + checklist + meals-left + names of kids who didn't eat). Trust is in the people we already pay.
- **Parent burden minimised by design.** Parents are asked once per enrolment for dietary tags and the approved meal set. Caterer changes don't trigger a parent re-ask; tutor-led preference reset handles it. The dietary profile is durable; the menu-specific approved set isn't.
- **Transparent preference framing.** Asking parents to "pick the meals we'll cycle between for your student" rather than "pick five" is a deliberate honesty move. Five is arbitrary; the real ask is "which subset of this caterer's menu is acceptable." Variable cardinality makes that explicit.
- **Tutor-mediated request mechanism as a release valve for parent-pref drift.** Parent-captured prefs sometimes don't reflect what the kid actually wants. The request mechanism lets the kid express real preference through the tutor — drawing from any dietary-safe menu item, not just the parent-approved set — without forcing a parent-loop re-ask. Pattern data feeds V4 algorithmic preference adjustment.

## On caterer relationships

- **Capability matrix considered and rejected.** V1 designed a full `(caterer, school, day_of_week, status, effective_dates, preference_rank, source)` relational matrix with 11 downstream join points. We considered it carefully and rejected it: the matrix solves problems Padea's operation doesn't yet have. Distance-radius targeting + RFP-time availability confirmation produces the same operational outcome (the right caterers get asked, the operator picks) with three columns instead of one full relational subsystem.
- **Competitive RFP framing.** Used rather than serial enquiry because it parallelises response time and creates implicit pricing pressure without explicit negotiation. The "out of those who agree we'll pick" framing is commercial leverage embedded in the process.
- **Generous default delivery range.** The 50km default for un-asked caterers is deliberately permissive. The cost of an over-reach is a caterer politely declining an RFP; the cost of an under-reach is silently excluding a caterer who'd have said yes. We optimise for the second mistake being impossible. Adjustable as the operation expands or contracts.
- **Honest rotation timeline.** Detection → warning → recovery window → RFP → responses → operator pick → cancellation notice → preview week → standard rotation is realistically a 3–5 week process, not "starting next week." Draft templates reflect this; demo narrative respects it.
- **Padea's caterer history is one-per-school over time.** Quality decline within a single relationship, not across multiple concurrent ones. Cross-school cost/quality comparison (V1's Shape C) has no data to feed it in V3 and is deferred accordingly. Shape B (current-pricing-projected) is the operator-facing cost surface.

## On MOQ and growth

- **MOQ as a transient problem.** The V1 MOQ-optimisation layer was solving a problem materially shrinking with Padea's growth. We chose to pay occasional shortfalls and surface them to the operator rather than build a system whose value decays as the cohort grows. Strong Learning sentence.
- **Never reduce variety to clear MOQ.** Natural variety in any order is whatever falls out of the cohort's collective preferences; the system doesn't strategically narrow it. If MOQ isn't met, pay the difference and notify. The escalation is informational, not action-required.
- **Canonical meal ordering as soft cluster alignment.** Each kid's rotation traverses a fixed sequence; kids with overlapping preferences tend to land on the same meal in any given week without any explicit clustering. Solves MOQ-relief naturally without any clustering algorithm.

## On automation boundaries

- **Auto-send vs. drafted-and-queued.** Commercial-change emails (warnings, RFPs, cancellations) are drafted by the system and queued for one-click operator approval. The 30-second saving on auto-send doesn't outweigh the commercial-relationship damage if the tone misfires. Routine actions (the weekly order to the incumbent) are autonomous because the relationship and shape of the message are pre-approved.
- **Rotation-stakes decisions stay human-initiated.** Sustained-decline detection fires an escalation and drafts a warning. The decision to escalate from warning to RFP, and to send the RFP, stays with the operator. The system does the data work; the human owns the commercial stakes.
- **Predicted cost on the order email as a soft tripwire.** Sending the prediction creates a low-effort verification channel — caterers see what we expect to pay, they reply if it's wrong. Catches pricing surprises through existing communication rather than building invoice ingestion infrastructure.

## On scoring discipline

- **1–5 not 1–10.** Five-point Likert handles central tendency bias better at the demo scale; the action is in the comments anyway, not the number. Both tutor and manager apps anchor the scale with in-app reminders (5 = perfect, 3 = satisfactory).
- **Probe, don't parrot.** Tutors are trained to push back on first-numbers from kids ("really a 5?") rather than just accept the verbalised score. The signal lives in the *negotiated* number, not the first one.
- **Unweighted rolling math committed; per-rater normalisation deferred.** Per-rater baseline normalisation, submission-timing decay, cross-rater divergence detection — all real V1 ideas, all deferred to V4. The data substrate is collected from V3 onwards; the analytics earn their place when there's enough history to make them meaningful. "Collect the data substrate from day one; defer the analytics until there was enough history to make them meaningful" is the Learning sentence.

## On edge cases acknowledged but not solved

- **Dietary-kid-low-variety problem.** Restricted-diet kid on a new caterer with few dietary options will receive the same one or two meals repeatedly. We chose dietary safety over variety deliberately; a production version would chase caterers for an expanded dietary range as a procurement requirement.
- **Parent approves zero meals.** Edge handled by escalation: system can't pick if nothing is approved, operator does manual outreach to parent.
- **Tutor doesn't fill the post-dinner box.** Kid's rotation continues from preferences as normal; that session's tutor rating is recorded as missing, not zero. Doesn't feed the rolling mean. Repeated missing data on a tutor or session is itself a soft signal visible in the weekly report.
- **Zero or one RFP responses.** Zero: system escalates, operator decides whether to extend search or proceed manually. Cancellation email hasn't been sent so no commercial damage. One: operator decides whether to accept the single respondent or retain the incumbent.

## On dependencies and process notes

- **Tutor / manager training is a system precondition.** The data quality of the entire feedback ecosystem depends on staff being trained to use the scale consistently, to probe rather than parrot, and to use the request mechanism transparently. The system surfaces the data; staff must collect it well.
- **Postcode-to-geo lookup is a third-party dependency.** Australian Post coordinate data (or a maintained Python library like geopy) handles distance calculation. Worth naming as a dependency in the build artifact.
- **The V1→V2→V3 process itself.** V1 was the ambitious initial design; V2 was the pedantic strip; V3 adds back only what survives a value-vs-complexity test. Every addition is justified in writing. V4 (simplification) and V5 (cycle-time acceleration) follow. This makes thinking visible rather than presenting only the final design — directly serves the Learning criterion.

## On rare cases (from Group 6)

- **Rare cases handled by humans, not code.** Mid-term enrolments are flagged as rare in the brief; opt-out reversals are rarer. Building automation for both would expand system surface area for a benefit that fires a handful of times per term. We chose operator handling end-to-end for these and kept the system focused on the common path. Inverse of the V1 instinct to model every edge case.
- **Redundant-channel reasoning.** An earlier Group 6 design had tutors recording free-text comments on opt-out kids. We cut it because the signal it captured (kid wants in) already has a working path (kid → parent → Padea). Building a second channel for an existing path is infrastructure for completeness, not value. "We identified that a proposed surface was a redundant channel for an existing path and chose not to build it" — direct Learning-criterion sentence.

## On opt-out posture (from Group 6)

- **Default-opted-in.** Catering is default-on; parents opt out actively. Matches the operational reality that most parents want catering.
- **Parent-controlled, not kid-controlled.** Opt-out changes only on parent action. Protects against impulse changes and keeps consent anchored where it legally lives.
- **Opt-out kids count toward attendance, not meal counts.** Different states for different operational purposes (staffing vs. catering).








delete v4 and v5 

Here’s a memo-style paragraph you could adapt:

In hindsight, I would have liked to spend more time on the final optimisation and acceleration stages of the process. My intended pathway was V1 to V5: start broad, delete aggressively, add back only what earned its place, then optimise and accelerate the final system. In practice, I spent from Thursday to Tuesday working through the hardest part of the task: interpreting a deliberately vague brief, grounding the requirements in messy source data, building an ambitious first architecture, stripping it back, and then carefully rebuilding the parts that actually mattered. By the time V3 was complete, I felt the core design had been tested deeply enough to start building for heats, even though V4 and V5 were compressed. This was a deliberate trade-off rather than an oversight: further simplification would have improved the polish of the system, but delaying implementation further would have put the working demonstration at risk. The final design is therefore not the fastest or most elegant possible version, but it reflects the most important thinking I did: learning what complexity the problem genuinely required, and what complexity was just architecture for its own sake.


## On enrolment lifecycle (from Group 8)

- **Active state is derived, not stored.** A status field was considered and rejected because it creates a second source of truth that can drift from the date columns. Dates are the canonical fact; activeness is computed.
- **Three lifecycle dates, not two.** Original start date (durable across re-enrolments), current-period start date (updates on return), current-period end date (null while active). Preserves "first ever joined Padea" as a fact that survives any number of departures and returns.
- **End-date semantic is "end of Padea relationship," not "left the school."** Padea is a separate entity from the school; the system tracks the catering-relevant relationship only.
- **Opt-out and withdrawal are factually distinct.** Both produce the same catering behaviour (skip the kid). They differ for safety auditing: opted-out kids are at the school on incident dates, withdrawn kids are not. Preserved via the orthogonal boolean rather than collapsed.
- **Date-parameterised enrolment queries as a discipline.** Every enrolment-checking tool takes a date parameter. Order composition uses session date; weekly report uses today; incident investigation uses incident date. One query infrastructure across all use cases.
- **Dietary tag history is the accepted gap.** Rare-case dispute (parent claims we knew about a restriction at the time of an incident) can't be answered from current overwrite-in-place model. Accepted because kids self-protect, the originating email is its own record, and the build cost doesn't earn its place. Production-build trigger documented.
- **Term boundaries handled by routine flows, not by bulk reset.** Operator end-dates departing kids one by one (or in small batches), creates new rows for new joiners, marks holiday periods as full-school exclusions. The system has no concept of "term" — terms emerge from the exclusion calendar.
- **History tables cut by policy across the schema.** No enrolment history, no menu price history, no caterer history. Overwrite-in-place chosen as discipline. Audit gaps documented as known production-build triggers rather than V3 features.


## On observability and escalation (from Group 11)

- **System surfaces; the human handles.** V1 modelled elaborate lifecycle state machines for escalations (open → acknowledged → in_progress → resolved). V3 trusts operator discipline instead — the system surfaces clearly, the operator acts, the next run reflects whatever new state results. The system's responsibility ends at surfacing. Builds for a single operator on a weekly cadence; lifecycle state would be modelling workflow for a scale that doesn't exist.
- **Three-tier urgency maps onto real escalation surface.** Urgent (gating something), notable (pattern or signal worth investigating), informational (audit-trail entry). Not arbitrary — fits the eight-to-ten distinct escalation types V3 produces across its locked decisions.
- **Wording is the load-bearing thing, not structure.** Because no lifecycle state tracks resolution, each escalation has to be readable enough to act on at first read. Subject line states what happened; body states the decision space; tier sorts the list. Wording quality is a system precondition.
- **Decision log as the only operator surface beyond the weekly report.** Regenerated from the database every run. Database is the source of truth; log is a view.
- **V4 triggers documented for every cut piece of escalation modelling.** Lifecycle (build trigger: operator team grows or volume becomes unmanageable). Dedup with recurrence (build trigger: pattern-matching breaks down). Retry (build trigger: unhandled urgents become problematic). Tree (build trigger: chains routinely span 5-7+ steps). References column (build trigger: JSON forensic queries become unacceptably slow). Cutting isn't "we don't need this"; it's "we don't need this yet, here's what would tell us to build it."




## NOTE; explain the layout of v one to five fully in this memo. 


## On identity layers (from Group 9)

- **Tutors as the only first-class identity table.** Students, parents, and cross-school identity all stay denormalised on enrolment rows. The bar for promoting to first-class is "does the system ask cross-context questions about this entity?" Only tutors clear that bar in V3 — feedback attribution needs cross-session identity.
- **Dual-role manager-tutor via booleans, not enum.** A person can be a manager, a tutor, both, or neither at any session. Booleans naturally express all four states; a role enum would force awkward "both" semantics or duplicate rows.
- **Feedback counts manager and tutor perspectives independently even from the same human.** A dual-role person submits two channels; rolling-mean math counts them as two raters, not one. Avoids double-counting a single perspective.
- **Denormalised parent contact accepted with maintenance cost.** Multi-sibling parent-email updates require touching each enrolment row. Accepted because the build cost of a parents table (FK cascade, ID maintenance) exceeds the low-frequency maintenance cost.

## On margins and predictions (from Group 10)

- **Zero operational margin is a deliberate cut, not an oversight.** V1 had walkup buffers, tutor buffers, ML-predicted absence margins. V3 cuts all three. The system orders exactly what it knows it needs. The cost of being wrong: occasional walkup with no meal that day. The cost saved: an entire prediction/reconciliation/buffer subsystem whose output we don't yet have data to validate. "We removed every margin concept because each margin solved a problem we don't have data to model."
- **Walkups suffer one week of no-meal — by design.** The kid asks their parent to email Padea. From the next session run, they're in rotation. The one-week friction is the forcing function keeping opt-out as a real choice. Intentional friction.
- **Opt-back-in via tutor app surfaces kid signal without depending on parent initiative.** Opted-out kid's tutor sees a checkbox where the rating box would be. Tick fires an email to the parent. Send-once tracking means repeated ticks don't spam. Kid's interest reaches the system via the tutor's eye; reversal still requires parent action.
- **Autonomous parent emails for routine non-commercial communications.** Operator approval reserved for commercial-relationship messages (warning, RFP, cancellation). Opt-back-in is parent-facing, low-risk; sends autonomously.
- **No formal reconciliation table.** Partial reconciliation (meals-left, kids-who-didn't-eat) lives inside the manager's session feedback. The structured count fields V1 had (walkup_count, excess_meal_count, shortfall_count as columns) are cut. V4 trigger documented if reconciliation becomes a real query surface.

## On architecture and cadence (from Groups 12, 13, 14, 15)

- **Per-session cadence is the architectural design call of V3.** V2 inherited Thursday-for-all-week from the human's existing operation. The Thursday cadence was an artifact of the human's schedule, not a system requirement. V3 replaced it with a 72-hour-per-session cadence — every caterer gets equal prep time regardless of which day they serve. "The existing cadence was a human-calendar artifact; we replaced it with a system-native cadence."
- **Monday 3:30 PM consolidated summary as the canonical spending document.** Aggregates the week's individual orders into one per-caterer summary with MOQ floor and GST applied. Payment crystallises here. The summary is the de-facto invoice from Padea's side; the database row for it is the audit record.
- **Order emails are final from the moment sent.** No provisional/final distinction. Caterer prepares against the order email; the Monday summary is administrative.
- **Payment is a known unknown.** Brief doesn't specify how Padea pays caterers. V3 assumes Monday 3:30–4:00 PM as the financial crystallisation window without modelling the payment mechanism. V4 build trigger documented.
- **Operator checks email over weekends.** Saturday and Sunday agent runs send orders autonomously; escalations wait until operator reads them. Acceptable for V3 demo; production hardening flagged.
- **Supabase native from day one.** Brief recommends Supabase as the "harder" database option. Postgres-native rather than SQLite-with-mirror is a Taste call.
- **Order email body shape carries operational + feedback weight.** Each line is meal-name + allocated-kid. Disambiguates prep; lets V3-FB-01 attach feedback to (kid, meal) pairs. The order email is the source-of-truth document for what each kid got on each date.
- **Room field on session_slots — the one missing location piece.** V2 had building (school-level); no room. Caterer emails couldn't say "Building A, Room 12." One column fixes it; brief explicitly mentions caterers asking for session-location help.
- **Per-date manager variation handled implicitly.** V3-IL-01's assignment model is per-session, not per-(school, day-of-week). Standin managers covering one-off sessions just get assignment rows for those sessions. V3 supports something V2 didn't, without adding any new mechanism.
- **Every dietary tag is safety-critical by default.** No severity field means the system treats preferences and allergies identically. Over-cautious, but the safe direction. V4 brings severity if data arrives carrying it.
- **Every deferred item carries a V4 build trigger.** Cutting is not silent absence; it's documented intent. Each cut item has a documented "build when this happens" condition. "We documented every deferred capability with the operational signal that would justify building it later — deletion was active, not passive."yes do 


really emphasise the v4 and v5 delete. with more time this will be ooptimised. 


Constraints on Task 3:
- The summary should be 150-300 lines total — short enough to read in 5 minutes.
- Every claim should be traceable back to a decision block in the ledger. Do not invent.
- Maintain the same tone as the ledger (operational, specific, honest).
- Do NOT include the full structured fields or detailed operational scenarios from the ledger.
- Do NOT rewrite or paraphrase memo flags — pull them directly where used.

# Final verification

After completing all three tasks:
1. Confirm `v3_decisions_ledger.md` exists with the residual fixes applied.
2. Confirm `v3_summary.md` exists at 150-300 lines.
3. Run `wc -l` on both files and report the counts.
4. Report any "find this text" patterns that didn't match in the source — flag them, do not silently make changes.
5. Confirm the old filename `v3_reinstatements_ledger_clean.md` no longer exists (it was renamed).