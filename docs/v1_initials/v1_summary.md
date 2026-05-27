# V1 Summary — Padea Operations Agent

**Purpose:** A walk-through of how V1 of the operations agent runs across a typical week and a typical term. The reader should finish this document understanding what the system does, in what order, and why each component exists. Technical detail lives in `schema.md` and `decision_register.md`; this is the narrative.

**Version:** V1, ambitious initial pass.

---

## What V1 is

The system is an AI agent that owns the weekly catering operation. It composes orders for every caterer-school combination, handles disruptions (absences, exclusions, walk-backs), tracks satisfaction through student ratings, and surfaces anything that needs human judgement as an escalation. A human approver — Padea's operations coordinator — remains in the loop for non-routine decisions, but routine work is the system's. The goal is to make catering a re-enrolment advantage rather than a back-office burden, and to do it visibly enough that anyone reading the system's record can reconstruct why each meal arrived.

V1 is the ambitious version. It includes mechanisms that V2 will examine and likely strip on cost-benefit grounds: an absence-prediction model, a per-parent false-notification tracker, a tutor-meals buffer, scorecard snapshots for each caterer, and others. These are included because they are individually defensible from the requirements — not because they are necessary for the system to function. The V2-then-V3 work cuts and reinstates so the final design is justified rather than assumed.

## Term start: preference capture

At the start of each term, before any session runs, the system contacts every parent of every enrolled student. The contact carries a list of menu items their child could be served — already filtered to exclude anything incompatible with the child's recorded dietary requirements. The parent marks each item as acceptable or not, with a comment field for context. These selections form the per-student menu universe for the term.

For students enrolling mid-term, the term-start flow is invoked immediately on enrolment. The student's first session is held in a manual-decision state until the parent responds or a configurable timeout passes. *(This is acknowledged as a weak point of V1 — the term-start framing was not designed with mid-term joins as a primary case. V3 addresses it more cleanly.)*

The parent-selected universe is the universe from which the student picks each week. The intent is straightforward: parents do not micromanage every meal, and students get meaningful weekly choice within a parent-approved set.

## Weekly composition: Monday for the following week

Each Monday, the system runs the week's order composition. The full week of upcoming sessions is in view at composition time — the order is not a per-session document but a per-caterer-per-week one, reflecting how caterers actually plan. With the full week visible, the minimum-order-quantity check happens once against full weekly demand rather than scattered across sessions.

Composition runs in two phases. The first phase reserves a meal for every student with a dietary requirement, drawn from the items the parent marked as acceptable for that student. Dietary meals are committed before any economic reasoning enters the picture; the safety floor cannot be traded against budget. The second phase fills the remaining slots from the standard menu pool, drawing on each student's weekly selection (where one has been submitted) and the system's variety record (which tracks what each student has eaten over recent weeks, so palate fatigue is actively prevented).

Alongside the chosen composition, the system computes alternative cost scenarios — what the same week would cost at one variety level higher or lower, what meeting the next MOQ tier would cost in surplus meals. These scenarios are stored with the order as decision-support data. The operator sees not just the chosen composition but the trade-offs that produced it.

The composed order includes three margin components beyond the confirmed attendance count: an operational margin of two meals per session, a per-session tutor-meals buffer for the tutors managing the session, and a walk-up prediction adjustment computed from per-school history and calendar features (exam week, end of term, public-holiday-adjacent days). The walk-up prediction itself is a stored model output with full feature snapshot, so a future investigator can reproduce the reasoning.

## Mid-week: absences arrive

Most absences arrive by parent email. The agent reads these from the incoming-emails feed, classifies each by intent, captures the raw content verbatim before any interpretation, and produces a canonical absence record per (student, session) pair. Duplicate notifications from anxious parents are folded into the same canonical record, with the chain of raw notifications preserved.

An absence that arrives before the order has been sent reduces the order's meal count for that session. An absence that arrives after the order has been sent does not amend the order — the caterer is already preparing the meal — and instead tags the session for walk-up handling. The operational margin and the walk-up prediction together absorb late absences without requiring the caterer to revise their preparation.

Walk-backs follow the same logic. If a parent emails a reversal of a previous absence, the absence record's walk-back timestamp is set; if the walk-back arrives post-send, the session's walk-up tag is removed and the previously-reserved meal is restored to its student. A walk-back of a walk-back creates a new absence record rather than re-flipping the original — preserving the history.

Per-parent statistics accumulate continuously. Parents whose absences are frequently walked back, or whose absent students frequently appear at the session anyway, are flagged in a notification-reliability surface that feeds the walk-up predictor and surfaces patterns for operator outreach.

## Mid-week: exclusions and edge cases

Exclusions — whole-session cancellations, year-level partial exclusions, or subject-specific cohort cancellations — enter the system through an operator form. The system receives exclusions that have been read and entered by a human; it does not attempt to disambiguate "Year 12 are on camp Tuesday" from free-text emails.

A whole-session exclusion overrides the dietary safety floor for that session: nobody is being served because the session is not running. A partial exclusion sizes the order against the remaining cohort with an additional buffer to absorb students who attend despite the exclusion. A whole-session cancellation arriving after the order has been sent escalates immediately — three pre-drafted response options accompany the escalation (recall, accept and donate, pay regardless), each with the financial figure attached.

## End of session: ratings flow back

After each session, the system sends each student a short rating link via the parent's contact. The student rates the meal received on a five-point scale with an optional comment. The comment runs through a separate LLM extraction step that pulls per-dimension signal — taste, portion, temperature, presentation, freshness — into structured form, alongside the raw comment.

Ratings are normalised against each student's own baseline (some students rate harshly, others generously; the deviation carries the signal). They are weighted by submission timing (ratings within two hours of session end count fully; later submissions decay to a floor). The normalised, weighted ratings feed each caterer's rolling quality score.

A session reconciliation record captures what actually happened: how many meals were eaten, how many walk-ups occurred, how many meals went unused. This is the ground-truth feed for the margin model, the walk-up predictor, and the per-parent reliability stats — all of which improve as reconciliation data accumulates.

## Mid-week to end of week: caterer relationships

Each caterer has a scorecard, snapshotted on a weekly cadence, accessible to the caterer through a tokened URL. The scorecard shows the caterer's own aggregate score over time, per-item scores, per-dimension trends, comparison to their own historical baseline. Individual student identities and other caterers' scores are never exposed. The existence of the scorecard is the discipline mechanism: a caterer who knows they are being measured and shown the result will adjust without explicit threats.

Internal to Padea, a comparative dashboard surfaces all caterers side-by-side: aggregate score, trend, per-school score, MOQ utilisation, cost-per-meal-delivered, capability coverage, recent decline signals. This is the surface for rotation conversations.

A caterer's quality is monitored continuously. A rolling four-week mean compared against the prior twelve weeks, dropping more than one standard deviation, AND with the absolute current score below a per-caterer configured floor, triggers a rotation proposal. The proposal includes comparative analysis of eligible alternative caterers, pre-drafted enquiry emails to alternatives, and a pre-drafted notification to the current caterer. The operator approves, dismisses with reason, or modifies. Rotation is never automatic; the system surfaces the need and prepares the action.

Caterer non-response handling runs in parallel. Each order has an expected confirmation deadline computed from the caterer's stated lead time. When the deadline passes without confirmation, an escalation raises with three pre-drafted actions — follow-up to the order-taker, call-script for direct contact, draft enquiry to an alternative caterer.

## End of term: stocktake

At term end, the system produces a term-level report consolidating: total meals delivered, total students served, average ratings per caterer, decline signals raised, escalations resolved, costs against budget, MOQ shortfalls, dietary trend observations across the network. The report is the input to caterer relationship discussions and to the V2/V3 design decisions about which V1 mechanisms have earned their place.

Several V1 mechanisms produce data here that explicitly questions their own value. The absence prediction model's performance against actuals is reported. The tutor-meals buffer's utilisation rate is reported. The order economics simulations are reviewed against the choices the operator actually made (did they ever revise based on the alternatives?). These reports feed V2's cut decisions with evidence rather than guesswork.

## Throughout: visibility

Every decision the agent makes — every tool it calls, every rule it applies, every branch it considers — is recorded. The records form a tree: top-level decisions spawn sub-decisions, tool calls, and results. Each run produces an HTML demo surface showing the run's reasoning chain, colour-coded by severity and outcome.

Escalations are first-class records with lifecycle states (open, acknowledged, in-progress, resolved, superseded). They deduplicate by match key — a recurring condition like a weekly MOQ shortfall doesn't produce a fresh escalation each week; it produces one escalation with a recurrence count. Severity is assigned per instance rather than per type, because the same kind of escalation can carry very different urgency depending on context.

History tables capture every change to mutable entities — enrolments, capabilities, menu items, caterer records — with the actor responsible (system, user, agent) and the cause linked to the run and decision that produced the change. The "why did this change?" question is always answerable.

## What V1 is not

V1 is not minimal. It includes mechanisms that V2 will strip. It is not the final design; it is the design that V2 will examine pedantically and V3 will partially restore. The mechanisms most likely to be cut — ML absence prediction, the tutor-meals buffer, per-parent reliability tracking, the order economics simulation, scorecard snapshots — are not defects of V1. They are V1's contribution to the cut-then-restore journey. V3 will be more honest because V2 had real material to argue against.
