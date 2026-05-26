# Assumptions — Padea Operations Agent

**Purpose:** What we are taking to be true where the source data, the brief, or operational reality leaves a gap. Each entry fills a gap by committing to one interpretation, so that downstream design has a settled foundation to build on.

**Compiled:** 25 May 2026
**Companion documents:** `data_observations.md`, `requirements_v1.md`, `decision_register.md`, `schema.md`.

---

## How to read this document

An assumption answers a question that the source material does not. The data does not say whether two students sharing a name at different schools are the same person; we have to commit. The brief does not say what happens when the human approver is unavailable for a week; we have to commit. Each entry below is one such commitment.

An assumption is not a design choice between equally workable options — that is a decision, and lives in the decision register. An assumption is not a thing the system must do — that is a requirement, and lives in the requirements doc. An assumption is the *foundation* on which requirements get derived and decisions get made.

Each assumption could be wrong. If operational reality contradicts one, this is the place to start before reworking anything downstream of it.

Assumptions are grouped by theme.

---

## Source data integrity

**A1. We assume the source data is accurate as given.** Pricing values that look unusual (Kenko $5.50, Lakehouse $35.00), placeholder caterer-contact names (`Big Mom`, `Big Chicken`, `Medium Giraffe`), routed emails (`dylan@padea.com.au` listed as a caterer contact), and the `dinner-time` column being recorded as a single timestamp rather than a window are all treated as intended for the purpose of this build. We do not second-guess input data on plausibility grounds.

**A2. We assume placeholder caterer contact emails are usable destinations during assessment.** Several of the listed addresses route to Padea-controlled inboxes (`carmen@padea.com.au`, `hellopadea@gmail.com`, `dylan@padea.com.au`). We assume outbound communications from the agent treat these addresses as live destinations rather than redirecting them to a sandboxed outbox.

**A3. We assume an empty dietary cell means no dietary requirements.** 253 of 320 students have a blank value in the dietary column. We treat this as a positive statement of "no restrictions" rather than as missing data — the source dataset was filled in deliberately, and blanks are intentional. If the gap were "not yet collected", the system's dietary safety floor could not function.

**A4. We assume any feedback originating in unstructured form (free text in an email, voice memo, a tutor's verbal observation) is converted to structured form upstream of the system.** The system reads structured feedback; the conversion step belongs to another component.

---

## Student identity and enrolment

**A5. We assume two students sharing a name at different schools are different people by default, including the cases where year levels match.** 13 names appear across two school sheets in the data; 7 of those have differing year levels (almost certainly different people), and 6 have matching year levels (which could plausibly be the same student enrolled at two schools, or two different students with the same name and year). Without identifiers that link records across sheets, the default treatment is non-collapse: each enrolment row represents a distinct student. Reconciliation remains possible later if evidence emerges.

**A6. We assume a student's year level is a property of their enrolment, not of the student.** The source data records year level per student per school. We treat year level as contextual to a period of enrolment, so that a student progressing year-to-year or attending multiple schools at different levels is represented as a sequence of enrolments rather than a mutating record.

**A7. We assume catering opt-out is a property of an enrolment.** The source data shows the opt-out marker appearing in the dietary column of student records, but offers no indication of how opt-out persists across terms or schools. We assume a student can opt out at one school and not at another, and can opt back in next term without overwriting prior history. The enrolment is where opt-out lives because the enrolment is what they are opting out of.

---

## Dietary interpretation

**A8. We assume non-pork menu items are halal.** The source data's menu legend states this explicitly. Halal eligibility is therefore derived from the absence of pork in a menu item rather than recorded separately. Items whose names contain pork or pork-products (bacon, pork) are non-halal; all others are halal.

**A9. We assume the `VO` annotation describes a caterer capability rather than a property of the item.** The source data uses `VO` to mean "vegetarian option available" — the item as listed contains meat, but the caterer offers a vegetarian variant on request. A vegetarian student matched to a `VO` item depends on the caterer making the swap.

---

## Caterer capability

**A10. We assume "able to serve" applies to the schools and days currently in operation, not to hypothetical future schedules.** The source data lists each caterer's "currently serves" and "able to serve" school sets. We assume capability extends to all currently-running sessions at those schools, but does not automatically extend to new sessions added later — because capability depends on scheduling, location logistics, and current operating conditions that may not hold for new arrangements.

**A11. We assume a caterer can serve multiple schools on the same day where capability and logistics permit.** The data shows GyG serving both Loreto and CHAC on Monday 1 May at the same 5:00pm dinner time. The two schools share a region (Central Brisbane) and the caterer evidently handles both deliveries within their operating capacity. We do not assume a one-school-per-day ceiling; the operational data captures which schools each caterer currently serves on each day, and same-day concurrency is treated as feasible where the existing operation already demonstrates it.

**A12. We assume capability is granular to (caterer, school, day-of-week).** A caterer who can serve a school on Monday is not automatically able to serve it on Thursday. Different days have different scheduling, traffic, and competing-commitment constraints. A school adding a new session day requires a fresh capability confirmation from the caterer.

**A13. We assume distance feasibility, kitchen capacity, and time-window constraints are already absorbed into the "able to serve" capability list.** When a caterer is listed as able to serve a school, we take those three constraints to be satisfied for that combination. They do not need to be modelled separately.

**A14. We assume falling below a caterer's MOQ results in a financial penalty.** The source data does not specify what happens when MOQ is not met, but the term itself implies a binding minimum. We assume the operational consequence is that Padea pays for the MOQ floor regardless of whether the meals are needed — the shortfall is a commitment, not a discount.

---

## Caterer contacts

**A15. We assume the name-to-email pairings in the contacts data are as given, even where they appear inverted.** Earlier readings of the data as containing errors are superseded by the placeholder nature of the data. No repair is attempted at ingest.

**A16. We assume any caterer contact can carry any combination of four roles: order-taker, chef, primary-contact, and cc-on-orders.** The data shows multiple role combinations across the six contacts. We do not constrain which combinations are valid; the system accepts whatever the data presents.

---

## Managers and tutors

**A17. We assume managers are tutors carrying a per-session manager role.** The data does not provide a separate manager population; the same names appear as managers at some sessions and as tutors at others. We treat the manager role as a property of a session-assignment, not as a property of a person.

**A18. We assume the tutor record holds only what the catering system needs.** Tutors are people whose broader record (subjects taught, qualifications, employment history) lives in other Padea systems. For catering purposes, we need identity and contact. Anything more is out of scope.

**A19. We assume a session has both an expected manager (set in advance) and an actual manager (recorded after the fact), and that the two may differ when cover is needed.** The data captures expected assignments; the operational reality includes last-minute swaps. By recording both, the difference between them captures cover events without needing a separate concept of tutor absence.

---

## Session structure

**A20. We assume sessions are 180 minutes long with the dinner break centred at the 90-minute midpoint.** Every session in the dataset runs for exactly 3 hours, with the dinner-time value falling exactly at the midpoint. We treat this as a structural rule of how Padea sessions operate, not a coincidence of this week's scheduling.

**A21. We assume the dinner break lasts 30 minutes.** The source data records only the dinner start time; the project context indicates a 30-minute duration. We take the 30-minute figure as authoritative and treat the source data as recording only the start time of the dinner window.

**A22. We assume no school has more than one session on the same day.** No double-session-per-day case appears in the dataset. We treat one session per school per day as a structural rule.

---

## Order timing and weekly cadence

**A23. We assume each caterer's weekly order is composed once, with the full week's sessions in view, and sent with adequate lead time before the earliest session of that week.** The current Thursday-for-following-week operation provides evidence that this cadence is feasible. With the whole week visible at composition time, the MOQ check is performed once against full weekly demand rather than per-session.

**A24. We assume the order, once sent, is not amended for subsequent absences or walk-backs.** Caterers prepare meals on a schedule that does not tolerate late changes; amending the order downstream of the send would create caterer-side disruption disproportionate to the gain. Late absence handling instead relies on operational margin within the order.

**A25. We assume an operational margin is required the moment we begin cutting meals in response to absences or exclusions.** Without a margin, any student whose absence is walked back arrives with no meal. The margin's purpose is to absorb walk-backs and the operational reality that absence notifications are not perfectly reliable. It is not for unenrolled visitors — unenrolled people have not paid for a meal and the system does not provision for them.

---

## Absences

**A26. We assume absences reach the system primarily through parent email, and that this is the dominant intake channel.** Other intake routes exist but are exceptional. The system reads from the email surface as its primary source of absence data.

**A27. We assume a parent who notifies an absence and then changes their mind is the same event, not a fresh one.** The absence record carries a reversal timestamp that is set when the walk-back occurs. A walk-back of a walk-back creates a new absence record rather than re-flipping the original.

**A28. We assume parents sometimes send the same absence notification multiple times.** Anxious parents send duplicates; some forward the original email back as confirmation. We assume duplicates will occur and that the system must handle them without rejecting them — each notification is preserved as it arrived, while a single canonical absence record is used for downstream reasoning.

---

## Exclusions

**A29. We assume exclusions that cancel a whole session override the rule that dietary-restricted students always receive a meal.** A school physically closed for the day means no student is on site to receive food. The walk-up-insurance reasoning that protects dietary-restricted students in normal operation does not apply when the session is not running.

**A30. We assume students whose year level is part of a partial exclusion are still paying for the session.** The data does not state otherwise, and partial exclusions are short-term events (camps, school activities) rather than enrolment changes. Where such a student attends the session anyway, they are treated like any returning student who needs a meal — the operational margin covers them.

**A31. We assume exclusions arrive at the system after a human has filtered them.** The source data shows exclusions as text statements from school administration. We assume the system receives exclusions that have been read by a human and entered (or routed) into the system manually — the system does not need to disambiguate which kids are at which camp or activity from free-text emails. Subject-specific cohort cancellations (e.g. "Physics students at a competition") would also reach the system as pre-filtered information rather than as parsed-from-text.

**A32. We assume exclusions do not have a walk-back mechanism analogous to absences.** A reversed school decision is rare enough that handling it manually — by removing or superseding the exclusion record — is acceptable. Building a reversal flow would over-engineer for an edge case.

**A33. We assume a whole-session cancellation arriving after the order has been sent requires human intervention and is outside the system's automated scope.** This contradicts the general rule that orders are not amended post-send, but allowing meals to be delivered to a closed school is unacceptable. We assume the human approver handles such cases manually, balancing caterer relationship and operational cost.

---

## Feedback in the initials state

The initials design captures feedback through a weekly student-rating flow. Parents select acceptable meal options for their child at the start of each week, the system orders an acceptable meal for each student from within those options, and students rate the meal after the session. The assumptions in this section describe the gap-filling commitments that make this flow workable.

**A34. We assume parents are in a position to know their child's acceptable meal options on their behalf each week.** The brief does not specify who knows student preferences. We assume parents can, in practice, identify which meals their child is willing to eat from a list of available options — possibly by asking the child, possibly by knowing from experience. Where this assumption fails, the household can adapt by handing the selection to the student directly.

**A35. We assume the parent-facing meal list is pre-filtered by the system to exclude items incompatible with the student's dietary requirements.** Showing parents items their child cannot eat would be confusing and would risk a parent selecting an inappropriate item by mistake. We assume the filtering happens before the list reaches the parent.

**A36. We assume students can be expected to rate the meal they were served.** The brief does not establish that students will participate in rating; we assume they will at a rate sufficient to produce useful signal. Where participation is low, the rating data will be noisy; we accept this for the initials design.

**A37. We assume student ratings remain Padea's property and are not visible to caterers in a form that identifies individual students.** The privacy expectation is implicit in any feedback system involving minors.

---

## Operational environment

**A38. We assume the dataset week (1–4 May 2026) is a representative sample of normal operation, not a one-off configuration.** The system is designed to handle the patterns visible in this week — the school list, the session schedule, the caterer assignments, the absence and exclusion rates. It is not tied to these specific dates, and we assume future weeks will look broadly similar in structure even as specific values change.

**A39. We assume students and households communicate primarily through email, or through channels that someone forwards into email before reaching the system.** The system reads from an email surface. Direct SMS or voice intake is out of scope.

**A40. We assume the human approver is available to respond to escalations within reasonable business windows.** Extended unavailability is rare and handled by advance configuration of a delegate. The system does not need to handle indefinite approver absence as a primary case.

**A41. We assume caterers respond to orders within a reasonable window in the routine case.** The system handles non-response as an escalation, but assumes the underlying business relationship is functioning. A caterer who is chronically non-responsive is replaced through the rotation mechanism rather than worked around indefinitely.

**A42. We assume automatic caterer rotation would touch service agreements, commercial relationships, and possibly legal terms that the system is not equipped to manage.** This makes rotation a human-judged action. The system's role is to surface the need and prepare the action, not to execute the rotation autonomously.

---

## Open questions to discuss

Two items came up during the assumptions work that may warrant new assumptions but need a short discussion before locking.

**On the late-cancellation edge case (A33):** The assumption says the human approver handles late session cancellations manually. We have not committed to *what they do* — call the caterer to cancel, accept the delivery and donate the food, pay the caterer regardless? The assumption is that this is human-judged; whether we need to pre-commit to a policy is open.

**On the feedback flow in the initials state:** The student-rating model assumes ratings flow back into the system somehow (A36). We have not stated *how* ratings reach the system — another email, a form, a simple endpoint. This is closer to a decision than an assumption, but the data flow's existence is an assumption underneath the decision.
