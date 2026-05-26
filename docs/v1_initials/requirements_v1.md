# Requirements — Padea Operations Agent

**Purpose:** What the system must do. Each requirement is derived from a premise that necessitates it. Decisions about *how* requirements are satisfied live in the decision register.

**Compiled:** 25 May 2026
**Companion documents:** `data_observations.md`, `assumptions.md`, `decision_register.md`, `schema.md`.

---

## How to read this document

Requirements are written as a chain. Each section begins with a premise — a claim about Padea's operational reality. The requirement is what must be true of the system for that premise to hold. Subsequent paragraphs in a section refine the requirement by reasoning further from the same premise.

Where a paragraph says "the system must," the statement is a requirement. Where a paragraph says "for X to be true, Y must hold," the statement is a derivation. The two interleave because requirements are not isolated demands — they are consequences of premises.

---

## The system's job

Padea is a tutoring business whose continued operation depends on families choosing to re-enrol their children term after term. Re-enrolment depends on the whole experience families pay for, of which the dinner break is a part. The system therefore exists to make catering an advantage to Padea — a part of the experience that contributes positively to re-enrolment rather than detracts from it.

For catering to contribute positively, several conditions must hold simultaneously: students must receive meals when sessions run; the meals must not harm them; the meals must be ones students want to eat; quality must remain high over time; variety must be sufficient; and the operation must be visible enough that problems are detected and acted on. None of these can be sacrificed; together they form the operational floor.

For these conditions to hold without the business hitting a bottleneck, the system must achieve them with effort that does not scale linearly with the number of sessions. If catering remains hand-operated, doubling the number of partner schools doubles the coordinator's workload. The system must therefore own the routine work and surface only decisions that genuinely require human judgement. When the human approver (the coordinator or another nominated supervisor) is consulted, it must be for decisions where their judgement adds value.

---

## The non-negotiable safety floor

For catering to contribute positively to Padea's business, it cannot harm students. This is a safety floor: the system must never serve a meal that violates a student's documented dietary requirements. A vegetarian student cannot be served meat. A nut-allergic student cannot be served a meal containing or contacting nuts. A halal-observant student cannot be served pork.

For this floor to hold, the system must have current dietary information for every student before any meal is matched. Where the information is missing or ambiguous, the system must not proceed on assumption.

For matching to be reliable, every menu item the system reasons about must have its dietary properties resolved in advance. The system cannot infer dietary properties at the point of decision; the resolution must already exist in the data the matching reads.

For matching to be reliable even at the edges, the system must escalate when no available menu item satisfies a student's dietary requirements. A student arriving to find no meal made for them is a worse failure than the system flagging an unmet requirement in advance.

For the safety floor to hold even when other parts of the system fail, the floor cannot depend on the rest of the system working. Where the system cannot confidently match a student to a safe meal — for any reason, including unrelated failures elsewhere — it must escalate and wait.

---

## Reliable meal delivery

For students to receive meals when sessions run, meals must arrive at the right place, at the right time, in the right quantities. A meal received late is, for the duration of the dinner break, a meal not received. A meal at the wrong school is a meal not received. A meal sent with the wrong count is, for the students past the count, a meal not received.

For this to be true, the system must own the logistics of each order from generation through delivery confirmation. It must generate orders with correct quantities for the correct session, address each order to the correct caterer with the correct contact, send each order with adequate lead time for caterer preparation, and confirm both that the caterer received the order and that delivery occurred at the session.

For failures in this chain not to become surprises at session time, the system must surface stalled or failed steps early enough that a human can intervene before students arrive expecting food.

For surprises not to come from caterers themselves, the system must handle the operational reality that caterers do not always respond promptly. Where a caterer has not confirmed an order in adequate time before the session, the system must escalate with viable options for the human approver — contacting the caterer directly, drafting an enquiry to an alternative eligible caterer, or proceeding under explicit human direction.

For the system to make correct ordering decisions in the first place, it must hold accurate facts about each caterer: which schools they currently serve, which schools they are able to serve, their minimum order quantity rules, their delivery fee structure and tax treatment, their lead time requirements. None of these can be inferred at runtime; they are facts the system must hold and keep current.

For caterer constraints to be respected economically, the system must distinguish between failing MOQ (which has a financial cost) and meeting MOQ (which does not). Where the cohort cannot meet a caterer's MOQ at the desired variety level, the system must surface the shortfall to the human approver with the cost implication made explicit.

For the system to handle sessions that do not run as normal, it must distinguish two kinds of disruption. When a session is cancelled in its entirety, no order must be sent. When a session is partially disrupted — for instance when specific year levels are excluded due to a camp or school event — the system must size the order to the remaining cohort while accounting for the reality that some students whose year level is excluded attend anyway.

For absences within a running session to be handled correctly, the system must distinguish absences that arrive in time to affect the order from absences that arrive after. Those arriving in time reduce the order's quantity; those arriving after do not, because amending caterer orders late in their preparation is disruptive. Where a student notified as absent attends anyway, a meal must still be available. The system must capture such walk-up events so recurring false-absence patterns can be identified and addressed.

For absorbing unpredictability that no notification system can eliminate, the system must include operational margin in each order — enough to handle students who came despite an absence notification, students who didn't come despite no notification, and visitors present unexpectedly. The size of this margin must be small enough to keep order economics tractable and large enough to avoid routine shortfalls. Where the margin is regularly exhausted or regularly unused, the system must surface this as a signal for re-sizing.

---

## Meals students want to eat

For the satisfaction loop to function, meals must be ones students actually want, not merely ones that comply with their dietary restrictions. A student who reliably receives food they would not have chosen is a student whose experience does not contribute to re-enrolment, regardless of whether they ate it or not.

For meals to be ones students want, the system must hold a current understanding of what each student finds acceptable. The understanding must be per-student, because cohort averages cannot match individuals. It must accommodate change over time, because preferences shift. It must distinguish students who genuinely have preferences from students who are content with whatever is provided, so the responsiveness of a subset of households does not bias outcomes for the rest.

For the system not to make claims on a student's behalf it has no basis for, it must not serve a student a meal the student or their household has not accepted as a possibility.

For unsatisfiable preferences to surface rather than be silently overridden, the system must escalate when it cannot satisfy a student's preferences within available menu items and caterer constraints. The escalation must include enough detail for the human approver to make a decision: which students are affected, what alternatives are available, what trade-offs exist.

---

## Sufficient variety

For meals to remain ones students want over time, palate fatigue must be prevented. Students who eat the same item repeatedly come to want it less, even when they initially wanted it. The requirement is not that the system serves variety for its own sake — the requirement is that the system prevents fatigue.

For fatigue to be preventable, the system must hold knowledge of what each student has been served recently and what alternatives each student finds acceptable. The first comes from the system's own order history; the second is the same per-student acceptability understanding that the previous section requires.

For variety to be possible, caterer constraints must permit it. Caterers have finite menus and minimum order quantity rules that can force fewer item types per order. The system must work within these constraints. Where a school's caterer cannot offer enough variety to avoid recent repeats for the cohort, the system must recognise this as a signal worth surfacing — a constraint that may indicate the caterer is no longer the right choice for that school.

For variety to be reduced gracefully when caterer constraints demand it, the system must know which menu options to keep and which to cut. When the caterer's minimum order quantity at the desired variety level cannot be met by the cohort, the system must reduce the number of menu options offered until MOQ becomes feasible. The choice of which options to drop must be informed by the same per-student acceptability data the previous sections require — the system must retain the options the most students find acceptable and drop the options the fewest find acceptable. Where dropping options would force students onto choices they have not accepted, the system must escalate before sending the order.

In choosing which options to cut, the system must also preserve dietary coverage for the cohort — cutting a vegetarian option from the menu set when half the vegetarians on the cohort depend on it produces a worse failure than cutting a less-relied-on option.

---

## Quality maintained over time

For catering to contribute positively to re-enrolment over time, caterer quality must not decline. Caterer quality is observed by the business to drift downward once a caterer is comfortably established. The system must prevent prolonged decline, not merely detect it after the fact.

For decline to be preventable rather than just detectable, two things must be true. Caterers must have a reason to maintain quality. And the system must be able to recognise decline early enough to act before students experience prolonged poor service.

For caterers to have a reason to maintain quality, the relationship structure must include both visible measurement of their performance and credible alternatives to them. A caterer who knows their performance is measured, and that schools they currently serve could be served by another caterer, has a structural incentive to maintain quality that a caterer in a captive relationship does not have. The system's job is not to create this incentive through threat — it is to maintain the conditions under which the incentive exists. The system must therefore hold and keep current the data that makes alternatives credible: which caterers are able to serve which schools on which days, and what the trade-offs would be for each alternative.

For decline to be detectable early, the system must collect quality signals continuously, aggregate them across time windows long enough to filter session-to-session noise, and surface aggregated decline before students experience prolonged poor service. Quality signals must come from multiple sources rather than any single channel, because reliance on any one source creates a system that fails when that source goes quiet.

For decline to be acted on once detected, the system must surface alternative eligible caterers and draft a swap proposal for the human approver to review. The system must not unilaterally rotate caterers; rotation is a relationship and commercial decision belonging to the human approver. The system's job at this point is to detect the need, propose the action, and execute the action once approved.

---

## Visible operation

For an operation to be supervisable, it must be visible. A system that operates correctly but opaquely is, when it occasionally fails, indistinguishable from a system that operates incorrectly. The human approver cannot supervise what they cannot see; future operations staff cannot trust what they cannot audit.

For the operation to be visible, the system must produce an inspectable record of every meaningful decision it makes. Each agent run, each decision within a run, each tool the agent invokes, each rule it applies, each escalation it raises must be captured with enough context that a human reading the record after the fact can understand what happened and why.

For the record to be useful rather than overwhelming, it must be legible, not merely complete. Routine activity must be distinguishable from notable activity. Outcomes must be visible at a glance. The record must serve both as forensic surface for the human approver reviewing later and as operational surface for anyone watching the system work in real time.

For visibility to extend to the system's edges, the system must fail loudly rather than silently. Where the system is uncertain, missing data, or out of its depth, it must escalate rather than guess. The default behaviour for "I do not know what to do here" must be to ask, not to act.

---

## The coordinator out of the bottleneck

For Padea to scale without the catering operation becoming a bottleneck, the coordinator's routine catering work must not scale with the number of sessions. The coordinator currently spends meaningful time each week on composing emails to caterers, guessing at quantities and menu choices, fielding parent emails about absences, and managing the flow of operational data. The system must take the routine flow off their desk while leaving them in clear ownership of decisions that genuinely require their judgement.

For routine work to be taken off their desk, the system must own end-to-end routine order generation including item selection, quantity calculation, and outbound communication. The coordinator must not be in the loop of a routine order; they should see catering activity only when something requires their judgement.

For the coordinator to stay in ownership of the decisions that do require their judgement, the system must escalate where decisions could damage business relationships, where outcomes are commercially significant, where situations are unpredictable enough that automated judgement cannot be trusted, or where the system encounters cases it was not designed to handle. This principle covers, among other things: caterer rotation proposals, contract or pricing anomalies, capability changes affecting a caterer's continued service, commitments to extras beyond what routine order construction would commit, dietary cases where no menu item satisfies a student's requirements, and any failure mode the system has not been designed to handle autonomously.

For the dividing line between routine and non-routine to remain accurate over time, the system must track its own escalation patterns. As cases accumulate in the operational record, the human approver gains evidence about which categories could be handled automatically in future configurations and which must remain human-judged.

---

## Graceful failure

For the system to remain trustworthy across failure modes, a failure of one part must not cause a failure of the system's key logic or requirements. Bugs and partial failures are inevitable; silent destruction of operational integrity is not.

For failure modes to be safe, they must be loud, surfaced with adequate context, and never silently destructive. Where the system cannot complete a workflow, the partial state must be captured explicitly so a human can resume from the failure point. Where the system encounters input it does not recognise, the input must be captured verbatim before any interpretation is attempted, so interpretation failures do not lose data. Where the system runs longer than expected, it must time out and escalate rather than hang. Where systems the agent depends on are unavailable, the agent must degrade to a reduced mode that preserves operational continuity rather than failing entirely.
