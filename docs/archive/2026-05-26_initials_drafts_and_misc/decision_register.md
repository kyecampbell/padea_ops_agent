# PADEA Operations Agent — Decision Register (Working Draft)

> Working set of decisions assembled from: (a) the previous assumptions document migration list, (b) the data observations / requirements review, and (c) earlier conversations that locked in tooling and architecture. Some entries will be refined or split when this is formalised.

---

## 1. Architecture & Tooling

### 1.1 Database substrate
**Decision:** SQLite as the local development database, with Supabase as the shareable mirror.
**Why:** SQLite gives a zero-setup single-file dev loop on Kye's machine; Supabase mirror exists for sharing the working state with Dylan or for demo surfaces that need to be reachable.

### 1.2 Agent loop
**Decision:** Anthropic API tool-calling. Haiku 4.5 for routing, Sonnet 4.6 for harder reasoning. Cap of ~15 tool calls per agent loop.
**Why:** Tool-calling is the genuine agentic primitive (vs. prompt-chaining); the model split keeps cost down on routing while preserving quality where reasoning matters; the cap prevents runaway loops in V1 before observability is mature.

### 1.3 Demo surface
**Decision:** HTML decision log file regenerated after each agent run. Timeline layout, each step a card (timestamp, tool called, reasoning, result, flags), colour-coded green/amber/red.
**Why:** Makes agent reasoning visible. Turns the demo away from "did it succeed end-to-end" and toward "look how it considered options and escalated" — which is the actual value for an Operations Engineer role.

### 1.4 Email I/O for V1
**Decision:** Simulated email I/O via `emails/incoming/` and `emails/outgoing/` text files. No real Gmail integration in V1.
**Why:** Defers OAuth, deliverability, and any real-world send risk. Keeps the loop deterministic and replayable for the demo.

### 1.5 Workspace
**Decision:** VS Code as the editor; project lives at `~/Projects/padea_ops_agent/`.
**Why:** Already locked from prior setup work — moved out of iCloud Desktop to avoid sync corruption.

### 1.6 Build phasing
**Decision:** V1 ships the catering agent on a flexible general schema. V2/V3 add feedback sophistication, ML absence prediction, term surveys, and full agent observability.
**Why:** V1 must demo something impressive end-to-end; the more speculative pieces (prediction, survey design, deep observability) earn their place only after the core loop is real.

---

## 2. Schema Decisions

### 2.1 Dietary vocabulary
**Decision:** One controlled vocabulary for dietary tags, shared between tutors and students, with two junction tables (tutor↔dietary, student↔dietary).
**Why:** Tutors and students draw from the same real-world set of restrictions; duplicating the vocabulary across two entities invites drift. Junction tables keep the cardinality clean (a person can have many tags; a tag can apply to many people).
**Alternatives considered:** Separate vocabularies per entity; freeform text per person.

### 2.2 Manager presence
**Decision:** Captured as two timestamps on the session — expected arrival and actual arrival — rather than as a separate tutor-absence entity.
**Why:** A manager being late or absent is a property of the session itself, not a standalone event that needs its own lifecycle. Two timestamps let us compute lateness, no-show, and on-time without a join.
**Alternatives considered:** Dedicated `manager_attendance` table; boolean + reason field.

### 2.3 Weekly catering order shape
**Decision:** *Open within this decision* — the weekly cadence is locked (A23 in the new assumptions doc), but the storage shape is not. Two viable forms:
- (a) One row per session within a weekly composition (session-keyed line items)
- (b) One row per caterer-week with embedded line items per session
**Why this matters:** Affects how MOQ checks run, how amendments are applied mid-week, and how the manifest is generated. Need to pick before the catering agent's tool layer is written.

### 2.4 Operational margin sourcing
**Decision:** Margin meals drawn from the common-pool item set (broadly-appealing items), not from preference-matched or tutor-preferred items.
**Why:** A margin meal might be eaten by anyone — the session manager, a walk-up, a student who changed their mind. Pulling from the common pool maximises the chance the surplus is actually edible to whoever picks it up. Preference-matched margin assumes we know who the extra mouth is; we don't.
**Alternatives considered:** Per-student preference-matched margin; per-tutor preferred margin.

### 2.5 Dietary meals as a guarantee
**Decision:** Dietary-restricted student meals are always made, even when the session is at risk of cancellation or under MOQ pressure.
**Why:** Skipping a dietary meal isn't a cost optimisation — it's a safety failure for that student. The operational margin (2.4) and whole-session override (per assumption A29) cover the *why* it's affordable; this decision elevates dietary fulfilment to a non-negotiable.

### 2.6 Manifest organisation
**Decision:** Order manifest organised by session, then by student within session.
**Why:** The manifest is consumed by the caterer and the session manager. Both think in "this session, these students" terms — not "this tutor group, these students," which crosses session boundaries on shared-school days.
**Alternatives considered:** Tutor-group organisation.

### 2.7 Caterer payment storage
**Decision:** Caterer payments are *derivable* from orders, not stored as a separate payments table.
**Why:** Payment in V1 is a function of (catering_orders, caterer pricing). A separate table would duplicate truth and create reconciliation work. If V2 introduces partial payments, disputes, or credit notes, revisit.
**Alternatives considered:** Dedicated `caterer_payments` table.

### 2.8 Cohort cancellation handling
**Decision:** Subject-specific cohort cancellations are recorded as individual student absences (one row per affected student) rather than as a cohort-level event.
**Why:** Downstream consumers (catering, attendance reports, parent comms) all operate at the student level. A cohort-level event would need to be exploded into per-student records at query time anyway.

### 2.9 Post-send cancellation retention
**Decision:** When a whole session is cancelled *after* the catering order has been sent, the cancellation is still recorded as an exclusion in the system.
**Why:** The human handles the live caterer conversation (per assumption A33), but the record still matters for audit, billing reconciliation, and feedback context. Losing the data because "the human took it" creates blind spots.

### 2.10 Walk-up event capture
**Decision:** Walk-ups are a first-class table.
**Why:** Walk-ups have their own attributes (who, when, what they ate, why they were there) that don't fit cleanly on `sessions`, `students`, or `catering_orders`. Treating them as a side-table also makes them visible to feedback and quality aggregation without polluting the student roster.

### 2.11 Decision log structure
**Decision:** Tool calls and reasoning branches share a single `decision_logs` table, distinguished by a `type` column.
**Why:** They share most fields (timestamp, agent run, parent decision, content). Merging avoids two near-identical tables and lets the demo timeline iterate over a single ordered stream.
**Alternatives considered:** Separate `tool_calls` and `reasoning_branches` tables.

### 2.12 Decision tree shape
**Decision:** Decisions form a tree via `parent_decision_id`. No depth cap.
**Why:** Agent reasoning is naturally nested (consider option → sub-consider → tool call → result → next branch). A hard depth cap would force artificial flattening. The ~15 tool-call cap (1.2) bounds the overall size anyway.

### 2.13 Severity assignment for escalations
**Decision:** Severity is assigned per escalation *instance*, not per escalation type.
**Why:** Same type can be high or low severity depending on context (MOQ failure on Monday vs. Friday; one missing meal vs. ten). Per-instance severity preserves that flexibility.

### 2.14 Approval-shaped escalations
**Decision:** Escalations that need human approval carry the drafted action *in the escalation body*. No separate "awaiting approval" state in the state machine.
**Why:** Splitting "escalation" and "approval-pending action" doubles the state surface for negligible gain. If the human replies "yes," the agent executes the embedded draft.

### 2.15 Email subject protocol
**Decision:** Outgoing escalation emails carry a token `[PADEA-ESC-{id}]` in the subject for reply parsing. Fuzzy matching on subject and body is the fallback.
**Why:** Token-based matching is fast and unambiguous when the reply chain is clean. Fuzzy matching covers the case where the human strips the token, forwards from another address, etc.

### 2.16 Incoming email storage scope
**Decision:** Incoming emails are stored with raw headers and bodies. Attachments are metadata-only (filename, size, MIME type), not the bytes.
**Why:** Headers + body are cheap and forensically essential. Attachment bytes are expensive and rarely needed for the operational loop; if V2 needs them, the metadata gives us the hook.

### 2.17 Tool output storage
**Decision:** Tool outputs are stored as summaries, not full payloads.
**Why:** Full payloads (e.g. an entire roster query result) are large, repetitive, and reconstructible from the database state. Summaries keep the decision log readable and the storage cost bounded. Forensics still possible by replaying the tool call against the historical state.

### 2.18 Agent versioning
**Decision:** Agent version and model identifier (e.g. `sonnet-4-6`, `haiku-4-5`) are recorded per run.
**Why:** Behaviour will change as prompts and models change. Without per-run identifiers, "why did it do that last Tuesday" becomes unanswerable.

### 2.19 Outgoing email architectural placement
**Decision:** Outgoing email handling lives in the action layer, not the operational data cluster.
**Why:** Sending an email is a side-effect, not a record of business state. The operational cluster owns truth about catering, sessions, escalations; the action layer owns delivery mechanics. Keeping them separate means the operational schema doesn't need to know about retries, delivery status, or transport.

---

## 3. Operational Policy Decisions

### 3.1 Caterer rotation as escalation
**Decision:** Caterer rotation is a human-approved action, not autonomous. The system detects when rotation is warranted, proposes alternatives, and drafts comms — but the decision to rotate belongs to a human.
**Why:** Automatic rotation likely touches service agreements, notice periods, and commercial/legal terms the agent has no visibility into. Treating rotation as escalation honours that constraint without requiring the agent to model contract law.
**Surfaced consequence:** This is the canonical example for the escalation pattern in the demo.

### 3.2 MOQ exclusion for dietary meals
**Decision:** Dietary-specific meals do not count toward the caterer's minimum order quantity. A session with 18 standard + 4 dietary meals counts as 18 against MOQ, not 22.
**Why:** Dietary meals are typically priced and prepared separately, often by a different process or supplier line. Treating them as part of the MOQ count would either let us under-order standard meals (failing the MOQ silently) or over-rely on dietary headroom that isn't actually fungible.
**Surfaced consequence:** The MOQ-failure path fires earlier than naive counting suggests. Edge case to demo.

### 3.3 Feedback solicitation routing
**Decision:** Solicited feedback flows through the feedback pipeline. Unsolicited feedback (someone replies to an unrelated email with a complaint, or sends an out-of-band message) becomes an escalation.
**Why:** Solicited and unsolicited feedback have different shapes, timing, and trust properties. Routing them to the same pipeline would either pollute the feedback aggregates with off-prompt noise or starve the escalation queue of real issues.

### 3.4 Feedback model (V3 target)
**Decision:** Feedback collected via three channels — manager rating, tutor rating, and term-wide survey.
**Why:** Three vantage points (operational, peer, customer) triangulate quality better than any single source. This is the V3 target; V1 implements the ledger that V2/V3 will populate.

### 3.5 Manager rating shape
**Decision:** Manager rates the session overall with free-text comments. An LLM extracts per-item signals from the comments at aggregation time.
**Why:** Asking a manager to rate every dimension explicitly fatigues them and gets worse data. One rating plus prose, with extraction downstream, gets honest input and recovers granularity.

### 3.6 Tutor feedback privacy
**Decision:** Tutor feedback is identified at collection (so it's actionable) and anonymised in aggregates (so peers can't be reverse-engineered).
**Why:** Identification matters for follow-up; anonymisation matters for honesty. Both, at different stages of the pipeline.

### 3.7 Rating scale
**Decision:** 1-to-5 rating with comments expected by default.
**Why:** Five-point scales are familiar, have enough resolution to detect drift, and don't suffer the central-tendency bias of three-point scales. Comments-by-default trains the input habit before V3's extraction layer relies on them.

### 3.8 Term survey identity
**Decision:** Term survey respondents are pseudonymous, with a consistent ID across terms.
**Why:** Anonymity is required for honest customer feedback; consistency across terms is required to track whether a given parent's complaints are improving. A persistent pseudonym threads that needle.

### 3.9 Caterer quality aggregation
**Decision:** Caterer quality is computed at query time, with two corrections:
- Rater-baseline normalisation (some managers are harsher; subtract their personal mean)
- Submission-timing weighting (a rating submitted three weeks after the session counts for less than one submitted same-evening)
**Why:** Computing at query time means the algorithm can evolve without backfilling. Normalisation and timing weights are well-known corrections that improve signal without much code.
**Sub-decisions inside this one:** weighting function shape, normalisation window, minimum sample size before a caterer gets a published score — to be specified when the aggregation tool is built.

### 3.10 Agent run granularity
**Decision:** An agent run is a discrete invocation with explicit start and finish timestamps. Crashed runs are detected by a staleness threshold (started, no finish, no activity for N minutes).
**Why:** Discrete runs make the demo timeline coherent. Staleness detection means a crashed run doesn't sit in "in-progress" forever, blocking the next invocation.

### 3.11 Escalation closure mechanism
**Decision:** Hybrid closure. An escalation auto-closes if the underlying condition disappears (e.g. the missing student turns up). It closes on human reply otherwise.
**Why:** Pure auto-close misses cases where the human needs to acknowledge. Pure human-close clogs the queue with stale escalations the world already resolved. Hybrid covers both.

### 3.12 Escalation deduplication
**Decision:** Recurring escalations are deduplicated via an agent-computed match key (a hash of the meaningful fields, not a literal text match).
**Why:** "MOQ failure for Brisbane Grammar Monday session" should match itself across runs even if the wording drifts. Match key keys on identity, not prose.

---

## 4. Open Questions (Decisions Pending)

### 4.1 Late-cancellation handling policy
**Status:** Open.
**Question:** When a whole session is cancelled post-send, what does the human approver actually *do*? Options:
- Pre-commit to a policy (e.g. "always attempt to recall; if caterer refuses, eat the cost")
- Leave as case-by-case judgement and just surface the context to the human
**Why it matters:** Affects whether the agent drafts a specific recall message or a neutral "here's what happened" message.

### 4.2 Student rating intake channel
**Status:** Open.
**Question:** How do student ratings physically reach the system?
- Reply-to email (parsed)
- Web form (POSTed)
- Endpoint hit by a third-party form tool
**Why it matters:** Each option has different identity-resolution, spam, and timing properties. Affects the V2/V3 feedback ingest layer.

### 4.3 Default manager pattern prediction
**Status:** Open — worth interrogating whether this is needed at all.
**Question:** Should the agent predict which manager will run a session when the roster is incomplete? If yes, from what — historical assignment frequency, declared availability, both?
**Why it matters:** If prediction is needed, it's an ML/heuristic decision worth building right. If it's *not* needed, removing the assumption simplifies the schema. Lean toward removing unless evidence says otherwise.

---

## 5. Items to Flag for Dylan (May 27 meeting)

Compiled from across the decisions above where the answer benefits from Dylan's input rather than Kye's choice:

- **3.1 Caterer rotation** — confirm the assumption that rotation touches commercial/legal terms is correct, and confirm escalation (not autonomy) is the right shape.
- **3.2 MOQ exclusion** — confirm dietary meals are priced/counted separately by current caterers. If they're actually part of the same MOQ count, this decision flips.
- **4.1 Late-cancellation policy** — needs PADEA's actual stance, not Kye's guess.
- **4.2 Student rating intake** — does PADEA already have a preferred channel?
- **4.3 Manager prediction** — does Dylan see value in this, or is the manager assignment always known well in advance?
- **2.3 Weekly order shape** — not a Dylan question per se, but worth confirming whether current caterers expect a per-session manifest or a weekly bulk view.

---

*End of working draft. Next pass: split any entry where the "decision" is actually two decisions (e.g. 3.9), and write a one-line traceability note on each entry linking back to the assumption it discharges.*
