# Summary — PADEA Catering Agent V2

**Purpose:** What V2 does, in plain terms. Reads as a confident description of the system, not as a diff against earlier versions. The decisions and trade-offs that produced this scope live in `decisions_v2.md`; the data model lives in `schema_v2.md`.

**Compiled:** 26 May 2026
**Companion documents:** `decisions_v2.md`, `schema_v2.md`, `requirements_v1.md`, `assumptions.md`, `data_observations.md`.

---

## What V2 is

V2 is the lean system that remains after deleting everything not essential to the core weekly order workflow. It is the output of a deliberate deletion pass applied to V1's ambitious initial architecture. Features were removed unless they were load-bearing for the single workflow of: compose an order, send it, track the reply, surface anything a human needs to act on. Nothing was preserved on the grounds that it might be useful later.

V2 is intentionally stripped back and not final. It is a stable floor, not a ceiling. The features that were cut are documented here as deliberate weaknesses. V3 will evaluate each of them against a complexity/effort/value test before deciding whether to restore them.

V2 is one agent, doing one workflow, on one operational cadence — weekly, on Thursdays.

The agent's brain is Claude Sonnet 4.6 invoked via tool-calling. The agent's tools are typed Python functions over a single SQLite database that holds all operational state. The agent's output is a sent order (written to the outgoing email folder), an updated database, and a regenerated HTML decision log that makes every step the agent took inspectable.

---

## What V2 does, in order

A run begins by ingesting any new emails in the incoming folder. The agent reads each new email, classifies it (parent absence notification, caterer reply, or something else), and writes structured records to the database. Notifications it cannot confidently classify become escalations rather than guesses.

The agent then composes one weekly order per caterer that serves a session in the upcoming week. For each caterer:

It pulls the enrolment rows for every session that caterer serves. It removes students whose sessions are excluded for the week (whole-session exclusions remove all students; partial exclusions remove only the affected year levels). It removes students with absence records dated within the upcoming week. It removes students who have opted out of catering. From the remaining cohort, for each student, it picks one menu item that satisfies the student's dietary requirements and falls within the student's acceptable item list where one is recorded.

It then adds operational margin — a small uplift on the headline count to absorb walk-backs and unflagged attendees. It checks the result against the caterer's minimum order quantity at the chosen menu variety level. If the cohort plus margin falls below MOQ, it reduces variety by dropping the menu item the fewest students depend on, and re-checks. If MOQ cannot be met at the minimum variety level, the order does not send; the case escalates to the coordinator with the shortfall made explicit.

When the order is composed, the agent writes the email body to the outgoing folder, marks the order as sent, and records the meal assignments and email body on the order record itself.

After all caterers have been processed, the agent reviews caterer reply emails ingested at the start of the run. Orders with confirming replies are marked confirmed. Orders without replies and past the lead-time deadline are flagged for the coordinator.

Throughout, every tool the agent calls, every choice it makes, and every escalation it raises is recorded as a step on the run. At the end of the run, an HTML decision log is regenerated from the database. The log is the demo surface — it is what makes the agent's reasoning legible to the coordinator.

---

## What V2 escalates rather than handles

V2 escalates whenever a decision could damage a commercial relationship, where the data does not support a confident action, or where the situation is one V2 was not designed to handle. The escalation cases are deliberate:

A student whose acceptable items contain nothing compatible with their current dietary requirements. A cohort that cannot meet MOQ at any variety level. A caterer that has not confirmed an order by the required lead time. A whole-session cancellation arriving after the order has been sent. An incoming email the agent cannot confidently classify. Any tool error the agent does not have a recovery path for.

Escalations appear in the decision log as red cards and produce a summary at the top of the log identifying what the coordinator needs to act on. The agent does not attempt to autonomously route around any of these cases — that is for V3 to evaluate.

---

## What V2 explicitly does not do

V2 does not rotate caterers. It does not track palate fatigue or enforce variety beyond what falls naturally out of per-student acceptable lists. It does not collect or score student feedback. It does not route to alternate caterers when the primary doesn't respond — it escalates instead. It does not amend orders after they have been sent. It does not parse free-text parent emails for nuanced intent — it handles the routine absence-notification shape and escalates anything else. It does not send real emails — outgoing messages are written to a folder for the demo. It does not run on multiple agents or use a routing model — one model, one agent, one workflow.

Each of these is a candidate for V3, evaluated against whether the complexity cost is justified by the effort/value return.

---

## Known weaknesses deliberately created by V2

These are not oversights. They are features that existed in V1's scope, were cut in V2's deletion pass, and have been left absent intentionally. Each is a likely V3 candidate; none will be restored until V3's add-back pass evaluates them.

**No feedback loop.** Student preference satisfaction and quality decline over time are explicitly part of the brief. V2 makes no attempt to collect post-session feedback, score it, or act on it. The system has no mechanism to detect that a caterer's quality is slipping or that students are growing tired of specific items. This is the highest-value cut and the most likely V3 restoration.

**No caterer alternative/capability layer.** When a caterer does not respond within the lead-time window, V2 escalates and stops. It has no awareness of whether another caterer could serve the same session, no eligibility matrix to consult, and no mechanism to draft a swap proposal. Non-response escalates but does not propose a path forward.

**No historical or lifecycle modelling.** V2 records order history but does not use it. There is no variety rotation across weeks, no fatigue tracking, no detection of patterns across sessions or terms. The order history accumulates in the database but is invisible to the agent's reasoning.

**No feedback-driven quality monitoring.** Related to the feedback loop gap but distinct: even if feedback were collected, V2 has no quality-scoring model, no caterer performance record, and no trigger logic to act on declining scores. The quality-monitoring requirement in the brief is entirely unaddressed at V2.

**Meal assignments stored as JSON, not a table.** V2 stores per-student meal selections as a JSON blob on the order record. This is sufficient while feedback is absent, but if V3 restores the feedback loop, the system will need to know which student got which meal in a queryable form. The JSON column may need to become a proper `order_meal_assignments` table in V3. The schema should be designed with that migration in mind.

---

## How the system is shaped

Four components, in layers:

A SQLite database file in the project's `data/` directory holds all operational state. It is the source of truth for schools, caterers, menus, sessions, enrolments, exclusions, absences, orders, agent runs, and the per-step decision record.

A Python tool layer in `tools/` exposes typed functions for the agent to call — `list_sessions_for_week`, `get_enrolments_for_session`, `apply_exclusions`, `apply_absences`, `pick_meal_for_student`, `check_moq`, `send_order_email`, `log_step`, and so on. Each tool is a thin wrapper around database operations with explicit input and output shapes. Tools do not invoke the LLM; they are deterministic data operations.

An agent loop in `agent/run.py` orchestrates a workflow run. It constructs the system prompt for the workflow, hands the available tools to the Claude API, and iterates the tool-use loop until the workflow completes or the per-phase 15-call cap is hit. The cap is a safety against runaway loops, not a budget.

A decision-log generator in `viewer/build_log.py` reads the `agent_runs` and `agent_steps` tables and writes a single HTML file to `viewer/index.html`. The log is regenerated after every run. It is a flat file, not a server — it opens in any browser and shows the full timeline of what happened, colour-coded by severity.

---

## How V2 will be demonstrated

The five-minute demo video shows a run from start to finish. Before the run, the database holds the seeded source data (six schools, four caterers, eleven session slots, 320 enrolments, recent absences and exclusions). The incoming folder holds a handful of staged emails — a couple of parent absence notifications, a caterer reply confirming a prior order, an ambiguous email designed to escalate.

The run is invoked from the command line. The agent ingests emails, composes four caterer orders, sends them, processes the reply, and surfaces two escalations the seed data was designed to provoke: a student with an unsatisfiable dietary constraint, and a cohort below MOQ at a chosen variety level. The HTML decision log opens in a browser and walks through every step the agent took, with the escalations highlighted at the top.

The database is the deliverable for "Database Access" — committed as a `.sqlite` file in the GitHub repo, viewable via any SQLite browser, with a schema diagram in the repo's README. The decision log HTML is the deliverable for "Build Artifact" alongside the agent code.

---

## What V2 commits to about the data

V2 trusts the source data as given. Unusual prices, placeholder caterer-contact names, and routed email addresses are treated as intentional. Empty dietary cells are treated as "no restrictions" rather than missing data. Cross-school name matches are treated as different students by default. The non-pork-equals-halal rule from the menu legend is treated as authoritative.

V2 does not attempt to repair, infer, or second-guess input data. Where the data is ambiguous, the agent escalates. Where the data is clear but unusual, the agent proceeds.

The full set of foundational commitments lives in `assumptions.md`.

---

## What V3 will evaluate

V3 is a justified add-back pass. Each feature removed in V2 will be assessed against the question: does the complexity cost justify the effort/value return? Nothing is restored automatically. The known candidates, drawn directly from V2's deliberate weaknesses above:

The student feedback and rating loop — the highest-value gap. The caterer rotation and capability layer — drafting swap proposals against an eligibility matrix. Alternate-caterer routing when the primary does not respond. Free-text parent email parsing for absence intake. Per-day caterer capability granularity. Variety and fatigue tracking using the order history that V2 already records.

The meal assignments JSON-to-table migration is a dependency of the feedback loop and will be sequenced accordingly.
