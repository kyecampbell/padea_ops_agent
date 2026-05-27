# V3 — Edge Cases and Accepted Gaps

This document inventories every edge case considered during V3 design and how V3 handles it. Each entry is either **handled in the design** (with a reference to the decision block that covers it) or **explicitly out of scope** (with the reason and, where relevant, a V4 build trigger).

The purpose is twofold: to make the design's coverage transparent to anyone reviewing it, and to document the deliberate gaps so they're not mistaken for oversights.

**Compiled:** 26 May 2026
**Companion documents:** the full V3 decisions block (V3-FB-01 through V3-AI-01), `cuts_v1_to_v2.md`, `memo_notes.md`.

---

## Handled in the design

### Mid-term enrolments

**Mid-term enrolment is rare; operator handles end-to-end.** Brief explicitly flags as rare. Operator captures dietary tags and approved meal set, creates the enrolment row with `original_start_date` and `current_period_start_date` set to the join date, manually composes the kid's first-week meal if the timing allows. From the next session run, kid is in standard rotation. Documented in V3-PV-01 and V3-EL-01.

**Late mid-term enrolment (after T-72hrs cutoff) — kid misses next session.** A kid entered into the system after a session's order has already been sent doesn't get a meal that session; waits for the next one. Same forcing function as the walkup pattern — operational friction is intentional. Documented in V3-PV-01 amendment.

### Absences

**Routine absence handling.** Parent emails Padea → Gmail polled at next agent run → agent classifies as absence → creates absences row → kid is excluded from the next T-72hrs order composition for the affected session. Documented in V3-CM-01 + V3-AI-01.

**Late absence (after order already sent).** Late absence is recorded in the absences table for audit but does not amend the already-sent order. Caterer prepares the meal anyway; kid doesn't show up; meal is wasted (or absorbed by manager-discretion redistribution). Cost: occasional wasted meal. Tradeoff: clean commercial-message discipline — no amendment emails to caterers. Documented in V3-AI-01.

### Walkups and unexpected attendees

**Opted-out kid changes their mind on the day.** Doesn't get a meal that session. Tutor can flag the opt-back-in checkbox; system fires an email to parent; from next session run after parent confirms, kid is in rotation. Documented in V3-MP-01.

**Truly unexpected attendee (sibling tagging along, paperwork-pending new enrolment).** Handled before dinner by the school's normal attendance processes. Catering system has no concept of unregistered attendees; no meal is ordered for them. Documented in V3-IL-01.

**Walkbacks (kid marked absent but turns up).** Whatever meal was ordered is either redistributed by the manager or wasted; no special handling. Documented in V3-MP-01.

### Caterer behaviour

**Caterer non-confirmation of order.** Orders are assumed acknowledged unless Gmail returns an explicit bounce/error. Caterer reply is not required for the order to be considered live. Per-session cadence trusts the caterer to operate on the order as received. Documented in V3-CM-01.

**Caterer responds to RFP — tie on pricing/distance.** Operator decides manually. No system tiebreaker. Same approval surface used for any RFP response: operator picks one, dismisses the rest, system drafts the cancellation email + thanks-but-no emails for operator approval. Documented in V3-CR-01.

**Caterer responds to warning email with improvement commitment.** Rolling means catch genuine improvement automatically — if scores rise, decline detection stops firing. Operator can manually dismiss the warning escalation. No explicit acknowledgment mechanism in the schema. Documented in V3-FB-01.

### Dietary safety

**Dietary contradiction at order composition.** Dietary tags are the hard floor at every stage. Parent's approved meal set is filtered by dietary tags at parent-email submission time. Re-filtered again at every order composition. If a contradiction is detected at order-composition (parent approved a meal violating their stated dietary tag — system filter glitch, edge case), the dietary tag wins; kid is auto-assigned the next available dietary-safe meal from their approved set. Logged for operator review. Documented in V3-FB-01 amendment.

**Mid-term dietary change.** Parent emails Padea about a new dietary restriction. Operator handles directly — updates the dietary tags on the enrolment row. No structured email-parsing flow built for this. Memo flag: rare event, operator labour acceptable. Documented in V3-PV-01.

**Dietary safety wins by default.** No severity field on dietary tags. Every dietary tag is treated as safety-critical (allergy-level) by default. Over-cautious, but the safe direction. Documented in V3-AI-01.

### Tutor / Manager feedback

**Tutor doesn't fill in the post-dinner box.** That session's tutor rating for that kid is recorded as missing (null), not zero. Not folded into the rolling mean. Pattern across sessions surfaces in the weekly report as a soft signal. Documented in V3-FB-01.

**Manager doesn't submit a session report.** Session-level rating recorded as null; doesn't feed mean. Same pattern signal as tutor missing data. Documented in V3-FB-01.

**Out-of-range scores from tutor or manager.** Scores are constrained as a 1-5 enum at the parsing layer. Out-of-range submissions cannot be made through the app UI; if received via direct email (the simulation channel), the agent escalates as a "malformed feedback submission." Documented in V3-FB-01.

**Duplicate submission from same tutor for same (kid, session).** Last write wins. Tutor can correct themselves; system uses the most recent submission. Documented in V3-FB-01.

**Dual-role manager-tutor at same session.** A person who is both managing the session and tutoring kids submits two distinct feedback channels: their manager-level session report and their per-kid tutor ratings. Rolling-mean math counts them as two independent rater perspectives. Documented in V3-IL-01.

### Order composition

**School holiday week.** Operator marks holiday dates as full-school exclusions. Agent's T-72hrs check sees the exclusion and skips order composition silently. No order email sent, no payment line. Documented in V3-EL-01.

**Exam-week attendance dip below MOQ.** No special handling. Order composition produces whatever count the cohort minus absences yields. MOQ floor kicks in via V3-OC-01 if needed — operator pays the floor, gets notified. Recurring patterns surface in weekly report. Documented in V3-OC-01.

**Same-name students at the same session.** Operator discipline at enrolment entry uses distinguishable names ("Sam Smith Jr.", "Sam Smith (Y8)"). Database IDs exist for system attribution; human-facing emails use the disambiguated name. Documented in V3-IL-01.

### Communication failures

**Gmail send failure.** Outbound row marked `status=failed` with failure reason. Escalation fires. Operator decides whether to retry, send manually via Gmail's web interface, or skip. Documented in V3-CM-01.

**Unclassifiable inbound email.** Escalation fires with sender, subject, received timestamp, and source reference. The original email content sits in Gmail (and is downloadable via the API); operator reads it and decides. No general inbound emails table. Documented in V3-CM-01.

**Inbound email arrives for an unknown thread.** Caterer replies to an old order email but the agent can't tie it to a current open order. Falls through to unclassified, escalates, operator handles. Documented in V3-CM-01.

### Opt-out lifecycle

**Opt-out elicited via parent email.** Single-click response from the term-start parent email. Default state is opted-in. Documented in V3-PV-01.

**Opt-out reversal.** Tutor app checkbox triggers an autonomous email to parent. Parent responds → operator handles dietary tags + approved meal set capture → flips the opt-out flag. From the next session run, kid is in rotation. Send-once tracking prevents repeated tutor ticks from spamming the parent. Documented in V3-MP-01.

**Opt-out kid wants meals on the day.** Doesn't get one that session. Tutor flags the opt-back-in checkbox; system fires the parent email; standard reversal flow. One-week friction is the forcing function. Documented in V3-MP-01.

---

## Out of scope — accepted gaps

Each entry below is a deliberate non-feature. Listed with the reason and the V4 build trigger where one applies.

### Parent and consent edge cases

**Parent never responds to enrolment email.** Out of scope. No timeout-driven escalation, no automatic default-to-opt-out at some configured delay. If the parent doesn't engage, the operator notices the missing response during their weekly review and handles manually. *Reason:* operator labour is acceptable for a low-frequency case; building automated chase-and-default logic earns less than the manual handling it would replace. *V4 trigger:* parent-no-response becomes a routine recurring case.

**Parent revokes consent mid-term in a structured way.** Out of scope. Mid-term dietary changes, opt-out flips, and other state changes all go through direct operator handling. *Reason:* rare, varied, doesn't fit a single parse-and-update flow. *V4 trigger:* multiple structured parent-state-change emails per term become routine.

### Order and delivery exceptions

**Caterer cancels a delivery last-minute.** Out of scope. Caterer-side cancellation (kitchen fire, staff illness, vehicle breakdown) arrives as an unclassified inbound, escalates, operator handles via direct communication. No system mechanism for emergency alternative routing. *Reason:* this is a human decision involving commercial relationship judgement that the system shouldn't model. *V4 trigger:* if last-minute cancellations become non-rare, an emergency RFP flow to the regional caterer list (V3-CR-01) becomes worth building.

**Caterer responds to RFP with a counter-offer (different price than current).** Out of scope as a structured flow. Arrives as an unclassified inbound; operator reviews, decides whether to accept, counter, or move to next candidate. *Reason:* commercial negotiation isn't something the system should be doing autonomously. *V4 trigger:* repeated RFP counter-offers become a recurring operational case.

**Email arrives in caterer's spam folder.** Out of scope. V3 has no read-receipt or open-detection mechanism. Operator notices over time if a caterer's responsiveness drops and investigates manually. *Reason:* Gmail API doesn't reliably expose this signal. *V4 trigger:* read-receipts or follow-up reminder logic if engagement metrics become operationally important.

### System reliability and consistency

**Agent run fails mid-execution.** Out of scope as a structured recovery feature. Agent runs are largely idempotent (database is the source of truth; outbound emails dedupe via send-status checks). Operator sees failed runs in the decision log and re-runs manually if needed. *Reason:* idempotent runs reduce the need for explicit retry/recovery logic; full-fidelity failure handling earns its place at production scale, not heats. *V4 trigger:* run failures become a regular operational issue.

**Database becomes inconsistent (orphaned references, manual edit errors).** Out of scope. No periodic consistency-check tooling; no anomaly detection on input changes. V3 trusts operator discipline and the explicit foreign-key constraints to prevent inconsistency. *Reason:* a deliberate-discipline approach is acceptable at a single-operator scale. *V4 trigger:* operator team grows or database errors become recurring.

**Daylight saving time transitions.** Out of scope. Cron jobs may fire 1 hour off during DST changeover weekends. The agent's "what session is 72 hours from now" logic absorbs this — the next session selection remains correct, just at a slightly different wall-clock time. *Reason:* low-frequency event; behaviour is correct even if timing drifts. *V4 trigger:* not anticipated to ever build.

**Multi-region / multi-time-zone operation.** Out of scope. V3 assumes single time zone (Australia/Brisbane). All times stored as UTC internally; displayed in the operator's local timezone. *Reason:* Padea is geographically constrained; multi-region is not the brief's reality. *V4 trigger:* Padea expands to a different time zone.

### Mass / unusual events

**Zero-cohort session (all kids opted out, all withdrawn, all absent, etc.).** Out of scope. So unlikely it isn't worth planning for. *Reason:* would require all kids in a session to be unavailable simultaneously, which the operational reality makes vanishingly rare. *V4 trigger:* never anticipated, but if it ever happens, operator handles manually.

**Mass simultaneous absence (large group of kids absent for the same reason — e.g. school excursion).** Already covered by full-session or partial exclusion mechanism (V3-EL-01). If it's expected, operator marks it as an exclusion at term start. If it's unexpected, individual absence emails arrive normally.

### Enrolment lifecycle

**Student who departs and returns more than once (repeat period cycles).** The V3 schema's three-date model (`original_start_date`, `current_period_start_date`, `current_period_end_date`) handles a single departure and return correctly. A student who departs and returns a second time overwrites the second `current_period_start_date` with the third — the middle period's start date is lost as structured data. The agent_steps audit trail preserves every operator update, so the history is recoverable, but it is not directly queryable from the enrolments table. *Out of scope for V3 — rare at Padea's current scale.* *V4 trigger:* add an `enrolment_periods` table storing each (start_date, end_date) pair per enrolment if multiple returns become a routine operational case.

### Identity and attendance

**Cross-school student identity resolution.** Out of scope. No kid in Padea's data attends multiple schools. If such a case emerged, operator manually notes the connection; system treats them as two unrelated enrolments. Documented in V3-IL-01. *V4 trigger:* real cross-school case emerges.

**Padea attendance differs from school attendance.** Out of scope to integrate with the school's attendance system. Padea marks attendance independently; kid not at school but at Padea is fine; kid at school but not at Padea is fine. *Reason:* Padea operates as a separate entity at the school; integrating with the school's attendance system is out of scope. *V4 trigger:* never anticipated.

**Silent no-show (kid was ordered for, didn't show up, no absence email arrived).** Not preventable in V3. Manager's "names of kids who didn't eat" field from V3-FB-01 catches it after the fact. *Reason:* requires integration with attendance systems V3 doesn't model. *V4 trigger:* school attendance integration.

### Operator and team

**Multiple simultaneous operators.** Out of scope. V3 assumes one operator. No conflict resolution, no role-based access. *V4 trigger:* operator team exceeds one person.

### Payment

**Payment integration (Stripe, accounting software, bank API).** Out of scope. V3 models the financial crystallisation moment (Monday 3:30 PM consolidated summary) but the actual payment mechanism is operator-handled outside the system. *V4 trigger:* operator labour for payment handling becomes a bottleneck.

### Edge cases that might emerge in a real deployment

**PII redaction and data retention policies.** Out of scope. Real deployment precondition; not a system feature for the demo. *V4 trigger:* real deployment with real parent data.

**Anomaly detection on incoming data changes.** Out of scope. Operator review covers it. *V4 trigger:* input data volume exceeds operator review capacity.

**What-if simulators (rotation modelling before commitment).** Out of scope. *V4 trigger:* rotation becomes high-frequency enough to warrant pre-decision modelling.

---

## Summary table

| Edge case | Status | Where handled / why deferred |
|---|---|---|
| Mid-term enrolment | Handled | V3-PV-01, V3-EL-01 — operator end-to-end |
| Late mid-term enrolment (after order sent) | Handled | V3-PV-01 amendment — kid waits |
| Routine absence | Handled | V3-CM-01, V3-AI-01 — Gmail polled at each run |
| Late absence (after order sent) | Handled | V3-AI-01 — recorded, not amended |
| Walkup / opt-out wants meal | Handled | V3-MP-01 — checkbox + parent email |
| Unexpected attendee | Handled | V3-IL-01 — school handles before dinner |
| Caterer non-confirmation | Handled | V3-CM-01 — assumed OK unless Gmail error |
| Caterer last-minute cancellation | Out of scope | Manual operator handling; V4 emergency RFP |
| Caterer RFP tie | Handled | V3-CR-01 — operator decides manually |
| Caterer RFP counter-offer | Out of scope | Unclassified inbound; operator handles |
| Caterer improves after warning | Handled implicitly | V3-FB-01 — rolling means catch it |
| Caterer email goes to spam | Out of scope | V4 read-receipts |
| Dietary contradiction | Handled | V3-FB-01 — dietary tags hard floor at every stage |
| Mid-term dietary change | Handled | V3-PV-01 — operator updates directly |
| Tutor missing data | Handled | V3-FB-01 — null doesn't feed mean |
| Manager missing data | Handled | V3-FB-01 — same as tutor |
| Out-of-range scores | Handled | V3-FB-01 — enum constraint at parsing |
| Duplicate tutor submission | Handled | V3-FB-01 — last write wins |
| Dual-role manager-tutor | Handled | V3-IL-01 — two independent rater channels |
| School holiday | Handled | V3-EL-01 — exclusions table |
| Exam-week MOQ dip | Handled | V3-OC-01 — pay MOQ floor, weekly report |
| Same-name students | Handled | V3-IL-01 — operator discipline at entry |
| Gmail send failure | Handled | V3-CM-01 — escalation |
| Unclassifiable inbound | Handled | V3-CM-01 — escalation |
| Inbound for unknown thread | Handled | V3-CM-01 — escalation |
| Opt-out elicitation | Handled | V3-PV-01 — single-click in parent email |
| Opt-out reversal | Handled | V3-MP-01 — tutor checkbox triggers parent email |
| Parent never responds to enrolment | Out of scope | Operator chases manually |
| Parent revokes consent mid-term | Out of scope | Operator handles directly |
| Mid-run failure | Out of scope | Idempotent runs reduce risk; V4 hardening |
| Database inconsistency | Out of scope | Operator discipline; V4 consistency checks |
| Daylight saving transitions | Out of scope | Logic absorbs timing drift |
| Multi-time-zone operation | Out of scope | Single time zone in V3 |
| Zero-cohort session | Out of scope | Vanishingly rare |
| Student departs + returns multiple times | Out of scope | V4 — add enrolment_periods table |
| Cross-school identity | Out of scope | V4 if real case emerges |
| Attendance system integration | Out of scope | V4 if needed |
| Silent no-show | Out of scope | Manager catches it after the fact |
| Multiple operators | Out of scope | V4 trigger documented |
| Payment integration | Out of scope | V4 build trigger documented |
| PII / data retention | Out of scope | Production precondition |
| Anomaly detection | Out of scope | Operator review |
| What-if simulators | Out of scope | V4 trigger |