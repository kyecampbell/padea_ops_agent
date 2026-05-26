# Assumptions — Padea Operations Agent

**Purpose:** What we are taking to be true about Padea's operation, the source data, and the world the system runs in. Each entry is an interpretive claim that could be revisited if reality contradicts it. Where an assumption has driven a downstream design choice, that choice lives in the decision register.

**Compiled:** 25 May 2026
**Companion documents:** `data_observations.md`, `decision_register.md`, `schema.md`.

---

## How to read this document

Where the requirements describe *what the system must do* and the decision register describes *how it chooses to do it*, this document describes *what we believed to be true* when those choices were made.

Some assumptions are interpretations of ambiguous source data — the data alone does not determine an answer, so we have to commit to one. Others are operational conventions about how Padea actually runs. Others are simplifications: the world is more complex than the assumption, but we are choosing to treat it as simpler for the purposes of this build.

Each assumption could be wrong. If operational reality contradicts one, the assumption is the place to revisit before reworking design downstream of it.

Assumptions are grouped by theme.

---

## Identity and student data

**A1. Same name at different schools refers to different students unless evidence shows otherwise.** Where the source data contains the same name at two schools, the two are treated as distinct individuals at ingest. Reconciliation is possible later if evidence emerges, but the default is non-collapse.

**A2. Year level is contextual to a period of enrolment, not a permanent property of a student.** A student moving from Year 11 to Year 12 mid-year, or between schools at different year levels, is treated as a sequence of enrolments rather than as a single student record being edited.

**A3. Catering opt-out is a property of an enrolment, not a property of a student.** A student can opt out of catering at one school and not at another, and a student opting out one term and not the next is handled by new enrolment data rather than mutation of a persistent flag.
## NOTE; should it be a property of enrolment though as studetns can opt back in for meals. how else can we deal with it. 

**A4. Tutors and students draw from the same dietary vocabulary.** Wherever dietary requirements are recorded, the same set of dietary concepts applies regardless of who carries them.
## NOTE; this feels very decisiony and not like an assumption. remember all of these should be direct knowledge gaps that are filled by our assumpt. they should feel intuitively necessary or elsewise be justified. 

---

## Dietary interpretation

**A5. Non-pork menu items are halal.** This is stated explicitly in the source data's menu legend. The system interprets this as: a menu item is halal-eligible if it does not contain pork. Halal status is derived rather than separately recorded per item.

**A6. The `VO` annotation on a menu item describes a caterer capability, not a property of the item.** An item marked `VO` is not vegetarian as listed — the caterer offers a vegetarian variant on request. Matching a vegetarian student to a `VO` item involves the caterer making the swap.

**A7. Dietary requirements are hard constraints, not soft preferences.** A vegetarian student is matched only to vegetarian items or to items where a vegetarian variant is available. There is no fallback to "vegetarian most of the time."
## NOTE; this feels a little redundant and already mentioned in the requirements. no need to repeat myself. 

---

## Caterer capability and rotation

**A8. A caterer's "currently serves" assignment is a stronger signal than their "able to serve" capability when considering routine ordering.** Caterers currently serving a school are the default choice; caterers listed as able to serve but not currently serving are alternatives, used when rotation or fallback is appropriate.
## NOTE; i think this is a slightly off interperation it also doesnt feel like an assignmetn. if the data is given as x currently serves y and is able to serve x and z its fair to ASSUME that that means for all sessions that school currently does but not ones that dont exist yet as availability is based of time and scheduling as well as location legistics etc. 

**A9. A caterer can serve at most one school on any given day.** A single caterer's kitchen produces meals in a constrained time window and a single driver delivers them, so the operational reality is one school per caterer per day. The dataset reflects this and no other case appears.
## NOTE; awesome assumption 

**A10. A caterer's stated capability is conditional on the conditions under which it was stated.** If a school's enrolment grows substantially, its schedule shifts, or its order patterns change in ways that materially affect what's being ordered, the caterer's previous "yes" should be re-confirmed rather than relied on indefinitely.
## this feels more requirementy than assumption, the assumption is that they are able to cater to teh current size and perhaps any sizes indicates in the MOQs, logical, they wouldnt offer a MOQ upper bound if they couldnt reach it. the current assumpt likely belongs in reqs. 

**A11. Distance feasibility, kitchen capacity, and time-window constraints are absorbed into the "able to serve" capability list rather than modelled separately.** When a caterer is listed as able to serve a school, those three constraints are satisfied for that combination.

**A12. Caterer capability is described at the granularity of (caterer, school, day-of-week).** A caterer who can serve a school on Monday is not automatically able to serve it on Thursday; a school adding a new session day requires a fresh capability conversation with the caterer.
## NOTE; yes good, perhaps my note earlier was redudnant as its answered here a fair bit. 

**A13. Caterer rotation is a human-approved action, not an autonomous one.** The system can detect when rotation is warranted, propose specific alternatives, and draft outbound communication, but the decision to rotate belongs to a human.
## NOTE; feels decisiony. could assume that cater automatic roration likely involves service agreements, legality issues etc. leave it at that in decisions i will talk about how this then requires the decision to escalate. 

**A14. MOQ is a hard contractual minimum.** Falling below a caterer's MOQ for the week creates a real commitment to make up the shortfall, not an opportunity to underpay. The system treats MOQ as binding.
## NOTE; assume anything less results in a financial penalty of such, perhaps paying for the MOQ regardless of needing less etc.

---

## Caterer contacts

**A15. The email addresses listed for caterer contacts in the source data are operational placeholders, not real caterer-business addresses.** Several route to Padea-controlled inboxes. This is treated as an intentional fixture of the data for assessment purposes rather than as a data quality issue.

**A16. Name-to-email pairings in the contacts data are preserved exactly as given.** Where the pairings appear inverted or unusual, no repair is attempted at ingest. Earlier interpretations of these as data quality issues are superseded by their placeholder status.

**A17. Each caterer contact carries some combination of four orthogonal role properties: order-taker, chef, primary-contact, and cc-on-orders.** Any combination of these is operationally valid. A single contact can be all four; another can be only one. Role combinations are not constrained at the data layer.

---

## Managers and tutors

**A18. Managers are tutors who, on a given session, are assigned the manager role for that session.** They are not a separate population. The same person can manage one session and tutor (without managing) at another.

**A19. The tutor record contains only the data the catering system needs about a tutor: name and contact.** Broader tutor information — subjects, qualifications, employment history — belongs elsewhere and is read by other systems.

**A20. Default manager patterns (e.g. "Lucian usually manages ISHS Monday") emerge from historical assignment data rather than from a stored default.** If patterns are needed for prediction, they are derived from the record of past assignments.
## NOTE; this feels redundnat and silly. i dont remember why our design requires predicitng session manager roles but it shouldnt, its locked in for the term unless they are away. 

**A21. Manager presence is captured at two timestamps per session: expected (set in advance, used for caterer logistics) and actual (recorded after the session).** Differences between expected and actual implicitly capture cover events without needing a separate concept of tutor absence.
## NOTE; this also feels weird. please jutfity. 
---

## Order generation

**A22. Each session generates its own order. Weekly aggregates are derived by summing across sessions for a given caterer.** There is no per-week order record that orders roll up into.

## NOTE;feels like a decision. 

**A23. The order for a session must be sent with adequate lead time for the caterer to prepare. The current Thursday-for-following-week operation provides evidence of feasible lead times for all current caterers.** Lead time is measured against session start, not against the dinner break within the session.
## NOTE;feels like a requirement. can easily be reworded as assumption. it is assumed prep time is measured releavnt too...

**A24. Order construction is a single event in the timeline of a session. After the order is sent, the order's contents are not amended in response to subsequent absences or walk-backs — those are absorbed by other mechanisms (margin, walk-up handling).** This avoids cascading amendments late in caterer preparation.
## NOTE; is this a deciison i cant tell what its trying to say. 

**A25. When generating an early-week order, the agent must forecast remaining-week demand to verify the caterer's weekly MOQ will be met.** Some caterers serve multiple sessions across a week; MOQ is a weekly figure; an order sent on Monday for that caterer commits a portion of the week's total.
## NOTE;i dont remember the system we decided on for this but this feels silly again. what happend to the monday nuance thing rememver that, 3 days of prep time means monday the final order for thursday will be sent. it also means monday the first delivery will be sent on monday so we can do the full weeks pay for every catere inbetween those two minimising risk. do you rememver this i will further explain if you dont. 

**A26. The operational margin (the few extra meals included beyond confirmed attendance) is drawn from a common, broadly-appealing pool of items.** It is not preference-matched to any specific person; its purpose is to absorb unpredictability — late absences walked back, students arriving unexpectedly, visitors. 
## NOTE; no students will be arriving unexpectedly, these students we dont account for it would be silly too, they havent paid for a meal. if there is a spare they will obciously take it it would be cruel otherwise. not worth documenting this. assumption rewording could incolve the assumption that a buffer will be required the second we start cutting meals in accordance with absences or exclusions as students may return and not notify us. 

**A27. Meals for dietary-restricted students are made even when the student's attendance is uncertain or cancelled before the order is sent.** Dietary-restricted students cannot fall back on the common-pool margin because no substitute exists; their meal must be guaranteed present.
## NOTE; this is a desision for sure. 

**A28. All students who are paying for the service have a meal available regardless of cancellation timing.** Late cancellations of non-dietary students are absorbed by the margin; the system does not produce a state in which a paying student arrives and has no meal.
## NOTE; this feels like a requirement. 

**A29. The order manifest is organised by session and by individual student.** Each meal is identifiable to whom it is for.

---

## Payment

**A30. Caterer payment information is derivable from orders and MOQ rules, not separately recorded.** What is owed to a caterer for a given week is a function of what was ordered and the MOQ floor. The system holds the inputs; the calculation is performed when needed.

---

## Absences

**A31. Absences are notified to Padea primarily through email from parents.** The system reads them from the email surface. Non-email sources are possible but exceptional.
## NOTE; this is a good assumption. reword to assume the edge cases out of existance. 

**A32. A parent who notifies an absence and later changes their mind (walk-back) is the same event arc, not a fresh event.** The absence record carries a "walked back at" timestamp that is set when reversal occurs. If a walk-back is itself walked back, a new absence record is created.

**A33. Whether an absence reaches the system in time to affect the order depends on when the absence was received relative to when the order for that session was sent.** This comparison is made at query time from the timestamps; there is no separate "pre-send vs post-send" state stored on the absence.

**A34. Anxious parents sometimes send the same absence notification multiple times.** The system handles duplicates without rejecting them — each notification is preserved as it arrived, while a single canonical absence record is used for downstream reasoning.

---

## Exclusions

**A35. An exclusion that cancels a whole session overrides the rule that dietary-restricted students always get a meal.** A school being physically closed means no student is on site to receive food; the safety case for making the meal anyway does not apply.
## NOTE; good assump reword more as an assump. 


**A36. Year-level partial exclusions accommodate the operational reality that some students whose year level is excluded attend anyway.** The order is sized larger than the strictly-remaining-cohort count, because social reality includes students who turn up despite a stated exclusion.
## NOTE; this is a decision that builds off the assump that we need a buffer the second we start cutting meals. this does open teh question of do students who are apart of the exclusion actually pay for the session, i think its safe to assume they do and then treat them as a student who if rocks up anyway needs a meal. 

**A37. Exclusions arrive from school administration, usually as year-level statements ("Year 12 is at camp Wednesday").** Where a school sends a list of individually-named students, those are treated as individual absences rather than as an exclusion.
## NOTE; definitely assume that any exclusions have been human checked and will be entered into the system manually or something similar. we shouldnt have to decipher which kids are atteingin a worship conference, swimming carnical or georgraphy camp. 

**A38. Subject-specific cohort cancellations (e.g. "Physics students are at a competition") are treated as individual absences rather than as exclusions.** Exclusions are reserved for cohort-level boundaries that align with how schools describe them.
## NOTE; maybe compress thiso ne into the previous one 

**A39. Exclusions, unlike absences, do not have a walk-back mechanism.** A reversed school decision is handled by superseding or removing the exclusion record manually rather than through a built-in reversal flow.


**A40. A whole-session cancellation arriving after the order has been sent is still recorded as an exclusion event.** The order cannot be undone, but the record exists for audit and for detecting recurring patterns.
## NOTE; this is an edge case worth assuming is outside of scope and requires human intervening. it contradicts our no changes to order past order date ideology, but also it would be silly to allow the meals to be delivered. 

---

## Feedback

**A41. Feedback flows through a small number of trusted channels rather than from every student per meal.** Per-student weekly meal ratings would produce noisy, biased data given realistic response rates; trusted-observer channels produce comprehensive coverage at lower cost.

**A42. Manager feedback covers one session at a time, with a rating and free-text comments.** Per-meal granularity is recovered later from structured signal extraction over the comment text.

**A43. Tutor feedback is identified internally but anonymised in any aggregate visible to caterers.** Identification is needed for reliability scoring and outlier detection; anonymisation protects tutors in caterer-facing comparisons.

**A44. The feedback rating scale used throughout is 1 to 5, with accompanying comments as the expected default rather than the exception.**

**A45. Feedback enters the feedback pipeline only when solicited.** Unsolicited messages — parent complaints, caterer concerns, ad-hoc observations — are operational events rather than feedback ratings, and are handled as escalations.

**A46. Term-survey respondents are pseudonymous: a consistent identifier per respondent across terms, but not linked to the respondent's real identity.** This preserves honest feedback while enabling longitudinal tracking of the same household over time.

**A47. A student who turns up at a session and is not on the enrolment list is operationally significant.** Walk-ups by unknown individuals need immediate attention; walk-ups by students whose absence was incorrectly notified are a parent-communication signal.

**A48. Caterer quality is computed from raw feedback at query time rather than from a stored aggregate.** Rater-baseline normalisation (some managers rate generously, others strictly) and submission-timing weighting (faster submissions are more reliable than later ones) are part of the computation.

---

## Agent operational behaviour

**A49. An agent run is a discrete invocation with a defined start and finish.** Each run is one entry in the operational record. A run that does not finish cleanly is a crashed run, detectable from later inspection.

**A50. Tool calls and reasoning branches are both treated as decisions in the operational record.** They share a common storage shape, distinguished by a type label rather than by living in separate places.

**A51. Decisions within a run can reference other decisions within the same run as their parents.** The structure of decisions is a tree, not a flat list.

**A52. Escalations resolve in one of two ways: the triggering condition disappears (auto-close) or a human responds with a closure action (human-close).** Both modes are available; the appropriate mode is part of the escalation's properties.

**A53. The same kind of issue, recurring multiple times, is the same escalation observed multiple times rather than multiple separate escalations.** Identity is established by a match key computed per escalation type.

**A54. Severity is assigned per escalation instance, not per escalation type.** The same kind of issue might be informational in one context and urgent in another, depending on what surrounds it.

**A55. Approval-shaped escalations carry the drafted action in their body. A human reply approving or dismissing closes the escalation; there is no separate "awaiting approval" state.**

**A56. Reply parsing for escalation closure relies on a subject-line token (e.g. `[PADEA-ESC-{id}]`) as the primary route, with fuzzy text matching as a fallback when the token is missing.**

**A57. Incoming emails are stored with their raw headers and bodies, both plain text and HTML where available.** Attachments are recorded by metadata only, not stored as content.

**A58. The agent's tool outputs are recorded as summaries in the operational record, not full outputs.** Full outputs would create disproportionate storage and would complicate later inspection.

**A59. The agent version and the model identifiers used in each run are recorded with the run.** This enables retrospective correlation of behaviour with system version.

**A60. Outgoing emails are handled by the agent's action layer rather than stored alongside operational data.** The data layer holds what entered and what was decided; what the agent sends is the action that follows.


## NOTE; the feedback and agent operational data doesnt make full sense to me yet. in the intiials we are using the weekly student survey based on parent allocated meals i believe. this is where feedback comes from. then in v3 we upgrade to the manager and tutor feedback with the termly surveys for students. importantly we are about to do decisions which all need to reference any relevant obvs reqs and assumps meaning the decision for this feedback system of v1 needs to build off these assumpts desing accordingly. you have more freedom with these two as i havent fully got my head around them. be careful no decisiosns here rebemember. 