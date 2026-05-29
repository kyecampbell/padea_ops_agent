# PADEA Operations Agent — Final 16-Hour Ship Plan

**Submission deadline:** as set by competition
**Time available:** 16 focused hours
**Mode:** ship, not perfect. Cuts are justified in the memo, not hidden.

---

## 1. Where you actually stand right now

### What is built, working, and approved

- **The core agent loop (`src/agent/loop.py`)** is complete and proven in production: assistant/tool_result round-trip correct, reasoning captured from Claude's text blocks, hard cap of 20 with `is_error` propagation to all remaining tool blocks plus one uncounted final summarising call, `add_note` meta-tool logged inside dispatch, three distinct observation shapes (success / business-empty / system-error via `is_error`), and `safety_records` logged unconditionally by the loop (never at model discretion). Single-model Sonnet 4.6.
- **The full tool layer (21 tools)** built and approved across `infrastructure / sessions / absences / quality / caterers / orders / enrolments / meals`. Integer cents throughout. GST normalised to inclusive basis before any comparison. Delivery fee × sessions. Brisbane TZ + injectable `as_of` for time-dependent tools. ISODOW 1=Mon…7=Sun.
- **`system_prompt.md`** rewritten to the 5-step per-session pipeline. The 6 forbidden internal tools are explicitly named. Quality monitoring has a 24h skip-out (no new feedback → 1 call and done). One-session-per-run rule, self-selecting via `get_sessions_needing_orders` idempotency.
- **Option C (VO = vegetarian-option, safety-fallback model)** fully built and verified live: schema (`order_lines.variant`, `menu_items.has_vegetarian_option`), 15 VO items flagged + verified against the source PDF, selection chain (inherent-safe → VO fallback with `variant='vegetarian_option'` → escalate), email renders `⚑ VEGETARIAN OPTION`, ⚠ UNSAFE MATCH suppressed only for the vegetarian gap (still fires for any other uncovered tag), `vo_variant_requested` informational step logged by the loop.
- **Three real orders in the production Supabase DB:**
  - Order 132 — slot 3 / 2026-06-03 / Terrific / 33 students / $676.50
  - Order 133 — slot 11 / 2026-06-03 / GYG / 38 students / $570.00
  - Order 135 — slot 2 / 2026-06-02 / Terrific / 28 students / $574.00 (Pooja & Rashid fed via VO; Rashid on the halal VO item, not pork)
- **DB is Supabase** (`aws-1-ap-southeast-1.pooler.supabase.com`). Deliverable 3 (shareable DB link) is structurally handled.
- **Backup taken** at `backups/pre_option_c_2026-05-29.sql` before the only schema migration.
- **Memo and process diagram:** described as essentially done.

### What is NOT built

- **The Monday consolidated-summary workflow** — the second of the two core workflows. Aggregates the week per caterer (cost + GST + MOQ floor → payment figure), detects quality decline against the seeded Terrific decline, drafts a caterer warning email, and proposes a caterer-swap with cost projections. **This is the largest remaining build and the one that unlocks three new demo scenes.**
- **Real Gmail integration** — currently emails render to text. Will be replaced with real send/poll into a dedicated `padea-catering@gmail.com` so both sides of caterer correspondence can be shown on camera.
- **The decision-log / dashboard HTML renderer** — currently the only way to see what the agent did is to query `agent_steps` in psql. No visual artifact yet.
- **Video.**

---

## 2. Strategic decisions locked in

### Build order (and why)

**Monday workflow → Gmail → Dashboard/Renderer → Video.**

The renderer is the most visible thing and instinct says build it first. We are explicitly **not** doing that. Reason: the renderer surfaces data, and the most valuable surfaces (quality trends, weekly spend graphs, swap suggestions, warning emails) only exist *after* the Monday workflow has run. Building the renderer against current data and then expanding it once Monday is in would mean doing the visual work twice. Build the data first, render once against the final shape.

### Cuts justified in memo, not hidden

These are intentional, time-boxed decisions. Each is recorded in the memo as a defensible call, not as something unfinished:

| Cut | Memo framing |
|---|---|
| `order_lines` / tutor-meal-level feedback unseeded | Manager feedback carries the full decline→warning→RFP arc; meal-level escalation is additive and unnecessary for the core story |
| Hardcoded 8-postcode centroid dict (no live geocoding) | Fixed demo dataset; full postcode coverage proven; real system would geocode via API |
| Real Gmail outbound to actual caterers | Demo mode routes everything to `padea-catering@gmail.com`; production is a config swap (SMTP creds), not a redesign |
| Lowest-ID VO tie-break (vegetarian may receive a meat-named dish with ⚑ flag) | A VO dish is genuinely vegetarian-on-request; the ⚑ flag is unambiguous to the caterer; selection refinement is cosmetic |
| Location-unequal `room`/`building` rendering untested | All seeded slots have identical values; logic is correct by construction |
| Time-based scheduling / cron triggers | The agent is invoked with an injected `as_of` for deterministic demoability; production needs a scheduler, which is environment config, not core logic |
| Caterer-swap actually swapping the database row | Swap *suggestion* is built and demonstrated; the operator approves the swap manually in the real system; auto-mutation requires a human-in-the-loop step we deliberately do not automate |

### Scope cuts that are NOT in the memo (because they're done correctly)

- VO is a safety fallback only — never a menu item, never a preference, never served to a non-restricted student. This isn't a cut, it's the correct model.
- Single-model Sonnet 4.6 in the agent loop (Haiku lives only inside the future Gmail classification tool). This isn't a cut from the locked architecture; it's the architecture.

### What ALSO happens in the memo

The investigations are themselves the substance the task sheet rewards under "Learning":
- The VO discovery — finding the legend, recognising VO is make-to-order, building variant-aware ordering rather than mis-tagging.
- The STEP 4 first-run cap-hit and the prompt-side fix (model was working at the wrong altitude by calling `compose_session_order`'s internals by hand).
- The GST mixed-basis normalisation finding.
- The per-delivery-fee bug catch.
- The reasoning capture fix in the loop (had been hardcoded `None`, would have rendered every step with blank reasoning).
- The `compose_session_order` safety hole pre-Option-C: request-source meals previously skipped the containment check entirely; now they run it.
- The per-session vs weekly ordering rhythm rethink (the existing process is Thursday weekly batch; the system is per-session T-72h, which is more responsive to absences and enrolment changes).

---

## 3. Hour-by-hour schedule

Times are aspirational targets. The **hard rule**: at the end of each block, if it isn't done, freeze it and move on. Each block has a kill-switch.

### Block A — Monday workflow (Hours 0–6)

**Goal:** a second `run()`-style workflow that runs once a week per caterer, aggregating costs, detecting quality decline against the seeded Terrific drop, drafting a warning email, and suggesting a caterer swap.

**Build path:**
1. Design declaration (no code) — what tools the model calls, what the prompt section says, the call budget. Same protocol as the order-workflow prompt fix.
2. Schema additions if any (likely a `weekly_summaries` table or similar; possibly none needed if everything is computed from existing `feedback` + `orders` + `caterers`).
3. New section in `system_prompt.md` for the Monday workflow.
4. Live run against the seeded Terrific decline; expect the warning email + swap suggestion to fire.

**Deliverable:** A `run()` against `caterer_id=2 / week_of=2026-06-01` that produces, in the decision log:
- The aggregated cost figure (with GST, with MOQ floor if any).
- An `urgent` quality-decline detected step (rolling mean 2.3, below 3.0 floor).
- A `notable` warning-email-drafted step with the email body.
- A `notable` caterer-swap-suggested step with the proposed alternative + projected cost.

**Kill-switch at Hour 6:** if quality detection + warning email work but the swap suggestion is incomplete, ship without the swap. Note in memo. Three new demo scenes becomes two.

### Block B — Gmail (Hours 6–8)

**Goal:** real send + poll against `padea-catering@gmail.com`. Both order emails and Monday summary emails flow through it. Bonus demo surface: a caterer "reply" from a separate account triggers an inbound escalation.

**Build path:**
1. Create `padea-catering@gmail.com`. Use a Google account dedicated to this build; do not reuse personal.
2. Enable Gmail API access; create OAuth credentials or use an app password depending on which `gmail_send` implementation path is fastest. Store creds in `.env`, never commit.
3. Wire `gmail_send` into `TOOL_SCHEMAS` so the agent can actually use it (currently absent from the tool registry).
4. Wire `gmail_poll` for inbound (this is the more annoying half — Gmail API auth + parsing).
5. Add Haiku-based `classify_inbound_email` tool (this is where the locked architecture's Haiku-routing claim actually lives).
6. Live test: send an order email, reply from a personal account pretending to be the caterer, watch the agent classify and escalate.

**Kill-switch at Hour 8:** if outbound send works but inbound poll doesn't, ship with outbound only. Memo: "real outbound implemented; inbound classification scoped but deprioritised." If neither works, **fall back to demo mode (text file render)** and don't lose any more time. The order workflow + Monday workflow are the real exhibits; Gmail is a multiplier on them, not a prerequisite.

### Block C — Dashboard / Decision Log Renderer (Hours 8–13)

**Goal:** a single HTML page judges can open that shows the agent thinking and the system state at a glance. Built once against final data shapes.

**Three surfaces on one page:**

1. **Decision log timeline.** Every `agent_steps` row, newest first or grouped by `agent_run`. Each row shows step index, tool name, urgency (colour-coded: red=urgent / amber=notable / green=informational / grey=none), reasoning text, tool input (collapsed by default), tool output (collapsed). Filter by run, by urgency, by date.
2. **Current state.** Recent runs (last 7 days), recent escalations needing attention (all urgent + notable not yet acknowledged — though there is no acknowledgement field per V4, so this is just "recent"), upcoming sessions in the next 72h.
3. **Trend charts.** Per-caterer 4-week rolling quality score (line chart, with the 3.0 floor as a reference line and a marker where the Terrific decline crosses it). Per-caterer weekly spend (bar chart, last 4-6 weeks). Per-caterer MOQ shortfall events (sparse markers on the spend chart).

**Tech approach:** static HTML + a small Python build script that queries the DB and writes a self-contained file. No webapp, no server, no auth. The judges open `index.html` locally or it's hosted as a static file. Charts via a small library (Chart.js works, or just SVG if simpler). The page does not need to be live-updating — regenerate on demand with a build command.

**Why this approach:** no framework overhead, no deployment complexity, no auth setup, no maintenance after the demo. It also reflects the V4 principle that "the database is the source of truth; the decision log is a view onto it" — the renderer is literally a view, regenerated from the DB.

**Build path:**
1. Skeleton HTML + the build script that queries `agent_steps`, `agent_runs`, `orders`, `feedback`, `caterers`. Get the layout right first with placeholder data.
2. Decision log timeline (the highest-value surface — this is what makes the video land).
3. Current state panel.
4. Trend charts (lowest priority of the three — if time is tight, skip and explain in memo that the data is there, the rendering is the unfinished piece).
5. Style pass — clean, restrained, not flashy. The judging criterion "Taste" is about making things good for their own sake, which means *restraint*, not visual fireworks.

**Kill-switch at Hour 13:** decision log timeline alone is enough. Current state and trend charts are bonuses. Do NOT spend hour 12 polishing CSS if the timeline isn't done.

### Block D — Video and submission (Hours 13–16)

**Goal:** a ≤5 minute video showing the system running across the demo scenarios + everything packaged and submitted.

**Hours 13–14: stage and shoot.** Each scene gets a deliberate data setup → trigger → capture the run → capture the rendered decision log. See section 4 for the scenarios.

**Hours 14–15: edit and assemble.** Rough cut, no fancy editing. Title cards referencing the matching memo section. Voiceover or on-screen narration where needed.

**Hours 15–16: submit.**
- Final memo polish.
- Repo push to GitHub. Confirm `.env` is gitignored. Confirm `backups/` is gitignored if you don't want them in the public repo. Short README explaining how to run it.
- Confirm the Supabase project is shareable (read access via a project invite or a connection string that judges can use). Test the link from an incognito window.
- Compose the submission email to `dylan@padea.com.au` with all deliverables linked.
- Submit before 11:59 PM.

**Hour 16: buffer.** Submissions always run late. Build this in or you will be the person submitting at 11:58.

---

## 4. The demo scenarios

Each scenario is a deliberate data setup → trigger → captured output. The video is the concatenation of these. Each opens with a title card matching a memo section.

### Scenario 1 — Happy-path order composition

- **Memo section:** Order composition pipeline
- **Setup:** clean slot 11 (GYG, CHAC Wednesday). No dietary conflicts. Already proven live as order 133.
- **Trigger:** `as_of = 2026-05-31T16:00:00+10:00`
- **What it shows:** agent finds the session, composes the order in one `compose_session_order` call (not 8 individual ones), no escalations, ~6 tool calls. The decision log renders green top to bottom.
- **Voice-over point:** "this is the system running on a clean session — five tool calls and an order is in the database, with the caterer email composed and a full reasoning trail."

### Scenario 2 — Dietary safety: VO fallback (Pooja + Rashid + multi-restriction)

- **Memo section:** Dietary safety and VO handling
- **Setup:** JPC Tuesday (slot 2). Already proven live as order 135.
- **Trigger:** `as_of = 2026-05-30T16:30:00+10:00, window_hours=0.25`
- **What it shows:** Pooja (vegetarian) and Rashid (halal + vegetarian) both get fed via VO; Rashid specifically gets the *halal* VO item, not the pork one. Two `vo_variant_requested` informational steps appear in the log. The caterer email renders `⚑ VEGETARIAN OPTION` on those lines. No `no_safe_meal` escalations.
- **Voice-over point:** "VO means the caterer can prepare a dish vegetarian on request. The system treats it as a safety fallback only — never as a menu item, never as a preference, never served to anyone who doesn't need it. And critically, VO only forgives the vegetarian requirement — Rashid is also halal, so the system correctly excluded the pork dish even though it carries VO."

### Scenario 3 — Quality decline → caterer warning (needs Monday workflow)

- **Memo section:** Quality monitoring and caterer accountability
- **Setup:** Terrific has 55 manager feedback rows seeded with a sustained decline; 4-week rolling mean is 2.3, below the 3.0 floor.
- **Trigger:** Monday workflow against `caterer_id=2 / week_of=2026-06-01`
- **What it shows:** the agent computes the rolling mean, detects the decline, drafts a warning email naming the score and stating consequences. Urgent step appears in the log. The email body is visible in the renderer.
- **Voice-over point:** "this is what the system does that a Thursday weekly batch can't — it watches caterer performance over time and acts on it. The decline was real and the warning is drafted; the operator approves with one click."

### Scenario 4 — Caterer-swap suggestion (needs Monday workflow)

- **Memo section:** Caterer accountability and swap mechanics
- **Setup:** same Terrific decline. Other caterers exist within delivery range for the affected schools.
- **Trigger:** continues from scenario 3, or a separate Monday run.
- **What it shows:** the agent proposes alternatives within range, with projected weekly cost for each (GST-normalised, per-delivery × sessions). A notable step in the log shows the comparison. The decision is *suggested*, not executed — operator approves the swap manually.
- **Voice-over point:** "the system doesn't swap caterers autonomously — that's a relationship decision. But it does the analysis the operator would otherwise do by hand: who's in range, what would they cost, is the swap worth it."

### Scenario 5 — Inbound caterer message (needs Gmail)

- **Memo section:** Inbound handling and escalation
- **Setup:** send an email from a separate personal account to `padea-catering@gmail.com` saying something like "Hi, our fridge broke and we can't deliver Tuesday's order."
- **Trigger:** Gmail poll workflow or run trigger.
- **What it shows:** agent receives the email, classifies it (Haiku inside `classify_inbound_email`), recognises it as a delivery cancellation, escalates urgently.
- **Voice-over point:** "inbound handling closes the loop. The system doesn't just send — it listens, classifies, and escalates. This is the only place Haiku is used in the architecture: a fast cheap router on inbound, with Sonnet still doing all the reasoning work."

### Scenario 6 — Weekly cost summary (needs Monday workflow)

- **Memo section:** Money side
- **Setup:** Monday workflow against any caterer with multiple weekly orders.
- **What it shows:** the consolidated payment figure, GST line, MOQ floor applied if any. This is the canonical spending document.
- **Voice-over point:** "the per-session emails establish who eats what. The Monday summary is what we actually pay against. GST is normalised; MOQ floor is applied if the week ran short; one number per caterer per week."

### Scenario priority if time runs short

1. Scenario 1 (mandatory)
2. Scenario 2 (mandatory — this is the safety story)
3. Scenario 3 (if Monday workflow lands)
4. Scenario 6 (if Monday workflow lands)
5. Scenario 4 (if Monday workflow lands and swap logic works)
6. Scenario 5 (if Gmail lands)

If only 1+2 land: it's still a complete submission, with the rest scoped in the memo.

---

## 5. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Monday workflow takes longer than 6 hours | Medium-high | Cuts demo to 2-3 scenes | Hard kill-switch at Hour 6; partial Monday (cost summary without swap) is still a scene |
| Gmail OAuth setup wastes 2+ hours | Medium | Loses a demo scene | Hard kill-switch at Hour 8; fall back to text-render demo mode and move on |
| Renderer turns into a frontend rabbit hole | Medium | Eats time from video | Build script + static HTML, no framework, no deployment. Decision log timeline is the only must-have |
| Supabase link broken when judges try it | Low | Major (deliverable 3 missing) | Test from incognito at hour 15. Have a screenshot fallback in the memo |
| Video runs over 5 minutes | High | Penalised but not fatal | Stage scenes to be 30-45 seconds each. Cut ruthlessly in edit. The task sheet says max 5, don't push it |
| `.env` accidentally committed with API key or Gmail creds | Low | Catastrophic (revealed key) | Before pushing to GitHub: `git ls-files` and grep for sk-ant- or any creds. Revoke and rotate if found |
| Hour 16 arrives and submission isn't sent | Medium | Catastrophic | Buffer is built in. Submit at hour 15 if possible, even with rough edges. A rough on-time submission beats a polished missed one |

---

## 6. Repo hygiene checklist (Hour 15)

- [ ] `.env` is in `.gitignore` and not in the repo (check `git log --all -- .env` returns nothing)
- [ ] API key is not in any committed file (grep for `sk-ant-`)
- [ ] Gmail credentials are not in any committed file
- [ ] `backups/` is gitignored if backups contain real data you don't want public
- [ ] A short `README.md` explains: what the system does, how to run it (`python -m src.agent.run` or whatever the entry point is), where to find the decision log
- [ ] `CLAUDE.md` and `chat_history/` — decide whether to include these. They're great evidence of how AI was used (deliverable 6) but verbose. Either include and reference in the memo, or strip and reference selectively.
- [ ] Supabase project is set to allow judge access (read-only is fine; share via project invite link)
- [ ] The decision-log HTML can be opened locally with no setup (open `index.html` and it works)
- [ ] Process diagram exists as a PDF or PNG in the repo
- [ ] Memo exists as a PDF

---

## 7. Submission email checklist (Hour 16)

To `dylan@padea.com.au`, including:

- [ ] **Memorandum** — one-page two-column PDF
- [ ] **Process diagram** — flowchart of order → delivery
- [ ] **Database access** — Supabase project link, tested in incognito
- [ ] **Demonstration video** — ≤5 minutes, link (YouTube unlisted or similar)
- [ ] **Build artifact** — GitHub repo link
- [ ] **AI usage (optional but worth including)** — link to `chat_history/` in the repo, or a summary document

Subject line clear and parseable. Body brief — not a sales pitch. Names every deliverable with its link. Sent before 11:59 PM.

---

## 8. Conventions and invariants (do not violate)

These have been hard-earned across the build. Anything new must respect them.

- **Database connection:** `from src.ingest.db import get_conn` — context manager, writes commit, reads don't.
- **Time:** Brisbane TZ (`ZoneInfo("Australia/Brisbane")`), UTC+10 no DST. Postgres `time` columns come back naive — localise when building datetimes. Time-dependent tools take an injectable `as_of` (default `now(TZ)`) so tests and demos are deterministic.
- **Money:** integer cents end to end. No floats. GST normalised to inclusive basis before any comparison. Delivery fee × sessions, not flat per week.
- **Weekdays:** `day_of_week` and `EXTRACT(ISODOW)` are both 1=Mon…7=Sun.
- **Step urgency enum:** exactly `urgent` / `notable` / `informational` / `none`. No other values.
- **Agent model:** Sonnet 4.6 (`claude-sonnet-4-6`). Haiku lives only inside the future `classify_inbound_email` tool. The loop is single-model.
- **Tool-call cap:** 20. Worst-case single-session run is ~13 with all escalations and quality firing; 7-call headroom.
- **Core principle (non-negotiable):** tools are deterministic and dumb; the agent reasons. Gaps, failures, shortfalls, and unsafe matches are RETURNED as data so the agent surfaces and escalates them. Tools never silently filter or swallow.
- **Safety invariant for VO lines:** `safe = item_tags ⊇ (student_tags − {'vegetarian'})`. Only the vegetarian gap is forgiven; any other uncovered tag still makes the line unsafe and fires `⚠ UNSAFE MATCH` on the email.
- **Loop-owned logging is non-negotiable:** `safety_records` iteration after every `compose_session_order` and the `vo_variant_requested` step are written by the loop, not by the model. The model cannot opt out of the safety log.
- **Approval discipline:** small steps, declare tables/columns before coding, tests fail loudly on real bugs, STOP for approval, never self-mark approved. Builder writes the handoff file before any chat ends.

---

## 9. If a fresh chat needs to pick this up

Read in order:
1. This file (`PADEA_FINAL_PLAN.md`)
2. `CLAUDE.md` (build status; ▶ pointer)
3. The latest `chat_history/` session summary (the ▶ pointer target)
4. `docs/v4_optimised/Schema/v4_schema.sql`
5. `v4_summary.md` (the design doc that WINS on conflicts with `tools_reference.md`)

Then current state is unambiguous and the next build step is whichever block of section 3 hasn't been crossed off.
