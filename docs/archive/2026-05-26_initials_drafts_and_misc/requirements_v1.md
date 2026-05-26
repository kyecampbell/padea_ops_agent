# Requirements V1 — Padea Operations Agent (Initials Stage)

**Purpose:** The maximally ambitious set of requirements that can still be argued from first principles. This document captures the system's *job* — outcomes and necessary conditions — at the level of what the system must achieve, not how it achieves it. Mechanism (schema, tool choice, agent loop) lives downstream.

**Compiled:** 25 May 2026
**Version:** V1 — ambitious initial pass. This document will be stripped pedantically into V2 and selectively reinstated into V3. See `docs/initials/methodology.md` for the reconstructive approach.
**Companion documents:** `data_observations.md`, `assumptions.md`, `decision_register.md`, `schema.md` (current), `ledgers/deletions_ledger.md` (V1→V2), `ledgers/reinstatements_ledger.md` (V2→V3).

---

## How to read this document

The requirements are written as a prose tree. The top-level claim is what Padea ultimately needs from this system. Each subsequent paragraph derives its requirements from the one above it. The system's necessary capabilities appear at the leaves, where the chain of reasoning has reached the level of "the system must be able to do X."

The document is dense by design. Skim-reading it would be unfair to the reasoning — every paragraph justifies the one beneath it. Reading top-to-bottom in order is the intended use.

Where a requirement was deliberately chosen over an alternative, the alternative is named. The job of this document is not to declare what's true but to derive what's true and show the derivation.

---

## The system's job, from first principles

Padea is a tutoring business whose continued operation depends on families choosing to re-enrol their children term after term. Re-enrolment is not a decision parents make based on tutoring quality alone — it's a decision they make based on whether the whole experience, including the parts adjacent to tutoring, is something they want to keep paying for. The dinner break is one of those adjacent parts. Done well, it contributes to students enjoying their time at sessions, which contributes to students wanting to return, which contributes to families re-enrolling, which contributes to revenue.

The system therefore exists to make catering an *advantage* to Padea — not merely a logistical necessity that the business has to manage, but an operational surface that quietly compounds the business's competitive position. A coordinator emailing caterers each Thursday and making educated guesses at meals is the current state and is not enough. The system must do better than that, and must do so reliably, so that the catering operation can scale with the business rather than bottleneck it.

For catering to be an advantage rather than a liability, several conditions must be true simultaneously. Students must actually receive meals when sessions run. The meals they receive must not harm them. The meals must be ones students want to eat, not ones they tolerate. Quality must remain high over time, not decay as caterers grow comfortable. Variety must be sufficient that students don't experience boredom or palate fatigue. The operation must be visible enough that decay is detected and acted on rather than persisting unchecked. None of these conditions can be sacrificed; together they are the operational floor on which "catering as an advantage" rests.

The system must achieve these conditions without consuming the coordinator's time in proportion to the number of sessions. The coordinator is a finite resource; if catering remains hand-operated, doubling the number of partner schools doubles the coordinator's catering workload, which is the textbook definition of a bottleneck. The system must therefore own the routine work and surface only the decisions that genuinely require human judgement. When the coordinator (or another nominated supervisor — call this role the *human approver* throughout) is consulted, it must be for decisions where their judgement adds value, not for decisions the system could have made itself.

---

## The non-negotiable safety floor

Above all other considerations, the system must never serve a meal that violates a student's documented dietary requirements. A vegetarian student cannot be served meat. A nut-allergic student cannot be served a meal that contains or contacts nuts. A halal-observant student cannot be served pork. This is not a satisfaction concern — it is a safety concern, and in the case of allergies, a medical one.

This requirement sits above all other requirements in the system. Where other requirements come into conflict with each other — variety against budget, freshness against MOQ — the system must reason about tradeoffs. The dietary safety floor admits no tradeoffs. A meal that violates a documented dietary requirement is a system failure, regardless of any other property it has.

Three consequences follow from this floor being non-negotiable.

First, every student's dietary information must be captured before any meal is matched to them. A new enrolment without recorded dietary information cannot proceed to meal-matching; the system must escalate to confirm before assuming "no restrictions." Default-allow is not safe; default-confirm is.

Second, the matching logic between students and menu items must be expressible as an objective rule, not a confidence score. Probabilistic matching is appropriate for preferences (where the system is trying to maximise enjoyment) but inappropriate for restrictions (where the system must guarantee non-violation). The system must therefore maintain its dietary data with controlled vocabulary, not free text — a typo in a free-text field is a safety incident waiting to happen.

Third, where a dietary tag's interpretation depends on inference (e.g. "non-pork meals are halal" as stated in the source data), the inference must be made *at ingest time, by a human or by a documented rule*, not at runtime. The system reasons over structured facts; it does not derive structured facts from menu names on the fly.

Where a meal cannot be matched to a student because no available menu item satisfies their dietary requirements, the system must not silently substitute — it must escalate to the human approver. A student arriving to find no meal made for them is a worse failure than the system flagging "I cannot satisfy this student's requirements with this caterer's menu; please intervene."

---

## What it means for students to receive meals reliably

A meal received late is, for the duration of the dinner break, indistinguishable from a meal not received. A meal received at the wrong school is, for the affected students, not received. A meal sent without an accurate count is, for the students past the count, not received.

The system must therefore own the logistics of each order from generation through delivery confirmation. This includes generating the order with the correct quantities for the correct session, addressing it to the correct caterer with the correct contact person, sending it with enough lead time for the caterer to prepare, and confirming both that the order was received by the caterer and that delivery occurred at the session. Where any step in this chain fails or stalls, the system must surface the failure with enough lead time that a human can intervene before students arrive expecting food.

The system must furthermore handle the realistic operational case where caterers do not respond promptly to orders. If a caterer has not confirmed receipt of an order by an appropriate threshold before the session, the system must escalate — proposing options such as calling the caterer directly, drafting an enquiry to a backup caterer, or asking the human approver whether to proceed on the assumption of silent acceptance. Quiet failure here is unacceptable; a caterer who has gone dark and a caterer who is preparing the order are operationally identical until they aren't, and the difference matters at session time.

The system must know which caterer is currently committed to which school on which day-of-week. It must know which alternative caterers are eligible to serve each school. It must know each caterer's minimum order quantity rules, which vary by the number of menu items in the order and by the caterer's contract. It must know each caterer's delivery fee structure, GST treatment, and lead time requirements. None of these can be inferred or guessed; they are facts that must be captured and kept current.

When a session is cancelled in its entirety — by school closure, public holiday, weather event, or other whole-session exclusion — the order must not proceed. When a session is partially excluded (e.g. specific year levels at camp), the order must be sized to the remaining cohort plus an appropriate buffer for the social reality that some excluded students attend anyway. The size of this buffer is a numeric policy the system must hold; for V1 it is fixed at ten percent of the excluded cohort, rounded up to a whole meal, on top of the standard session contingency buffer.

Absences within an attending cohort must be handled differently from exclusions. An absence is one student missing one session; an exclusion is a structural decision about a cohort. Absences arriving before the order is sent reduce the order's quantity; absences arriving after the order is sent do not, because amending caterer orders post-prep is operationally disruptive and the contingency buffer absorbs late walk-backs. Where a student marked absent attends anyway, the buffer must cover them; the system must record the walk-up as an event so that recurring false-absence patterns can be detected and the parent contacted.

The contingency buffer itself is small (two meals per session in V1) but is a deliberate operational primitive, not a workaround for poor forecasting. Its job is to absorb the inherent unpredictability of session attendance — a student who came despite an absence email, a tutor who arrived hungry, a visitor present unexpectedly — without forcing the system to make perfect predictions. Where the buffer is regularly exhausted, the system must surface this as a signal for re-sizing. Where the buffer is regularly half-eaten, the same.

---

## What it means for meals to be ones students want to eat

A meal a student doesn't want is, from the satisfaction perspective, a meal not eaten. A session of students who didn't enjoy their food does not contribute to the satisfaction loop the system exists to support. Therefore the system cannot be satisfied with delivering meals that merely comply with dietary requirements — it must deliver meals that students actually want, within the dietary constraints.

This is harder than it sounds, because student preferences are not directly observable by the system and they are not constant across students. Two halal students may have very different taste preferences. A student who liked Korean Beef Bulgogi in March may be tired of it by May. The system must therefore have *some* mechanism for understanding what students want, and that mechanism must scale to hundreds of students across multiple schools.

The V1 ambitious mechanism is weekly preference capture from parents. At the start of each week, the system sends parents a list of available meal options for their child's upcoming session — filtered to exclude items their child cannot eat — and asks the parent to select acceptable options on the child's behalf. The parent may select "all are acceptable" (the system encourages this option for convenience), select specific items, or rank options. The system aggregates these responses across the cohort and constructs orders that maximise the proportion of students receiving acceptable meals.

This mechanism has several attractive properties. It produces direct per-student per-week data. It engages parents in their child's experience, which is itself a satisfaction signal. It makes preferences explicit rather than inferring them. It accommodates students who are picky one week and easy the next. And it sidesteps the problem of asking the same person the same stable question repeatedly — preferences expressed weekly *are* changeable, and the weekly cadence respects that.

The mechanism also has known weaknesses, which V1 will accept and V2 will examine. Parents do not respond at 100% rates and never will; the system must have a default behaviour for non-responders (use the child's most recent stated preferences, or default to "all acceptable"). Parents responding for older students introduces a layer of mediation between the system and the actual eater; the parent's understanding of their teenager's preferences may be incomplete. The administrative load on parents is non-trivial — a weekly email asking for input is a weekly demand on their attention. These weaknesses are real and will be debated in V2.

The system must also handle the case where a student's stated preferences cannot be satisfied — every acceptable option is over MOQ, or the caterer cannot offer enough variety. In this case the system must escalate to the human approver with enough detail to make a decision: which students are affected, what the alternatives are, what the cost difference is. The system does not unilaterally serve a student a meal they did not accept.

---

## What it means for variety to be sufficient

Even when meals are technically acceptable, students experience palate fatigue when the same items recur. Korean Beef Bulgogi every Monday for a term becomes Korean Beef Bulgogi-shaped resentment by week six. The system must therefore vary the menu choices week-to-week, not by random selection but by tracking what each cohort has been served and weighting away from recent items.

In V1 this is a soft requirement enforced by the system at order-generation time: the agent, given the cohort's recent meals and the caterer's available items, chooses items that have not been served recently to that cohort. The system holds the memory of recent meals as data, and the order-generation step consults it.

Variety is constrained by caterer reality. Some caterers have ten menu items; the system cannot conjure more. Some caterers have MOQ rules that effectively force fewer item types per order (Lakehouse's MOQ of 25 at six items vs 15 at four items means smaller schools are forced toward less variety). The system must respect these constraints while doing the best it can within them. Where a school's caterer cannot offer enough variety to avoid recent repeats, the system should recognise this as a signal — possibly indicating that the school would be better served by a different caterer with a broader menu, or by rotation to a backup caterer for a refresh.

---

## What it means for quality to remain high over time

Caterer quality is observed by the business to decline over time once a caterer is comfortably established. This is not a slander — it is a known property of supplier relationships across many industries, and the system must assume it will happen and design for it.

The system must therefore collect quality signals continuously, aggregate them across appropriate time windows, and surface decline early enough that the business can act. Quality signals are not single-source; the system collects them from multiple channels.

In V1, the primary channel is the weekly parent preference response — implicitly, parents who repeatedly reject available options are signalling dissatisfaction with the caterer's offering, even when they don't say so explicitly. Secondary channels include direct feedback (parents who write in unsolicited about a meal), session-level observations (a manager noting "students didn't finish their meals today"), and term-end surveys to families.

The system computes a rolling caterer rating from these signals. Rolling, because single-session noise should not trigger action. Window length is a policy parameter; in V1 it is four weeks. When the rating falls below a threshold, the system surfaces alternatives — drawing from the "able to serve" list — and drafts a swap email for the human approver to review and send.

The system does not unilaterally rotate caterers. Caterer rotation is a relationship decision with commercial implications, and the human approver retains authority over it. The system's job is to detect the need, propose the action, and execute it once approved. The leverage in this relationship is not threat — it is visible measurement combined with the existence of alternatives. Caterers who know their performance is measured and that alternatives exist will tend to maintain quality more reliably than caterers who do not.

Where multiple caterers are eligible to serve the same school, the system must also use this redundancy for proactive trial. Rather than waiting for decline at a school, the system may periodically suggest trying an alternative caterer at a low-stakes session (e.g. a session known to be smaller, or a school with two eligible caterers) and comparing satisfaction signals. This is a V1 ambition; the trial-and-rotate cycle is what turns the caterer-relationship from a static commitment into a dynamic competitive market for Padea's business.

---

## What it means for the operation to be visible

A system that operates correctly but opaquely is, when it occasionally fails, indistinguishable from a system that operates incorrectly. The human approver cannot supervise what they cannot see. The judges cannot evaluate what they cannot inspect. Future operations staff cannot trust what they cannot audit.

The system must therefore produce an inspectable record of every decision it makes. Each agent run is one row in a record of runs. Each decision within a run is one row in a record of decisions, linked back to the run and to any prior decisions that influenced it. Each tool call the agent makes, each branch in its reasoning, each rule it applies, each escalation it raises is captured.

This record is not just for forensics — it is the surface on which the demo lives. The same record that lets the human approver answer "why did the agent do that?" three weeks from now is the surface that lets a judge watching a five-minute video understand what's happening in real time. The system must therefore produce this record in a form that is *legible*, not merely *complete*. Color-coding for outcomes (success, escalation, deferred), typography that respects the reader, structure that draws attention to the interesting decisions and hides the routine ones.

The system must also be designed to fail loudly rather than silently. When uncertain, it escalates. When data is missing, it escalates. When a tool fails, it logs and escalates. The default behaviour for "I don't know what to do here" is to ask, not to guess. This is the operational analogue of the dietary safety floor — when the system is at the edge of its competence, the human approver is the safer destination than the system's own best guess.

---

## What it means for the coordinator to be out of the bottleneck

The coordinator currently spends meaningful time each Thursday composing emails to caterers, making educated guesses at quantities and menu choices, fielding parent emails about absences, and managing the routine flow of catering operations. The system's job is to take the routine flow off their desk while leaving them in clear ownership of the non-routine decisions.

This means the system must own end-to-end order generation, including item selection, quantity calculation, and email composition. The coordinator should never be in the loop of a routine order; they should only see catering activity when something requires their judgement.

The system must escalate to the human approver for: caterer rotations (commercial decision), pricing or contract anomalies (commercial decision), capability changes that affect a caterer's continued service (relationship decision), MOQ shortfalls that require commitment to extras at a cost (commercial decision), dietary cases where no menu item satisfies a student's requirements (safety decision), and any failure mode the system has not been designed to handle (out-of-scope decision).

The system must *not* escalate for: routine order generation, routine absence handling, routine exclusion handling, routine confirmation/reminder workflows, or any decision the system can make from the data and rules it already holds.

The dividing line between routine and non-routine is itself a system policy that must be maintained. As the system learns what kinds of decisions it can make reliably, more of what was non-routine becomes routine. This evolution should be tracked in the same decision record — over time, the system's own log becomes evidence for which escalation types could be auto-resolved in future versions.

---

## What it means for the system to fail gracefully

No system runs without error. The question is not whether the system fails but how it fails. The system must be designed such that its failure modes are loud, surfaced to humans with sufficient context, and never silently destructive.

When the system cannot complete a workflow, it must record the partial state explicitly so a human can resume from the failure point rather than re-running from scratch. When the system encounters input it does not recognise, it must capture the input verbatim before attempting interpretation, so that interpretation failures do not lose data. When the system runs longer than expected, it must time out gracefully and escalate rather than hang. When tools the system depends on are unavailable (email service down, model API failure), the system must degrade to a reduced mode that preserves operational continuity.

The single most important failure-mode property: the system must never serve a student a meal that violates their documented dietary requirements, *even when other parts of the system have failed*. Where the system cannot confidently match a student to a safe meal, it escalates and waits, regardless of how routine the request appeared at the start.

---

## Outcome targets V1 commits to

The system is judged not merely by whether it operates but by what it produces over time. V1 commits to the following outcome targets, measurable against the current state of operations:

The coordinator's time spent on catering should drop by approximately 80% within six months of the system being in operation. This is the bottleneck metric — the test of whether the system has actually removed the coordinator from the routine flow.

Student-reported satisfaction with the catering experience should rise term-over-term. The signal is collected through the parent weekly preference flow (response rates and selection patterns), the term survey (direct rating), and the rolling caterer rating (composite signal). Trend direction is the metric; absolute values are baselined at the system's first complete term of operation.

Caterer rotations should be triggered by data, not anecdote. The system's rotation proposals should be visibly tied to declining ratings, not to the human approver's intuitions. A rotation that the system did not propose first is evidence of a failure of the satisfaction loop to detect what humans detected manually.

Operational integrity should be measured by zero unhandled escalations exceeding their expected response window, zero dietary safety violations, and zero sessions where students arrived to find no meal arranged. These are operational floor metrics; they are not aspirational, they are non-negotiable.

---

## Operational assumptions V1 makes

The system operates under several assumptions about the world it is embedded in. These are not requirements — they are facts the system relies on which are out of scope to enforce or change.

The human approver is available to respond to escalations within a reasonable window during business hours, typically same-day. Where the approver is unavailable for extended periods, secondary delegation must be configured in advance.

Caterers respond to orders within a reasonable window. The system has handling for non-response (escalation, backup-caterer-enquiry) but assumes the routine case is responsive caterers. A caterer who is structurally non-responsive should be replaced via the rotation mechanism; the system does not work around chronic supplier failures.

Students and parents communicate primarily via email, or via channels (SMS, phone) that are forwarded into the email channel by the recipient before reaching the system. The system reads from an email inbox; it does not directly read SMS or take phone calls. Where it does so in future versions, that capability is out of V1 scope.

Session managers submit feedback in a format suitable for the system to ingest. Where the manager submits feedback in an unstructured form (free text in an email, voice memo, etc.), an upstream agent — not part of V1 — converts it to the structured form the system expects. V1 reads structured manager feedback; the conversion layer is a separate concern.

The source data describing schools, sessions, students, caterers, contacts, menus, and rules is treated as accurate at ingest time. The system does not second-guess input data on plausibility grounds. Where data appears anomalous (e.g. an unusually low menu price), the anomaly is documented but not corrected; the system's job is not to be a market analyst.

---

## What V1 explicitly does not attempt

For clarity, V1 is *not* trying to do the following — these are out of scope by design, not by omission:

V1 does not replace the human approver. The approver retains final authority on caterer rotations, commercial decisions, and any case the system escalates. The system is decision-support and operational execution, not autonomous decision-making.

V1 does not manage tutoring scheduling. Which tutor teaches which students at which time is the domain of a separate (and existing) Padea system. V1 reads tutor and manager assignments as input; it does not modify them.

V1 does not track student attendance for academic purposes, manage report cards, or relate to the academic content of sessions. Its concern is the catering operation; the broader student record is out of scope.

V1 does not handle billing, parent payments, or invoicing. Caterer payment is *modelled* (committed amounts derived from orders and MOQ rules) but the system does not interact with banking systems or send invoices. Real banking integration is deferred indefinitely.

V1 does not handle Friday sessions or schools not in the current configuration. Adding either requires explicit operational changes to caterer capability matrices and is treated as a configuration extension, not a runtime feature.

V1 does not include an upstream conversion agent for non-structured manager feedback. The V1 system assumes structured input; the conversion layer is a separate component to be built later.

---

## Notes on this document and what comes next

This is V1. It is ambitious. It commits to capabilities that, on review, may not all survive a strict deletion test. That review is V2's job, and the cuts will be tracked in `ledgers/deletions_ledger.md` with reasoning. Some V1 capabilities will be cut in V2 and not return; others will be cut in V2 and selectively reinstated in V3 via `ledgers/reinstatements_ledger.md`. The journey from V1 through V3 is the design's evolution made visible.

When reading the schema and the decision register alongside this document, note that the schema reflects the system as it stood when the documentation was formalised, which is closer to V3 than to V1. The documents in this folder describe the ambitious initial conception; the schema describes the current shipping design. The methodology document (`methodology.md`) explains why the two differ and how the journey was reconstructed.

V1's job is not to be correct. V1's job is to be honestly ambitious — to capture what the system might do if every defensible capability were pursued, so that V2 has something meaningful to cut and V3 has something meaningful to justify. The document earns its keep by being more than V3, not by being right.
