# Requirements — Padea Operations Agent

**Purpose:** What the system must do, derived from the operational reality Padea operates within. Each requirement is justified by the one above it. Decisions about *how* requirements are satisfied live in the decision register, not here.

**Compiled:** 25 May 2026
**Companion documents:** `data_observations.md`, `assumptions.md`, `decision_register.md`, `schema.md`.

---

## How to read this document

The requirements are written as a prose tree. The top-level claim is what Padea ultimately needs from this system. Each subsequent paragraph derives its requirements from the one above it. The system's necessary capabilities appear where the chain of reasoning has reached the level of "the system must be able to do X."

Where a requirement states a necessary outcome or capability, *how* the system delivers it is not specified here. Implementation choices are decisions and live in the decision register.

---

## The system's job

Padea is a tutoring business whose continued operation depends on families choosing to re-enrol their children term after term. Re-enrolment is not a decision parents make based on tutoring quality alone — it is a decision they make based on whether the whole experience, including the parts adjacent to tutoring, is something they want to keep paying for. The dinner break is one of those adjacent parts. Done well, it contributes to students enjoying their time at sessions, which contributes to students wanting to return, which contributes to families re-enrolling, which contributes to revenue.

The system exists to make catering an advantage to Padea rather than a liability — an operational surface that contributes positively to the business rather than one that consumes effort while producing complaints. A coordinator emailing caterers each Thursday and making educated guesses at meals is the current state and is not sufficient. The system must do better than that, and must do so reliably as the business grows.

For catering to be an advantage rather than a liability, several conditions must hold simultaneously. Students must receive meals when sessions run. The meals must not harm them. The meals must be ones students want to eat. Quality must remain high over time. Variety must be sufficient. The operation must be visible enough that problems are detected and acted on. None of these conditions can be sacrificed for others; together they form the operational floor on which catering's contribution to re-enrolment rests.

The system must achieve these conditions without consuming a coordinator's time in proportion to the number of sessions. If catering remains hand-operated, doubling the number of partner schools doubles the coordinator's catering workload, which is the textbook definition of a bottleneck. The system must therefore own the routine work and surface only the decisions that genuinely require human judgement. When the human approver (the coordinator or another nominated supervisor) is consulted, it must be for decisions where their judgement adds value.

---

## The non-negotiable safety floor

The system must never serve a meal that violates a student's documented dietary requirements. A vegetarian student cannot be served meat. A nut-allergic student cannot be served a meal that contains or contacts nuts. A halal-observant student cannot be served pork. This is a safety concern, and in the case of allergies, a medical one.

This requirement sits above all others. Where other requirements come into conflict with each other, the system must reason about tradeoffs. The dietary safety floor admits no tradeoffs.

Every student's dietary information must be captured before any meal is matched to them. Where dietary information is missing or ambiguous, the system must not proceed on assumption.

Matching between students and menu items must be reliable. Where a menu item's dietary properties depend on interpretation, the interpretation must be made and recorded before the matching step, not derived ad-hoc at the point of decision.

Where no available menu item satisfies a student's dietary requirements, the system must escalate to the human approver rather than substitute silently. A student arriving to find no meal made for them is a worse failure than the system flagging an unmet requirement in advance.

---

## Reliable meal delivery

A meal received late is, for the duration of the dinner break, indistinguishable from a meal not received. A meal received at the wrong school is, for the affected students, not received. A meal sent with the wrong count is, for the students past the count, not received.

The system must own the logistics of each order from generation through delivery confirmation. It must generate orders with correct quantities for the correct session, address each order to the correct caterer with the correct contact, send each order with adequate lead time for caterer preparation, and confirm both that the caterer received the order and that delivery occurred at the session.

Where any step in this chain fails or stalls, the system must surface the failure with enough lead time that a human can intervene before students arrive expecting food.

The system must handle the operational reality that caterers do not always respond promptly. Where a caterer has not confirmed receipt of an order in adequate time before the session, the system must escalate with viable options for the human approver, including contacting the caterer directly, drafting an enquiry to an alternative eligible caterer, or proceeding under explicit human direction.

The system must know which caterer is currently committed to which school on which day, which alternative caterers are eligible to serve each school, each caterer's minimum order quantity rules, each caterer's delivery fee structure and tax treatment, and each caterer's lead time requirements. None of these can be inferred at runtime; they are facts the system must hold and keep current.

When a session is cancelled in its entirety, no order must be sent. When a session is partially cancelled — for instance when specific year levels are excluded due to a camp or school event — the system must size the order to the remaining cohort while accounting for the operational reality that some excluded students attend anyway.

Absences within an attending cohort must be handled. Absences notified in time to affect the order must reduce the order's quantity; absences notified after that point must not, because amending caterer orders late in their preparation is disruptive and the system must instead absorb late changes through its own margin. Where a student notified as absent attends anyway, a meal must still be available. The system must capture such walk-up events so that recurring false-absence patterns can be identified and addressed.

The system must include operational margin to absorb the inherent unpredictability of session attendance — students who came despite an absence notification, students who didn't come despite no notification, visitors present unexpectedly. The size of this margin must be tractable in the order's economics but adequate to avoid routine shortfalls. Where the margin is regularly exhausted or regularly unused, the system must surface this as a signal for re-sizing.

---

## Meals students want to eat

A meal a student does not want is, from the satisfaction perspective, a meal not eaten. A session of students who did not enjoy their food does not contribute to the satisfaction loop the system exists to support. The system must therefore deliver meals students actually want, within their dietary constraints — not merely meals that are dietetically compliant.

# NOTE - a meal not eaten should not serve as the criteria for a meal not being good. we must think of another system, students dont eat meals all the time for a multitude of reasons; not hungry, brought food, pizza night at home etc. 

Student preferences are not directly observable by the system and are not constant across students or over time. The system must therefore have a mechanism for understanding what each student wants and must keep that understanding current. The mechanism must scale to hundreds of students across multiple schools without depending on every student providing input every week. 

The mechanism must produce per-student data, because cohort averages are not adequate for matching individuals. It must accommodate students whose preferences change over time. It must distinguish students who genuinely have preferences from students who are content with whatever is provided, so that responsiveness from a subset of households does not bias outcomes for the rest.

Where the system cannot satisfy a student's preferences within available menu items and caterer constraints, the system must escalate with sufficient detail for the human approver to make a decision: which students are affected, what alternatives are available, what trade-offs exist.

The system must not unilaterally serve a student a meal the student or their household has not accepted as a possibility.
## NOTE; i understand what this is referencing - the idea we had that the parents choose the options and the students choose one from these options each week. This is unclear in this document and feels random. make clearer, however is it an actual requirment. 

---

## Sufficient variety

Even when meals are technically acceptable, students experience palate fatigue when the same items recur. The system must therefore vary menu choices across weeks for each cohort, drawing on memory of what each cohort has been served and weighting away from recent items.

Variety is constrained by caterer reality. Caterers have finite menus and minimum order quantity rules that can force fewer item types per order. The system must respect these constraints while doing the best it can within them. Where a school's caterer cannot offer enough variety to avoid recent repeats, the system must recognise this as a signal worth surfacing.

## Note; the system doesnt have to vary choices and weigh out recent items, it simply has to prevent fatigue (req 1) and then have a system that does such. this requires knowing multiple meal options for each student, which requires asking them somewhere or somehow which meal options they like, understand the requirement logic. in fact we were over specific it doesnt require asking them it requires finding out which may not involve asking them, might track something else. you see the logic. 

---

## Quality maintained over time

Caterer quality is observed by the business to decline over time once a caterer is comfortably established. The system must assume this will happen and detect it.

## NOTE; the system must prevent this... lead into each req. to prevetn this the system must collect quality analysis continuously to gauge the over time degradation etc. 

The system must collect quality signals continuously, aggregate them across time windows long enough to filter session-to-session noise, and surface decline early enough that the business can act on it before students suffer prolonged poor service.

Quality signals must come from multiple sources rather than any single channel. Reliance on any one source — student input, manager observation, parent complaints — creates a system that fails when that source goes quiet.

## NOTE; no when it falls below a quality it doesnt neccerarlly have to surface alternatives, it needs to seek to fix this... meaning the system requires an ability to fix this piror to it needing fixing, in adcance. this means the system should have an in built way of motivating resturatns to maintain wuality, this could (could is not a req but our idea - somewhat a decision) involve the cateres being aware prior to working that if wuality drops they will lsoe the shift, and it will be given to another caterr. this meas the system requries the knowledge of what caterer can do what day etc. does this logic make sense. 


When aggregated quality signals fall below an acceptable level for a caterer, the system must surface alternative eligible caterers and draft a swap proposal for the human approver to review. The system must not unilaterally rotate caterers; rotation is a relationship and commercial decision belonging to the human approver. The system's job is to detect the need, propose the action, and execute the action once approved.

The leverage in the caterer relationship is not coercion. It is the combination of visible measurement and the existence of alternatives. Caterers who know their performance is measured and that alternatives exist will tend to maintain quality more reliably than caterers who do not. The system must therefore make measurement visible and keep the alternatives current.

Where multiple caterers are eligible to serve the same school, the system may use this redundancy proactively — periodically suggesting a trial of an alternative caterer at a low-stakes session to refresh quality signals — rather than only reacting to decline. The system must surface such proactive suggestions for human approval rather than initiating them autonomously.
## NOTE; what is a low stakes session,  explain in the chat to me and we will decide to keep ore remove. 
---

## Visible operation

## this one is worded much better, first premise, second premise etc first principles argument. 
A system that operates correctly but opaquely is, when it occasionally fails, indistinguishable from a system that operates incorrectly. The human approver cannot supervise what they cannot see; future operations staff cannot trust what they cannot audit.

The system must produce an inspectable record of every meaningful decision it makes. Each agent run, each decision within a run, each tool the agent invokes, each rule it applies, each escalation it raises must be captured with enough context that a human reading the record after the fact can understand what happened and why.

The record must be legible, not merely complete. Routine activity must be distinguishable from notable activity. Outcomes must be visible at a glance. The record must serve both as forensic surface for the human approver reviewing later and as operational surface for anyone watching the system work in real time.

The system must fail loudly rather than silently. Where the system is uncertain, missing data, or out of its depth, it must escalate rather than guess. The default behaviour for "I do not know what to do here" must be to ask, not to act.

---

## The coordinator out of the bottleneck

The coordinator currently spends meaningful time each week on routine catering tasks: composing emails to caterers, guessing at quantities and menu choices, fielding parent emails about absences, managing the flow of operational data. The system must take the routine flow off their desk while leaving them in clear ownership of decisions that genuinely require their judgement.

The system must own end-to-end routine order generation including item selection, quantity calculation, and outbound communication. The coordinator must not be in the loop of a routine order; they should see catering activity only when something requires their judgement.

## NOTE; the system should notify a human for issues that could cause relational damage or are unpredictable or something else etc. this means decisions such as.... should cause an escalation. 
The system must escalate to the human approver for: caterer rotation proposals, contract or pricing anomalies, capability changes affecting a caterer's continued service, commitments to extras beyond what routine order construction would commit, dietary cases where no menu item satisfies a student's requirements, and any failure mode the system has not been designed to handle autonomously.

The system must not escalate for routine work it can complete from data and rules it already holds.

The dividing line between routine and non-routine is itself a property the system must maintain over time. As patterns of escalation accumulate in the operational record, the human approver gains evidence about which categories could be handled automatically in future configurations.

---

## Graceful failure

##NOTE; the system must not break its key logic or requirements due to a bug or system fail, therefore the failure modes must be loud etc. 
No system runs without error. The system must be designed such that its failure modes are loud, surfaced with adequate context, and never silently destructive.

Where the system cannot complete a workflow, the partial state must be captured explicitly so a human can resume from the failure point. Where the system encounters input it does not recognise, the input must be captured verbatim before any interpretation is attempted, so that interpretation failures do not lose data. Where the system runs longer than expected, it must time out and escalate rather than hang. Where systems the agent depends on are unavailable, the agent must degrade to a reduced mode that preserves operational continuity rather than failing entirely.

The dietary safety floor must hold even when other parts of the system have failed. Where the system cannot confidently match a student to a safe meal — for any reason — it must escalate and wait, regardless of how routine the surrounding workflow appeared.

---

## How we know the requirements are met

The system is judged not by whether it operates but by what it produces over time. The following outcome signals indicate the requirements above are being satisfied.

Coordinator time spent on catering should drop materially. The bottleneck requirement is met when the coordinator is doing meaningfully less routine catering work after the system has been operating for a few months.

Student-reported satisfaction with catering should trend upward over time, measured through whatever feedback channels the system maintains. Trend direction is the operative measure; absolute baselines are set when the system has been operating long enough to produce reliable data.

Caterer rotations should be triggered by data in the operational record rather than by anecdote. A rotation that the system did not propose first is evidence that the satisfaction loop failed to detect what humans detected manually.

Operational integrity should be measured by zero dietary safety incidents, zero sessions where students arrived to find no meal arranged, and zero escalations exceeding their expected response window. These are floor metrics, not aspirations.

---

## Operational assumptions
## NOTE; i want these in assumptions file but in a section in assumptions. matter of fact all of our assumptions should be in sections. 
The system relies on the following facts about the world it operates within. They are not requirements the system must enforce; they are conditions out of scope for the system to change.

The human approver is available within reasonable business windows to respond to escalations. Extended unavailability requires advance configuration of delegation.

Caterers respond to orders within a reasonable window in the routine case. The system handles non-response, but assumes the underlying business relationship is functioning. Chronically non-responsive caterers are replaced through the rotation mechanism rather than worked around indefinitely.

Students and households communicate primarily through email, or through channels forwarded into email by recipients before reaching the system. The system reads from an email surface.

Session managers submit feedback in a structured form. Where feedback originates in unstructured form, conversion happens upstream of the system.

Source data describing schools, sessions, students, caterers, contacts, menus, and rules is treated as accurate at ingest. The system does not second-guess input data on plausibility grounds. Anomalies are documented but not corrected.

--

## Out of scope
deleted out of scope stuff. not relevant. keep the doc simple. 