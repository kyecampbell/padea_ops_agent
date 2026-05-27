v1 missed the edge case of when students join mid term. fix this. 

# V3 Working Notes

**Purpose:** Items flagged during V1 and V2 work that will inform V3 design. Living document. No polish required — this is a scratchpad that V3 will mine when it begins.

**Created:** [today's date]

---

## Schema fixes carried forward from V1 review

Four issues identified in the V1 schema that weren't V2 cut decisions — just schema problems to clean up in V3.

**feedback dual reference.** `feedback` has both `order_line_id` and `submission_token` pointing at the same `order_lines` row. Pick one as the canonical reference and remove the other. Token is the lookup mechanism at submission time; `order_line_id` is the resolved FK. Likely: keep `order_line_id` as the stored reference, drop `submission_token` from `feedback` (it's already on `order_lines`).

**caterer_school_capabilities mutable status.** `status` column flips between `currently_serving`, `able_to_serve`, `previously_served`, `confirmed_unable` with no record of when it changed. Effective dates exist but don't capture the status transition itself. Fix: either make status immutable by inserting a new row on each change (retiring the old with `effective_to`), or add a `caterer_capability_history` table on the same pattern as the other history tables.

**caterer decline floor has no home.** `caterer_decline_signals` references a per-caterer configured floor in its note but no column stores it. Needs a `quality_floor` column on `caterers`, or a dedicated config table if it needs to vary by school.

**margin config on orders.** `margin_meals_per_session` and `tutor_buffer_meals_per_session` are stored on every `orders` row. If they're operational constants they belong in a config table, not denormalised onto each order. If they're intended as per-order overrides (Dylan can adjust for a specific week) the note should say so and they stay.

---

## V1 oversights to fix in V3

Things V1 missed or under-handled. V3's job is to acknowledge and resolve them.

**Mid-term enrolment flow.** V1 schema technically supports mid-term enrolment (enrolments.start_date can be any date) but the V1 preference-capture flow assumes parents list options at the start of term. A student enrolling in week 4 has no preference data. V1 falls back to dietary-compatible defaults until parents respond, which is fragile. V3 should introduce an explicit mid-term-onboarding flow: detect new enrolment, immediately send parents the preference-options form, hold the student's first session in a manual-decision state until the form is returned or a configurable timeout passes.

---

## V1 features to reconsider in V3

Things V1 commits to that V3 may strip, refactor, or replace.

**ML absence prediction model.** V1 includes a calendar-aware absence prediction model using trailing rate, day-of-week, calendar-week-of-term, exam-period flag, public-holiday-adjacent flag, end-of-term flag, and per-parent false-absence rates. The point of including this in V1: make a real attempt at proactive margin sizing. The probable V3 conclusion: the model's predictions only marginally outperform a fixed margin, and the data infrastructure to maintain it (feature engineering, weekly retraining, per-parent stats refresh) is expensive. V3 likely cuts back to a simpler fixed-margin approach with a few obvious tweaks (e.g. fixed margin + day-of-week adjustment, no ML).

**Tutor meals buffer.** V1 includes extra meals provisioned for tutors who might want to eat at sessions, in addition to the operational margin and the partial-exclusion buffer. The point of including this in V1: tutors at long sessions sometimes eat student meals; the buffer prevents shortfalls. The probable V3 conclusion: tutors aren't paying for meals, the cost adds up across the network, and the savings from cutting the buffer outweigh the operational benefit. V3 likely cuts tutor meals entirely, perhaps replaced by a separate tutor-meal-ordering line item that isn't included by default.

**Feedback ecosystem overhaul.** V1 collects feedback only via weekly student ratings — the assumption is students rate their meals. The probable V3 finding: students don't reliably submit ratings, what comes in is biased (only kids who hated the meal submit), and the signal is too thin to support quality-decline detection. V3 pivots to a richer model with tutor feedback + manager feedback + term-end survey. This is a substantive design overhaul, not a tweak.

**Order economics simulation.** V1 computes and stores cost alternatives alongside each composed order (current variety, one tier above, one tier below, etc.) so the operator sees trade-offs explicitly. The probable V3 conclusion: the operator rarely overrides the agent's choice, the alternatives are computed but mostly unread, and the storage overhead isn't earning its keep. V3 likely simplifies to "agent picks, operator approves or revises."

---

## V1 features to deepen in V3

Things V1 includes lightly that V3 may invest further in.

*(Add items here as they come up during V1/V2 work.)*

---

## Open questions about V3 direction

Decisions we'd ask Dylan about, or that need evidence to resolve, before V3 work begins.

*(Add items here as they come up.)*