# Summary — PADEA Catering Agent V4

**Purpose:** What V4 does, in plain terms, read chronologically. The reader should finish this document understanding how the system runs from the start of a term through to a typical caterer rotation. Decisions and trade-offs live in `v3_decisions_ledger.md`; the data model lives in `schema.md`.

**Compiled:** 28 May 2026 (revised)
**Companion documents:** `v3_decisions_ledger.md`, `schema.md`, `edge_cases.md`.

---

## What V4 is

V4 is a fully operational AI agent that runs Padea's catering workflow end-to-end. It sends real emails via Gmail, receives and classifies real replies, composes per-session orders for every caterer-school pair, collects post-dinner feedback from tutors and session managers, monitors caterer quality over time, and initiates the replacement process when quality declines. A human operator remains the final authority on commercial decisions — every email that changes a caterer relationship requires one-click approval before it sends. Everything else is autonomous.

The system runs five to seven times per week, triggered by a cron-style scheduler. Each run begins by reading new emails, determines what sessions are due for orders, composes and sends them, processes any feedback or replies that have arrived since the last run, evaluates quality signals, and regenerates the HTML decision log. The database is Supabase Postgres; the agent's reasoning model is Claude Sonnet 4.6.

---

## Term start: parent preference capture

Before the first session of a new term, the system sends every enrolled student's parent a preference email. The email carries two tasks.

First, the parent picks dietary attributes for their child from an extensible vocabulary — no pork, no seafood, halal, vegetarian, mild not spicy, and so on. These tags are durable: they stay attached to the enrolment record and survive caterer changes, because they describe the child, not any one menu. The preference email also includes a free-text "other" field for parents whose child has a restriction that does not fit any structured tag — an unusual nut variant, an onion intolerance, a specific preparation restriction. Any submission containing an "other" entry triggers an operator escalation rather than processing automatically: the operator contacts the caterer to confirm which specific menu items are safe, then resolves the escalation and records the outcome on the enrolment. The student is still included in meal preference selection while the escalation is open; the operator's resolution determines which meals they can actually receive.

Second, from the current caterer's menu already filtered by those dietary tags, the parent ticks every meal their child would be happy to receive. The framing is explicit: "select the meals we'll cycle between for your student." There is no prescribed number — a child who is happy with two meals ticks two; a child with broad taste ticks ten. The result is a variable-size approved set that honestly represents the parent's permission, not an arbitrary cap.

The email offers a third response: a single-click opt-out that marks the child as not participating in catering for the term. The opt-out is presented at the same level as the main submission, not hidden. A parent who makes no response is chased once with a reminder; after that the case escalates to the operator for manual handling.

New enrolments at term start go through the same parent email. Mid-term enrolments are different — the operator captures dietary tags and the approved meal set directly, composes the child's first-session meal manually, and enters the child into the system with full data already in place. From the following session onward the child is in the rotation like any other enrolment. Mid-term enrolments arrive through varied channels — email, website enquiry, phone call, direct referral — making a single automated intake flow impractical. As the brief declares them rare, operator-handled intake is the correct trade-off; the flow could be automated in a later version if volume warrants it.

---

## Each run: reading new mail

Every agent run starts with a Gmail API poll. The system reads every message that has arrived in the dedicated Gmail account since the last run and classifies each one.

**Parent absence notifications** create an absence record tied to the relevant student and session. The student is excluded from the next order composition for that session. An absence that arrives before the T-72hrs order has been sent prevents the meal from being ordered at all. An absence that arrives after the order has gone is recorded for audit but does not amend the order — the caterer is already preparing.

**Caterer order confirmations** are recorded for audit only — the acknowledgement is logged as a step on the agent run. There is no order-status write.

**Parent enrolment responses** — dietary tags and approved meal set submissions — update the student's enrolment record and admit the student to the rotation from the next session run.

**Caterer price-change notifications** — a caterer replying to an order email to say a price has changed — are classified as a structured escalation type. The operator is surfaced the detail; they update the affected menu items manually. No auto-update.

**Unclassifiable inbound** — anything the agent cannot confidently route, including complaints or unusual correspondence — fires an escalation. The operator sees the sender, subject, and timestamp and reads the message directly in Gmail. No general inbox table exists; unclassifiable messages live in Gmail and the escalation carries enough context to find them.

Each inbound message is deduplicated by its Gmail message ID, so a run that fires shortly after a previous run does not double-process the same emails.

---

## T-72hrs: per-session order composition

The binding trigger for order composition is exactly 72 hours before each session. A Monday session gets its order at Friday 3 PM. A Tuesday session at Saturday 3 PM. Wednesday at Sunday 3 PM. Thursday at Monday 3 PM. The per-session order email lists every student and the meal they are receiving — no costs appear. Costs and payment totals are consolidated in a separate Monday 3:30 PM summary sent to each caterer, described at the end of this section.

**Building the cohort.** The system queries all active enrolments for the session's date. An enrolment is active when its `current_period_start_date` is on or before the session date and its `current_period_end_date` is either null (the student is currently enrolled) or set to a future date. `current_period_start_date` marks the start of the student's most recent continuous enrolment period — it is updated when a student returns after a departure. `opted_out_of_catering` is a per-student flag set by the parent via the term-start email; it reflects an individual family's decision, not a school-wide setting. A school stopping Padea catering entirely would be modelled as a full-school exclusion in the exclusions table. Students with absence records for that session are removed, as are students whose sessions are excluded for that date (school holidays, whole-school cancellations, year-level exclusions).

Walk-backs — students marked absent who turn up unexpectedly — are an accepted gap. Zero operational margin means no spare meals are held in reserve. The session manager redistributes any surplus from other absences, or the student misses that session's meal. This is documented in `edge_cases.md`.

**Choosing meals.** For each remaining student, the system checks whether a tutor has filed a per-session meal request for that student via the tutor app from the previous week. If one exists, the student gets that meal — the request is a one-off override for this session only, drawn from any meal on the current caterer's menu the student can safely eat. If no request exists, the system selects the next meal in the student's rotation. The rotation follows the caterer's canonical meal order — a popularity-ranked sequence of all menu items computed at term start — advancing through whichever items from that order appear in the student's approved set, always picking the one least recently served to that student.

The canonical order's value is twofold. First, because the popularity ranking reflects what most students approved, widely-liked meals appear early in the sequence — students cycle through what they actually want rather than what the algorithm happens to reach first. Second, a shared sequence across all students creates natural order concentration on the caterer's most common items, providing a gentle structural reduction in MOQ sensitivity without any artificial inflation of quantities.

Dietary-restricted students always get a dietary-safe meal, whether selected by request or by rotation. The dietary tags are a hard floor at every stage of composition.

**MOQ.** The minimum order quantity check is assessed weekly rather than per-session, in the Monday consolidated summary. If a week's total order with a given caterer falls below their MOQ floor, the system pays the difference and fires an informational escalation so the operator is aware. The composition itself is never padded or re-optimised to clear MOQ — the order reflects exactly what students need.

This is the right trade-off for Padea's current stage. The business is growing, and each term's enrolment brings more meals per school — making MOQ shortfalls progressively less common. Student satisfaction, with each student receiving the right meal in the correct rotation, is the primary operational goal; padding an order to hit a threshold would compromise dietary safety and distort rotation integrity. The canonical meal order provides a mild natural benefit here too, concentrating orders toward more popular items and softly reducing the likelihood of shortfalls over time.

**The per-session order email.** The email body lists each allocated meal with the student's name beside it — "Chicken Caesar — Sam Smith. Pasta — Lily Chen. Vegetarian curry — Marcus Patel…" — covering every student in that session's cohort after absences and exclusions are removed. No costs appear on the per-session order. The caterer receives a clear, unambiguous delivery brief: these students, these meals, this session date and time, this delivery address and room. Pricing and payment totals are reserved for the Monday consolidated summary.

The email is sent via the Gmail API. The outbound record is written to the `outbound_emails` table with its full rendered body, status, and a link back to the agent run that produced it. Send failures are caught explicitly: the outbound row marks as failed, an escalation fires, and the operator decides whether to retry, send manually via Gmail, or skip.

---

## After each session: tutor and manager input

After dinner at every session, tutors open the app and fill one box per student in their group. The meal the student received is pre-loaded. The tutor enters a 1–5 score the student verbalised — after probing rather than accepting the first number. A free-text comment captures plate behaviour, swaps, or anything notable. This is one extra box per student alongside the session notes tutors are already completing.

Alongside the rating box, a separate meal request section is available for the next session. It is not required — tutors are trained that it is an optional override, to be used only when a student specifically requests something. When opened, it presents a dropdown of all current menu items for standard students, or a filtered dropdown of dietary-safe items only for students with dietary restrictions. A request is a one-off signal drawn from the full dietary-safe menu — not constrained to the student's parent-approved set — of what the student actually wants at the next session. A request filed after the next session's T-72hrs order has already gone defers naturally to the session after that.

For opted-out students, the tutor sees a different surface: a small opt-out label in place of the rating box, plus a single checkbox — "student wishes to opt back in for meals." Ticking and submitting fires an autonomous email to the parent. The email follows the same structure as the original term-start preference email — dietary tag selection and meal preference capture — but its opening clearly states that the student's tutor has noted the student would like to start receiving meals again. Any further conversation happens directly between the tutor and the parent; tutors are trained on what to say if parents follow up. No operator approval is needed because the email is parent-facing and carries no commercial-relationship risk. The system tracks that this email has gone so repeated checkbox ticks by the tutor do not spam the parent — a second send is blocked until the opt-out period closes and a new one opens. Recurring ticks without a parent response accumulate as a soft signal in the weekly report.

The session manager fills out their own report alongside. It includes a session-level 1–5 food score, a structured checklist, a free-text comment, a count of meals left over, and the names of specific students who did not eat. The structured checklist covers five boolean questions: food arrived on time; correct number of meals delivered; correct dietary meals present for restricted students; food at appropriate temperature; packaging intact with nothing visibly wrong. These are quick to complete and specific enough to drive meaningful quality signals over time. The manager's report is the cross-check on tutor-collected data and the primary source for whole-session signals.

If a tutor does not fill in a student's post-dinner box, the system records the rating as missing — not as zero — and excludes it from the rolling mean. A pattern of missing data on a tutor or session is itself a soft signal visible in the weekly report.

---

## Each run: quality monitoring

After ingesting feedback, every agent run evaluates three single-session auto-escalation conditions:

1. A manager score of 1 or 2 on any session → operator reviews immediately.
2. A student-average score of 1 or 2 on any session — even if the manager did not flag it — → same treatment.
3. Tutor scores of 1 exceeding 25% of all tutor scores in a rolling window → a pattern escalation fires. This threshold is configurable in `runtime_config.yaml` (`tutor_1_pattern_threshold: 0.25`).

These escalations are parallel awareness, not replacements for the rolling mean. Extreme scores stay in the rolling average because they are real data.

The per-caterer rolling quality score is an unweighted four-week mean of all filled ratings — tutor and manager scores combined — per caterer. It is computed on every run, stored, and surfaced in the decision log and the weekly cross-school report.

---

## Monday 3:30 PM: weekly consolidated summary

Every Monday at 3:30 PM the system produces one summary email per caterer covering that caterer's full week across all their Padea sessions. The summary aggregates total meals, applies the MOQ floor if the weekly total fell short, adds the GST line according to the caterer's pricing flags, and states the expected total for the week. This is the canonical spending document — the figure against which payment crystallises and against which any invoice dispute is resolved. The per-session order emails established who receives what; the Monday summary translates those allocations into aggregated totals, applies MOQ and GST, and produces a single expected payment figure per caterer.

The weekly report regenerates alongside the consolidated summary. It is an HTML document — a cross-school view showing every caterer's rolling quality score, their trend over the term, any recent escalations, per-caterer cost trajectory, and opt-out rates per school. The operator reads it as a slow-drift awareness surface rather than as a real-time dashboard.

---

## Sustained decline: the rotation chain

> **As-built scope (V4):** The system's autonomous role ends at the **warning draft** and the **swap analysis** surfaced to the operator. The remaining links described below — issuing the RFP, processing responses, selecting a new caterer, and sending the cancellation and courtesy notices — are operator-manual in V4 and a candidate for a V5 build. The chain is documented here in full because it defines the intended end-to-end process the operator follows; only the warning + analysis links are autonomous today.

When the four-week rolling mean for a caterer drops below 3.0 and has also fallen at least 0.5 points below the prior twelve-week mean, the system fires a sustained-decline escalation. Both thresholds are configurable in `runtime_config.yaml` (`quality_floor: 3.0`, `quality_decline_threshold: 0.5`) — no code change or database migration is required to adjust them. It drafts a polite warning email to the incumbent caterer — naming the quality drop and stating what will happen if scores do not recover. The email sits in the outbound queue; it does not send until the operator approves with one click.

If the operator judges that scores have not recovered after the warning window — this is a manual call; there is no automatic re-trigger — they ask the system to fire a Request for Proposal. The system queries all caterers whose home postcode is within the school's postcode radius (using each caterer's stored maximum delivery distance), excludes the incumbent, and drafts a competitive RFP email to each eligible caterer: can you cover this school on this day starting approximately two weeks from now, and if not already on file, what are your current prices and lead time? The RFP goes to all eligible caterers simultaneously. The operator approves the recipient list and draft before it sends.

Responses arrive as inbound emails, classified and surfaced in the decision log. For each caterer that responds yes, the system displays: their name and contact, their stated start date, their per-meal price, their delivery fee structure, and a projected weekly cost for this school's cohort — computed as cohort size times per-meal price plus delivery fee, with the MOQ floor applied. The operator picks one respondent. The remaining respondents receive a courtesy reply drafted by the system and approved by the operator before sending.

Once the operator selects a new caterer, the system drafts a cancellation notice to the incumbent — two weeks' notice, professional tone — and queues it for operator approval. The incumbent continues to serve while the new caterer is onboarded.

Operator approval is required at every stage of the rotation chain because these are the moments when a business relationship changes. An automated system can determine that quality data warrants action, but it cannot judge tone, timing, or context the way a person can. The operator's approval ensures the right message goes at the right moment — professional, considered, and defensible regardless of what the quality scores say.

---

## Caterer change: preview week and preference reset

The new caterer's first week is a preview week. The system flags the entire week's order as an escalation requiring operator action — the operator composes that week's order manually, mirroring pre-system operation. Dietary-restricted students' meals are also chosen by the operator during the preview week; no auto-selection occurs. The new caterer's dietary offerings may not map cleanly to existing dietary tags without the operator first verifying each item directly with the caterer, so the safe default is full operator control for the entire first week.

During or after the preview week, tutors use the app to reset each student's approved meal set. The preference reset screen presents the new caterer's full menu as a checkbox list; the tutor ticks the meals each student would be happy to receive, informed by what students saw, ate, and discussed during the preview week. For students with dietary restrictions, the list is pre-filtered to dietary-safe items only — the operator has already worked through which of the new caterer's items meet each dietary requirement and marked them accordingly, so tutors select from a verified subset. No orders are composed during this preference-reset week, which means the canonical meal order can be computed fresh from the new approved sets immediately after the reset is complete. There is no fixed number of selections; the approved set is whatever the student would actually accept. Old approved sets are archived rather than deleted, in case the school ever reverts to the previous caterer.

The canonical meal order — the popularity-ranked sequence used to drive rotation — is recomputed at caterer change using the newly-captured approved sets. From the second week with the new caterer, the standard rotation resumes: least-recently-served from each student's approved set, in canonical order, with per-session meal requests overriding for individual students.

Parent involvement on a caterer change is zero. The tutor-led preference reset is the standing process, and dietary tags remain unchanged because they describe the student, not the menu.

The caterer change process requires operator involvement at every stage because the new caterer's offerings rarely map one-to-one to the incumbent's. A student who received a certified halal option from the outgoing caterer may find the new caterer's halal offering is from a different supplier, a different dish category, or not yet verified. A meal the outgoing caterer labelled gluten-free may require separate confirmation from the new caterer's kitchen. Pork-free claims may apply across the full new menu or only to specific items. The operator works through each of these questions during the preview week — communicating directly with the new caterer where needed — and marks each dietary-relevant item before tutor-led preference capture begins. This operator-gated process is deliberate: the consequences of a dietary misclassification are severe, and no schema or algorithm substitutes for a human verification step when menus change.

---

## Enrolment lifecycle: students joining, leaving, and returning

Each enrolment row carries three dates. `original_start_date` records when the student first ever enrolled with Padea and never changes. `current_period_start_date` records the start of their current active period — the same as the original start on first enrolment, updated if they return after a gap. `current_period_end_date` is null while the student is active and set when they leave. The question "was this student active on this date?" is always answered by comparing those dates against the date of interest — never from a stored status field.

When a student withdraws, the operator sets their `current_period_end_date`. From that date onward the student is excluded from all order composition. Their history — orders, feedback, preferences — remains fully queryable. When the same student returns in a later term, the operator updates `current_period_start_date` to the new join date and clears the end date. `original_start_date` is untouched; the full Padea history of that student sits under the same row.

A student who departs and returns more than once is a known limitation in V4: the schema's single `current_period_start_date` field is overwritten on each return, so only the most recent return date is directly queryable from the enrolments table. Earlier period start dates are preserved in the agent_steps audit trail but are not structured data. This is an accepted gap at Padea's current scale — the case is rare — and is documented in `edge_cases.md` with a V5 trigger to add a dedicated period history table if it becomes routine.

Every agent tool that touches enrolment data takes the relevant date as a required parameter. Order composition queries enrolment as of the session's date. The weekly report queries as of the report date. Incident investigation queries as of the incident date. There is no implicit "as of today" default — the date is always explicit.

School holidays and term breaks are handled as full-school exclusions in the exclusions table. Each exclusion row carries a `start_date` and `end_date`, so a two-week holiday across six schools is six rows — one per school covering the full date range. No per-day or per-session rows are needed; the T-72hrs check queries whether the session date falls within any active exclusion for the school. These rows are inserted by the operator in bulk via a one-off script at term end. The system runs continuously across terms; terms are a property of the exclusion calendar, not of the schema.

---

## Throughout: visibility and escalation tiers

Every tool call the agent makes, every decision, and every escalation it surfaces is recorded as a step on the agent run, with the full input, output, and reasoning captured. After every run — five to seven times per week — the HTML decision log is regenerated from the database. It is a static file that opens in any browser and shows everything the agent did, grouped by week, with urgency-sorted sections at the top of each week.

Every escalation carries one of three urgency tiers applied consistently across all escalation types.

**Urgent** items are gating something. Until the operator acts, an email does not send, an order does not compose, a caterer is not engaged. Examples: a warning email awaiting approval, an RFP awaiting approval, a Gmail send failure requiring a retry decision, an unclassified inbound requiring routing. These are what the operator works first when they open the decision log. The log renders urgent items in red, sorted to the top of each week group.

**Notable** items are worth the operator's attention but not blocking. Examples: a manager score of 1 or 2 on a session, an MOQ shortfall recurring at the same school across consecutive weeks, a tutor-1-pattern firing on a caterer. The operator reads these, makes notes, and decides if they warrant follow-up. Rendered in amber.

**Informational** items are the audit trail. Examples: an order sent successfully, a parent opt-out recorded, a caterer order confirmation received, a one-off MOQ shortfall paid and noted. No action expected. Rendered in green.

A summary count at the top of each run — "3 urgent, 4 notable, 12 informational" — lets the operator know the scale of what is waiting before they scroll. There is no acknowledgement field and no "open vs. closed" state on escalations. When the operator handles something, the next run reflects the result in the underlying data, and the log renders the updated state. The database is the source of truth; the decision log is a view onto it.

---

## How V4 is shaped

**Database.** Supabase Postgres, connected via the standard Postgres connection string. The schema is defined in SQL DDL files in the repo, giving reproducibility and a Postgres-native database accessible via the Supabase project link.

**Tool layer.** Typed Python functions wrapping deterministic database operations — `compose_session_order`, `caterers_within_range`, `project_weekly_cost`, `gmail_send`, `gmail_poll_inbox`, `get_enrolments_for_session`, and so on. Tools are called by the agent; they do not invoke the LLM. They are the unit-testable layer.

**Agent.** Claude Sonnet 4.6 invoked via the tool-calling API. The agent's `main()` inspects the current time on invocation and determines what the run should do: compose a T-72hrs order if one is due, generate the Monday consolidated summary if it is Monday 3:30 PM, or run inbound polling and quality evaluation only if neither trigger applies.

**Email.** All outbound email goes via the Gmail API in production mode. In demo mode, a single environment variable (`EMAIL_MODE=demo`) rewrites every outbound recipient to the developer's address, with the original intended recipient preserved in the email body and the database row. One config flag separates demo from production; no code changes.

**Decision log.** A static HTML file regenerated after every run from the `agent_runs` and `agent_steps` tables. Events are grouped by week, sorted within each week by urgency tier descending, then by step index. The log is the primary operator surface; the weekly cross-school report is the secondary one.

---

## Schema note: dietary tags as shared vocabulary

An important design decision in V4 is that dietary properties on menu items are not stored as boolean columns — there is no `is_halal`, `is_vegetarian`, `contains_nuts`, or any equivalent flag on the `menu_items` table. Instead, menu items carry dietary properties through the same `dietary_tags` vocabulary used for student requirements, via a `menu_item_dietary_tags` junction table. This mirrors the `enrolment_dietary_tags` pattern already used on the student side.

The semantics are deliberate: a dietary tag means the same thing on both sides. On a student enrolment, `no_nuts` means "this student requires a nut-free meal." On a menu item, `no_nuts` means "this item is nut-free." The safety check at order composition is therefore a clean set operation: an item is safe for a student if and only if the item's tag set is a superset of the student's tag set. There is no mixed-direction logic — no flipping between "contains X" and "is free from X" depending on which side of the join you are on.

This matters beyond elegance. A boolean-column approach requires a schema migration every time a new dietary requirement appears. A shared junction approach does not: adding a new tag — say, `no_sesame` — is a single data insert into `dietary_tags`, after which it is immediately available to mark both student requirements and item properties. At Padea's scale, where each school year may bring new enrolments with requirements not seen before, this extensibility is operationally significant. It also means the dietary safety logic in the tool layer is a single, auditable function rather than a growing list of boolean checks that must be updated in step with the schema.
