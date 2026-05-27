# Summary — PADEA Catering Agent V3

**Purpose:** What V3 does, in plain terms, read chronologically. The reader should finish this document understanding how the system runs from the start of a term through to a typical caterer rotation. Decisions and trade-offs live in `v3_decisions_ledger.md`; the data model lives in `schema.md`.

**Compiled:** 27 May 2026
**Companion documents:** `v3_decisions_ledger.md`, `schema.md`, `edge_cases.md`.

---

## What V3 is

V3 is a fully operational AI agent that runs Padea's catering workflow end-to-end. It sends real emails via Gmail, receives and classifies real replies, composes per-session orders for every caterer-school pair, collects post-dinner feedback from tutors and session managers, monitors caterer quality over time, and initiates the replacement process when quality declines. A human operator remains the final authority on commercial decisions — every email that changes a caterer relationship requires one-click approval before it sends. Everything else is autonomous.

The system runs five to seven times per week, triggered by a cron-style scheduler. Each run begins by reading new emails, determines what sessions are due for orders, composes and sends them, processes any feedback or replies that have arrived since the last run, evaluates quality signals, and regenerates the HTML decision log. The database is Supabase Postgres; the agent's reasoning model is Claude Sonnet 4.6.

---

## Term start: parent preference capture

Before the first session of a new term, the system sends every enrolled student's parent a preference email. The email carries two tasks.

First, the parent picks dietary attributes for their child from an extensible vocabulary — no pork, no seafood, halal, vegetarian, mild not spicy, and so on. These tags are durable: they stay attached to the enrolment record and survive caterer changes, because they describe the child, not any one menu.

Second, from the current caterer's menu already filtered by those dietary tags, the parent ticks every meal their child would be happy to receive. The framing is explicit: "select the meals we'll cycle between for your student." There is no prescribed number — a child who is happy with two meals ticks two; a child with broad taste ticks ten. The result is a variable-size approved set that honestly represents the parent's permission, not an arbitrary cap.

The email offers a third response: a single-click opt-out that marks the child as not participating in catering for the term. The opt-out is presented at the same level as the main submission, not hidden. A parent who makes no response is chased once with a reminder; after that the case escalates to the operator for manual handling.

New enrolments at term start go through the same parent email. Mid-term enrolments are different — the operator captures dietary tags and the approved meal set directly, composes the child's first-session meal manually, and enters the child into the system with full data already in place. From the following session onward the child is in the rotation like any other enrolment.

---

## Each run: reading new mail

Every agent run starts with a Gmail API poll. The system reads every message that has arrived in the dedicated Gmail account since the last run and classifies each one.

**Parent absence notifications** create an absence record tied to the relevant student and session. The student is excluded from the next order composition for that session. An absence that arrives before the T-72hrs order has been sent prevents the meal from being ordered at all. An absence that arrives after the order has gone is recorded for audit but does not amend the order — the caterer is already preparing.

**Caterer order confirmations** update the status on the matching order record.

**Parent enrolment responses** — dietary tags and approved meal set submissions — update the student's enrolment record and admit the student to the rotation from the next session run.

**Caterer price-change notifications** — a caterer replying to an order email to say a price has changed — are classified as a structured escalation type. The operator is surfaced the detail; they update the affected menu items manually. No auto-update.

**Unclassifiable inbound** — anything the agent cannot confidently route, including complaints or unusual correspondence — fires an escalation. The operator sees the sender, subject, and timestamp and reads the message directly in Gmail. No general inbox table exists; unclassifiable messages live in Gmail and the escalation carries enough context to find them.

Each inbound message is deduplicated by its Gmail message ID, so a run that fires shortly after a previous run does not double-process the same emails.

---

## T-72hrs: per-session order composition

The binding trigger for order composition is exactly 72 hours before each session. A Monday session gets its order at Friday 3 PM. A Tuesday session at Saturday 3 PM. Wednesday at Sunday 3 PM. Thursday at Monday 3 PM. Each caterer-session pair gets exactly one order email at that moment — there is no provisional-then-final distinction. The email is the contract.

**Building the cohort.** The system queries all active enrolments for the session's date. Active means: `current_period_start_date` on or before the session date, `current_period_end_date` null or in the future, and `opted_out_of_catering` false. Students with absence records for that session are removed. Students whose sessions are excluded for that date (school holidays, whole-school cancellations, year-level exclusions) are removed.

**Choosing meals.** For each remaining student, the system checks whether a tutor has filed a per-session meal request for that student via the tutor app. If one exists, the student gets that meal — the request is a one-off override for this session only, drawn from any meal on the current caterer's menu the student can safely eat. If no request exists, the system selects the next meal in the student's rotation. The rotation follows the caterer's canonical meal order — a popularity-ranked sequence of all menu items computed at term start — advancing through whichever items from that order appear in the student's approved set, always picking the one least recently served to that student.

Dietary-restricted students always get a dietary-safe meal, whether selected by request or by rotation. The dietary tags are a hard floor at every stage of composition.

**MOQ.** The minimum order quantity check is assessed weekly rather than per-session, in the Monday consolidated summary. If a week's total order with a given caterer falls below their MOQ floor, the system pays the difference and fires an informational escalation so the operator is aware. The composition itself is never padded or re-optimised to clear MOQ — the order reflects exactly what students need.

**The order email.** The email body lists each allocated meal with the student's name beside it ("Chicken Caesar — Sam Smith. Pasta — Lily Chen. Vegetarian curry — Marcus Patel…"), followed by per-session meal totals and a predicted cost line: the expected total based on current menu prices, including the delivery fee. This predicted cost is visible to the caterer on every order email, creating a soft verification channel — if pricing has changed, the caterer's reply flagging the discrepancy becomes a structured escalation.

The email is sent via the Gmail API. The outbound record is written to the `outbound_emails` table with its full rendered body, status, and a link back to the agent run that produced it. Send failures are caught explicitly: the outbound row marks as failed, an escalation fires, and the operator decides whether to retry, send manually via Gmail, or skip.

---

## After each session: tutor and manager input

After dinner at every session, tutors open the app and fill one box per student in their group. The meal the student received is pre-loaded. The tutor enters a 1–5 score the student verbalised — after probing rather than accepting the first number. A free-text comment captures plate behaviour, swaps, or anything notable. This is one extra box per student alongside the session notes tutors are already completing.

The same box exposes a meal request picker for the next session: a tutor can file a specific meal request on behalf of a student, drawn from any meal on the current caterer's menu the student can safely eat. The request is not constrained to the student's parent-approved set — it is a one-off signal of what the student actually wants. Filed after the next session's T-72hrs order has already gone, the request defers naturally to the session after that.

For opted-out students, the tutor sees a different surface: a small opt-out label in place of the rating box, plus a single checkbox — "student wishes to opt back in for meals." Ticking and submitting fires an autonomous email to the parent, identical in structure to the original term-start preference email. No operator approval is needed because the email is parent-facing and carries no commercial-relationship risk. The system tracks that this email has gone so repeated checkbox ticks by the tutor do not spam the parent — a second send is blocked until the opt-out period closes and a new one opens. Recurring ticks without a parent response accumulate as a soft signal in the weekly report.

The session manager fills out their own report alongside. It includes a session-level 1–5 food score, a structured checklist (food on time, anything visibly wrong), a free-text comment, a count of meals left over, and the names of specific students who did not eat. The manager's view is the cross-check on tutor-collected data and the primary source for whole-session signals.

If a tutor does not fill in a student's post-dinner box, the system records the rating as missing — not as zero — and excludes it from the rolling mean. A pattern of missing data on a tutor or session is itself a soft signal visible in the weekly report.

---

## Each run: quality monitoring

After ingesting feedback, every agent run evaluates three single-session auto-escalation conditions:

1. A manager score of 1 or 2 on any session → operator reviews immediately.
2. A student-average score of 1 or 2 on any session — even if the manager did not flag it — → same treatment.
3. Tutor scores of 1 exceeding a configurable percentage of total tutor scores in a rolling window → a pattern escalation fires.

These escalations are parallel awareness, not replacements for the rolling mean. Extreme scores stay in the rolling average because they are real data.

The per-caterer rolling quality score is an unweighted four-week mean of all filled ratings — tutor and manager scores combined — per caterer. It is computed on every run, stored, and surfaced in the decision log and the weekly cross-school report.

---

## Monday 3:30 PM: weekly consolidated summary

Every Monday at 3:30 PM the system produces one summary email per caterer covering that caterer's full week across all their Padea sessions. The summary aggregates total meals, applies the MOQ floor if the weekly total fell short, adds the GST line according to the caterer's pricing flags, and states the expected total for the week. This is the canonical spending document — the figure against which payment crystallises and against which any invoice dispute is resolved. The per-session predicted totals on individual order emails provide the line-item detail behind it.

The weekly report regenerates alongside the consolidated summary. It is an HTML document — a cross-school view showing every caterer's rolling quality score, their trend over the term, any recent escalations, per-caterer cost trajectory, and opt-out rates per school. The operator reads it as a slow-drift awareness surface rather than as a real-time dashboard.

---

## Sustained decline: the rotation chain

When the four-week rolling mean for a caterer drops materially below the prior twelve-week mean and also falls below an absolute configured floor, the system fires a sustained-decline escalation. It drafts a polite warning email to the incumbent caterer — naming the quality drop and stating what will happen if scores do not recover. The email sits in the outbound queue; it does not send until the operator approves with one click.

If the operator judges that scores have not recovered after the warning window — this is a manual call; there is no automatic re-trigger — they ask the system to fire a Request for Proposal. The system queries all caterers whose home postcode is within the school's postcode radius (using each caterer's stored maximum delivery distance), excludes the incumbent, and drafts a competitive RFP email to each eligible caterer: can you cover this school on this day starting approximately two weeks from now, and if not already on file, what are your current prices and lead time? The RFP goes to all eligible caterers simultaneously. The operator approves the recipient list and draft before it sends.

Responses arrive as inbound emails, classified and surfaced in the decision log. For each caterer that responds yes, the system displays: their name and contact, their stated start date, their per-meal price, their delivery fee structure, and a projected weekly cost for this school's cohort — computed as cohort size times per-meal price plus delivery fee, with the MOQ floor applied. The operator picks one respondent. The remaining respondents receive a courtesy reply drafted by the system and approved by the operator before sending.

Once the operator selects a new caterer, the system drafts a cancellation notice to the incumbent — two weeks' notice, professional tone — and queues it for operator approval. The incumbent continues to serve while the new caterer is onboarded.

---

## Caterer change: preview week and preference reset

The new caterer's first week is a preview week. The system flags the entire week's order as an escalation requiring operator action — the operator composes that week's order manually, mirroring pre-system operation. Dietary-restricted students still get a dietary-compatible meal auto-chosen even in the preview week.

During or after the preview week, tutors use the app to reset each student's approved meal set. They read the new caterer's menu options to the students in their group — informed by what students saw, ate, and discussed that first week — and record which meals each student would be happy to receive. There is no fixed number; the approved set is whatever the student would actually accept. Old approved sets are archived rather than deleted, in case the school ever reverts to the previous caterer.

The canonical meal order — the popularity-ranked sequence used to drive rotation — is recomputed at caterer change using the newly-captured approved sets. From the second week with the new caterer, the standard rotation resumes: least-recently-served from each student's approved set, in canonical order, with per-session meal requests overriding for individual students.

Parent involvement on a caterer change is zero. The tutor-led preference reset is the standing process, and dietary tags remain unchanged because they describe the student, not the menu.

---

## Enrolment lifecycle: students joining, leaving, and returning

Each enrolment row carries three dates. `original_start_date` records when the student first ever enrolled with Padea and never changes. `current_period_start_date` records the start of their current active period — the same as the original start on first enrolment, updated if they return after a gap. `current_period_end_date` is null while the student is active and set when they leave. The question "was this student active on this date?" is always answered by comparing those dates against the date of interest — never from a stored status field.

When a student withdraws, the operator sets their `current_period_end_date`. From that date onward the student is excluded from all order composition. Their history — orders, feedback, preferences — remains fully queryable. When the same student returns in a later term, the operator updates `current_period_start_date` to the new join date and clears the end date. `original_start_date` is untouched; the full Padea history of that student sits under the same row.

Every agent tool that touches enrolment data takes the relevant date as a required parameter. Order composition queries enrolment as of the session's date. The weekly report queries as of the report date. Incident investigation queries as of the incident date. There is no implicit "as of today" default — the date is always explicit.

School holidays and term breaks are handled as full-school exclusions in the exclusions table. A two-week holiday across all schools adds roughly sixty exclusion rows — one per school per session day per week — inserted by the operator in bulk via a one-off script at term end. The system runs continuously across terms; terms are a property of the exclusion calendar, not of the schema.

---

## Throughout: visibility and escalation tiers

Every tool call the agent makes, every decision, and every escalation it surfaces is recorded as a step on the agent run, with the full input, output, and reasoning captured. After every run — five to seven times per week — the HTML decision log is regenerated from the database. It is a static file that opens in any browser and shows everything the agent did, grouped by week, with urgency-sorted sections at the top of each week.

Every escalation carries one of three urgency tiers applied consistently across all escalation types.

**Urgent** items are gating something. Until the operator acts, an email does not send, an order does not compose, a caterer is not engaged. Examples: a warning email awaiting approval, an RFP awaiting approval, a Gmail send failure requiring a retry decision, an unclassified inbound requiring routing. These are what the operator works first when they open the decision log. The log renders urgent items in red, sorted to the top of each week group.

**Notable** items are worth the operator's attention but not blocking. Examples: a manager score of 1 or 2 on a session, an MOQ shortfall recurring at the same school across consecutive weeks, a tutor-1-pattern firing on a caterer. The operator reads these, makes notes, and decides if they warrant follow-up. Rendered in amber.

**Informational** items are the audit trail. Examples: an order sent successfully, a parent opt-out recorded, a caterer order confirmation received, a one-off MOQ shortfall paid and noted. No action expected. Rendered in green.

A summary count at the top of each run — "3 urgent, 4 notable, 12 informational" — lets the operator know the scale of what is waiting before they scroll. There is no acknowledgement field and no "open vs. closed" state on escalations. When the operator handles something, the next run reflects the result in the underlying data, and the log renders the updated state. The database is the source of truth; the decision log is a view onto it.

---

## How V3 is shaped

**Database.** Supabase Postgres, connected via the standard Postgres connection string. The schema is defined in SQL DDL files in the repo, giving reproducibility and a Postgres-native database accessible via the Supabase project link.

**Tool layer.** Typed Python functions wrapping deterministic database operations — `compose_session_order`, `caterers_within_range`, `project_weekly_cost`, `gmail_send`, `gmail_poll_inbox`, `get_enrolments_for_session`, and so on. Tools are called by the agent; they do not invoke the LLM. They are the unit-testable layer.

**Agent.** Claude Sonnet 4.6 invoked via the tool-calling API. The agent's `main()` inspects the current time on invocation and determines what the run should do: compose a T-72hrs order if one is due, generate the Monday consolidated summary if it is Monday 3:30 PM, or run inbound polling and quality evaluation only if neither trigger applies.

**Email.** All outbound email goes via the Gmail API in production mode. In demo mode, a single environment variable (`EMAIL_MODE=demo`) rewrites every outbound recipient to the developer's address, with the original intended recipient preserved in the email body and the database row. One config flag separates demo from production; no code changes.

**Decision log.** A static HTML file regenerated after every run from the `agent_runs` and `agent_steps` tables. Events are grouped by week, sorted within each week by urgency tier descending, then by step index. The log is the primary operator surface; the weekly cross-school report is the secondary one.

---

## How V3 will be demonstrated

The demo runs against a live Supabase Postgres database and a real Gmail account. Judges see real emails arrive in the Gmail inbox as the agent composes and sends them. The demo includes the operator replying to a system email from their phone — the agent picks up the reply on the next run and processes it. The system is not simulating email; it is using it.

Seed data covers six schools, multiple caterers, a full term's enrolment cohort, recent absences, and school-holiday exclusions. Staged inbound emails are designed to exercise the classification logic: a parent absence notification, a caterer confirmation reply, a caterer price-change notification, and one unclassifiable message intended to escalate. The decision log opens in a browser after the demo run and walks through every step the agent took, with urgent items surfaced at the top.

The Supabase project URL is the "Database Access" deliverable — a live Postgres instance with the real schema, accessible to judges directly. The agent code and decision log HTML are the build artifact deliverables.
