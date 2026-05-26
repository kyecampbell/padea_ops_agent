# Assumptions — Padea Operations Agent

**Purpose:** The interpretive decisions and operational assumptions the schema and agent operate under. Each entry is an assumption made during design or ingest that could be revisited if operational reality contradicts it.

**Compiled:** 23 May 2026
**Source:** Extracted from `schema_complete.md` "Running assumptions list" section.
**Companion documents:** `schema_complete.md`, `decision_register.md`, `log_2026-05-23_schema-design.md`, `log_2026-05-23_build-phases.md`

---

## How to read this document

The schema design rests on these assumptions. Where the schema describes *what* the system does, these assumptions describe *what we believed to be true* when we designed it that way.

Some assumptions are interpretations of ambiguous source data (e.g. "non-pork meals are halal"). Others are operational conventions (e.g. "one caterer can serve at most one school per day"). Others are design philosophy choices applied consistently across the schema (e.g. "event-storing as default").

Each assumption could be wrong. If operational reality contradicts one, the schema or agent logic may need revisiting. The document is the audit trail for those revisits.

Grouped here by theme. The original numbering from `schema_complete.md` is preserved in `[brackets]` after each entry for cross-reference.

---

## Identity and student data

**1. Same name at different schools = different students unless evidence to the contrary.** Two students sharing a name across schools are treated as different humans at ingest. Can be reconciled later if data emerges. *[1]*

**2. Year level lives on enrolment, not on student.** Year level is contextual to a time period; a student moving from Year 11 to Year 12 mid-term creates a new enrolment, not an edit to the student. *(implicit from schema design; see DR-6)*

**3. Opt-out from catering is per-enrolment, not per-student.** A student can opt out at one school but stay in at another; term-to-term flips are clean via new enrolment rows. *(implicit from schema design; see DR-11)*

**4. Tutors and students share dietary vocabulary.** One `dietary_tags` table; two junction tables (`student_dietary_tags`, `tutor_dietary_tags`) reuse the same vocabulary. *(implicit from schema design; see DR-9)*

---

## Dietary interpretation

**5. Non-pork menu items are halal.** Source PDF rule applied at ingest. Halal-matching done as exclusion query against `contains_pork` tag. *[2]*

**6. VO ("vegetarian option") is a caterer capability, not a property of the menu item.** Modelled as `vegetarian_swap_available` boolean. The original item is not vegetarian; the caterer can swap it on request. *[3]*

**7. All dietary tags treated as hard constraints in v1.** No soft preferences. A vegetarian student is matched only to vegetarian-tagged or VO-capable items. *(implicit from schema design)*

---

## Caterer operations

**8. Preference rank baseline inferred from current "currently serves" data.** Caterers currently serving a school are ranked higher; updated by operational signal over time. *[4]*

**9. One caterer can serve at most one school per day.** Simplest reading of the operational constraint; covers all conflict cases without time-window calculations. *[5]*

**10. Caterer capability is conditional on current operating conditions.** Significant changes (enrolment growth, schedule shifts, MOQ pressure) trigger re-confirmation escalation rather than silent continuation. *[6]*

**11. Capability matrix encodes (without separately modelling) distance feasibility, kitchen capacity, time-window constraints.** All three are out of scope as first-class data; assumed satisfied by the capability matrix. *[7]*

**12. Caterer capability modelled at (caterer × school × day-of-week) granularity.** Schools adding session days require explicit new capability rows. *[20]*

**13. Caterer rotation in v1 is human-in-the-loop.** Agent surfaces and drafts; Dylan approves and triggers. *[21]*

**14. MOQ treated as hard weekly contract minimum in v1.** Service agreement with MOQ floor would soften this and reduce escalations; out of scope for v1. *[22]*

**15. MOQ rules modelled as separate `caterer_moq_rules` table with (caterer × menu_variety_count) granularity.** *[25]*

---

## Caterer contacts

**16. Email addresses are operational; Padea-controlled placeholders during judging.** Dylan can monitor what the system sends during competition assessment without spamming real businesses. *[8]*

**17. Caterer contact email/name pairings preserved as given.** Earlier interpretation about apparent Dylan/James email swap superseded — these are placeholder addresses, not data quality issues. *[9]*

**18. Contact roles modelled as four independent booleans** (`is_order_taker`, `is_chef`, `is_primary_contact`, `cc_on_orders`). Any combination is valid; new contacts with new role combinations require no schema change. *[10]*

---

## Managers and tutors

**19. Managers are tutors with a per-session manager role, not a separate population.** Modelled via `expected_manager_id` and `actual_manager_id` on sessions; no separate `managers` table. *[11]*

**20. Tutor table in v1 is minimal.** Just identity and mobile. Expansion deferred to the future tutor module. *[12]*

**21. Default manager patterns not modelled explicitly.** Lucian-usually-does-Monday-ISHS emerges from historical session_tutor_assignments rather than a stored default. *[13]*

**22. Session manager captured as expected + actual fields; difference captures cover events.** No separate tutor-absences table needed. *[14]*

---

## Order generation

**23. Orders generated per-session, sent 3 days before session start time.** Not per-week. Weekly aggregates derived from queries over orders. *[15]*

**24. Agent forecasts remaining week's demand at early-week order generation for MOQ verification.** When generating an early-week order, the agent projects later-week demand to verify weekly MOQ will be met. *[15a]*

**25. "3 days before" means 3 days before session *start* time, not dinner time.** Standardised rule across all sessions regardless of dinner-time variation. *[23]*

**26. Buffer meals drawn from "common, broadly-appealing" pool.** One per tutor + 2 contingency per session. Not preference-matched to individual tutors; flexible enough to absorb walk-ups. *[16]*

**27. Dietary-restricted student meals are always made.** Walk-up insurance plus commercial guarantee — no substitute exists from the common-meal buffer. *[17]*

**28. Dietary-restricted student meals are made even on pre-send cancellation.** If a parent cancels a dietary student before the order is sent, the meal is still made. *[35]*

**29. All paying students have a meal available regardless of cancellation timing.** Late walk-backs of non-dietary students are absorbed by buffer meals. *[36]*

**30. v1 manifest organised by session-and-student.** Tutor-group organisation deferred to future tutor module. *[18]*

**31. Order construction is a single event at T-3 days.** `order_lines` are never mutated by subsequent absences. Pre-send "cancellation" = omission at construction, not amendment of an existing line. *[40]*

**32. Current Thursday-as-order-day operation demonstrates 3-day prep capability for all caterers.** The current human-driven Thursday send for the earliest Monday session proves the lead time is workable. *[19]*

---

## Payment

**33. Payment calculation derived from orders per (caterer × week) as a query, not a stored table.** Actual payment recording deferred to v2 with real banking integration. *[24]*

---

## Absences

**34. Absence intake primarily email-driven.** Non-email sources permitted via nullable `source_email_id`. *[37]*

**35. Walk-backs modelled as nullable timestamp on the absence row.** Walk-back-of-walk-back creates a new absence row rather than re-flipping the existing one. *[38]*

**36. Pre-send vs post-send window derived from `received_at` vs `orders.sent_at` at query time.** Not stored as a column. *[39]*

**37. One absence row per (student, session), database-enforced.** Confirmation duplicates discarded; conflicting reasons resolved as first-wins. Source emails preserved in `incoming_emails` regardless of dedup outcome. *[41]*

---

## Exclusions

**38. Whole-session cancellations override the dietary-always-made rule.** No meals constructed at all when a session is cancelled. School being physically closed makes walk-up-insurance and commercial-guarantee reasoning inapplicable. *[42]*

**39. Partial exclusions (year level) trigger a 10% attendance buffer.** Ten percent of the excluded cohort, rounded up to the nearest whole meal, added on top of the standard buffer. Sized to the social reality that some excluded students attend anyway. *[43]*

**40. The 10% attendance-buffer rate is hard-coded in the agent's order-construction logic.** Per-school or per-event-type configuration deferred to v2 pending actual consumption data. *[44]*

**41. Exclusions arrive primarily as year-level bloc statements from school admin.** Individual-student lists (when schools send them) are processed as absences instead. *[45]*

**42. Subject-specific camps and similar partial-cohort exclusions are modelled as individual absences, not exclusions.** Exclusions table is reserved for whole-session and year-level cases in v1. *[46]*

**43. Exclusions have no walk-back mechanic.** Reversed school decisions are handled manually by deleting or superseding the exclusion row. *[47]*

**44. One exclusion row per (session, scope, scope_value), database-enforced.** Confirmation duplicates discarded; source emails preserved in `incoming_emails`. *[48]*

**45. Whole-session cancellations arriving post-send are still recorded as exclusion rows.** The order is not undone; the row exists for audit and pattern detection. *[49]*

---

## Feedback

**46. Feedback collected via two-tier model.** Manager per-session + tutor self-feedback + end-of-term parent/student surveys. Not per-meal student ratings. *[26]*

**47. Manager rates session-overall with free-text comments.** Per-item granularity recovered via LLM extraction of structured signals from comments. *[27]*

**48. Tutor feedback identified (not anonymous) for outlier detection.** Aggregates anonymised at presentation. *[28]*

**49. Rating scale is 1-5 throughout. Comments expected as default for all feedback.** Earlier "extreme-rating-requires-comment" rule dropped; comments are the default practice. *[29]*

**50. Solicited feedback only enters the feedback pipeline.** Unsolicited messages (parent complaints, caterer concerns) become escalations rather than feedback rows. *[30]*

**51. Term survey respondents pseudonymous.** Random consistent ID per respondent across terms; honesty preserved while longitudinal tracking remains possible. *[31]*

**52. Walk-up student events captured as a first-class table.** Drive immediate escalation when unmatched to an enrolled student; parent-call escalation after 2 false-absence walkups. *[32]*

**53. Comment-extracted signals stored as a computed cache.** Deliberate exception to event-storing default; justified by LLM cost and query frequency. *[33]*

**54. Caterer rolling rating computation includes rater-baseline normalisation and submission-timing reliability weighting.** Both done at query time; no stored calibration columns. *[34]*

---

## Agent operational

**55. Agent runs are discrete invocations.** Each gets one `agent_runs` row. Crashed runs detected by next-run cleanup with 30-minute staleness threshold. *[50]*

**56. Tool calls and branch decisions live in the same `decision_logs` table, distinguished by `decision_type`.** Demo UI defaults to hiding routine tool calls and rule applications. *[51]*

**57. Decisions form a tree via `parent_decision_id`; no depth cap.** *[52]*

**58. Escalations use hybrid resolution.** `auto` closes when trigger condition is gone; `human` closes when Dylan replies to notification email with closure keyword. *[53]*

**59. Escalation dedup via agent-computed `match_key` with code-side conventions per escalation type.** Same-key resolved escalations don't block new ones. *[54]*

**60. Severity is per-instance, agent-chosen.** Same `escalation_type` can range info to urgent based on context. *[55]*

**61. Approval-shaped escalations use `open` state; body carries drafted action; Dylan's reply (`approved`/`dismissed`) closes the row.** No separate "awaiting_approval" state. *[56]*

**62. Reply parsing for escalation closure uses `[PADEA-ESC-{id}]` subject token with fuzzy matching as fallback.** *[57]*

**63. Incoming emails stored with raw headers + plain + html bodies.** Attachments metadata-only in v1. *[58]*

**64. Tool outputs stored as summaries only.** Full outputs and PII redaction deferred to v2. *[59]*

**65. `agent_version` and `model_identifiers` recorded per run for retrospective correlation.** *[60]*

**66. Outgoing emails not part of the operational cluster.** Designed with the agent's action layer rather than the data layer. *[61]*

---

## Notes on numbering

The original list in `schema_complete.md` had 61 entries. This document expands to 66 by:

- Promoting some implicit-from-design assumptions (entries 2, 3, 4, 7) to explicit numbered status. These were referenced consistently in the schema work but never given assumption numbers.
- Renumbering for clarity (the original list had a "15a" sub-entry that's now standalone).

The bracketed references at the end of each entry (e.g. `[2]`) point back to the original schema doc numbering for cross-reference.

---

*End of assumptions list. This document is the consolidated reference. If new assumptions are added during build, append them here with the date and reasoning.*
