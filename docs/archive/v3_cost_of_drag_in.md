# PADEA Operations Agent — V3 Cost-of-Drag-In Pass

This document is the honest accounting of what V3 added back compared to V2's lean 10-table baseline. Direct memo material — the numbers and verdicts here feed the submission memo. Companion documents: `v3_reinstatements_ledger.md` (all ten V3 decisions), `cuts_v1_to_v2.md` (V1→V2 cut ledger), `summary_v2.md` (V2 baseline), `v3_edge_cases.md`, `memo_notes.md`.

The structure is four passes: schema delta, tool layer delta, operational surface delta, then the honest read on where it earns its weight and where it might not.

---

## 1. Schema delta — table-by-table accounting

### V2 baseline (10 tables)

`schools`, `caterers`, `menu_items`, `enrolments`, `absences`, `session_slots`, `exclusions`, `orders`, `agent_runs`, `agent_steps`.

### V3 added tables (9 new)

| New table | Source decision | What it carries | Why earned |
|---|---|---|---|
| `tutors` | V3-IL-01 (required by V3-FB-01) | tutor identity (name, email, mobile) | Per-tutor feedback attribution; cross-session identity for rater tracking |
| `session_tutor_assignments` | V3-IL-01 | (session, tutor, is_manager, is_tutor) | Dual-role manager-tutor model; per-date manager variation |
| `order_lines` | V3-FB-01 (promoted from V2 JSON) | per-meal-per-kid rows | Per-meal feedback attribution; named allocations in order emails |
| `feedback` | V3-FB-01 | polymorphic (tutor/manager) ratings + comments | The whole quality picture closes on this table |
| `dietary_tags` | V3-FB-01 | extensible taxonomy | Replaces V2's JSON `dietary_flags` |
| `enrolment_dietary_tags` | V3-FB-01 | junction (enrolment → dietary tag) | Same as above |
| `term_meal_preferences` | V3-FB-01 | per-enrolment-per-caterer approved meal set, supersession-aware | Parent's term-start submission lives here; tutor-led reset on caterer change re-populates it |
| `meal_requests` | V3-FB-01 | per-kid per-session one-off override | The "I want chilli chicken next week" release valve |
| `outbound_emails` | V3-CM-01 | every system-sent email with status lifecycle | Full audit; failure handling; commercial-approval workflow |

**Net: V2's 10 → V3's 19 tables. Roughly doubles the table count.**

### V3 modified tables (V2 tables with new columns or dropped columns)

| Table | Change | Source decision |
|---|---|---|
| `caterers` | + `home_postcode` (text) | V3-CR-01 |
| `caterers` | + `max_delivery_km` (int, default 50) | V3-CR-01 |
| `caterers` | + `canonical_menu_order` (JSON list) | V3-OC-01 |
| `schools` | + `postcode` (text) | V3-CR-01 |
| `enrolments` | + `original_start_date` (date, not null) | V3-EL-01 |
| `enrolments` | + `current_period_start_date` (date, not null) | V3-EL-01 |
| `enrolments` | + `current_period_end_date` (date, nullable) | V3-EL-01 |
| `session_slots` | + `room` (text, nullable) | V3-AI-01 |
| `session_slots` | − `manager_name` (DROPPED in V3 migration) | V3-IL-01 |
| `session_slots` | − `manager_phone` (DROPPED in V3 migration) | V3-IL-01 |
| `orders` | − `margin_meals_per_session` (DROPPED) | V3-MP-01 |
| `orders` | − `tutor_buffer_meals_per_session` (DROPPED) | V3-MP-01 |
| `orders` | + rotation-escalation status (existing field repurposed or new column TBD in schema rewrite) | V3-FB-01 |
| `orders` | + preview-week flag | V3-FB-01 |
| `orders` | − `meal_assignments` JSON (REMOVED — promoted to `order_lines` table) | V3-FB-01 |
| `agent_steps` | `severity` text replaced with `urgency` enum (urgent/notable/informational/none) | V3-OE-01 |
| `absences` | + `source_email_message_id` (nullable text, in addition to existing `source_email_filename`) | V3-CM-01 |

**Net: 14 new/modified column-level changes across V2 tables. Five columns dropped (clean wins).**

---

## 2. Tool layer delta

V2's tool layer is small — order composition, parser tools for the simulated email folders, basic database CRUD. V3 adds significantly more agent surface.

### New deterministic tools introduced

| Tool | Decision | Purpose |
|---|---|---|
| `gmail_send(to, cc, subject, body, email_type)` | V3-CM-01 | Real outbound email via Gmail API |
| `gmail_poll_inbox(since_timestamp)` | V3-CM-01 | Real inbound polling |
| `gmail_get_message_body(message_id)` | V3-CM-01 | Full-body fetch when classification needs more than headers |
| `caterers_within_range(school_id)` | V3-CR-01 | Distance query via postcode lookup (wraps geopy) |
| `project_weekly_cost(caterer_id, school_id)` | V3-CR-01 | RFP-time projected cost computation |
| `compose_session_order(session_id)` | V3-AI-01 | Per-session order composition, draft, send |
| `compose_weekly_summary(caterer_id, week_start)` | V3-AI-01 | Monday 3:30 PM consolidated summary, draft, send |
| `compute_canonical_menu_order(caterer_id)` | V3-OC-01 | Popularity-ranked snapshot at term start / caterer change |
| `get_enrolments_for_session(session_id, date)` | V3-EL-01 | Date-parameterised enrolment query |
| `get_enrolment_history(enrolment_id, date)` | V3-EL-01 | Historical state reconstruction for incident investigation |

**Net: ~10 new tools. V2 had roughly 6 tools.** Roughly doubles the tool surface.

### New agent reasoning capabilities (not deterministic tools, but agent logic)

- Per-caterer rolling-mean computation (4-week + 12-week with absolute floor) — V3-FB-01
- Single-week escalation evaluation (manager 1-2, student-avg 1-2, tutor-1 pattern) — V3-FB-01
- Sustained-decline detection triggering warning email draft — V3-FB-01
- Rotation chain composition (warning → RFP → cancellation → preview week) — V3-FB-01
- Inbound email classification into one of 5 domain types — V3-CM-01
- Idempotent classification dedup via gmail_message_id — V3-CM-01
- Per-session order composition with meal_request override + canonical-order rotation — V3-FB-01 + V3-OC-01
- Opt-back-in email firing with send-once tracking — V3-MP-01
- Decision log per-run regeneration with weekly grouping and three-tier urgency sort — V3-OE-01
- Weekly report generation (cross-school visual, cost panel) — V3-FB-01 + V3-OC-01

**Net: 10 new agent reasoning patterns** — these don't add tables but they're real cognitive surface the LLM has to handle correctly.

---

## 3. Operational surface delta

### Email type enum

V2: 1 email type (the simulated weekly order, not even formally enumerated).
V3: 11 canonical email types — `session_order`, `weekly_consolidated_summary`, `warning`, `rfp`, `cancellation`, `rfp_loser_courtesy`, `parent_enrolment`, `parent_reminder`, `opt_back_in_request_to_parent`, `operator_notification`, `other`.

**Net: 1 → 11. Order-of-magnitude growth in email surface.** Each one has its own template, its own approval logic (autonomous vs queued), its own classification rule on inbound.

### Operator-facing surfaces

V2: HTML decision log, generated once per Thursday run.

V3:
- HTML decision log, regenerated after every run (5-7 times per week), grouped by week, three-tier urgency sort, colour-coded
- Weekly cross-school report with cost + quality panels (Friday read)
- Decision log "current quality picture" panel per caterer
- Tutor app per-kid post-dinner box (rating + comment + meal request picker) [V3 describes; simulation handles for demo]
- Tutor app opt-back-in checkbox surface [V3 describes]
- Manager app session report (food score + checklist + meals-left + names) [V3 describes]
- RFP response comparison panel (per respondent: price, projected cost, delivery fee, lead time, start date)
- Operator approval queue for commercial-relationship emails (warning, RFP, cancellation, RFP loser courtesy)

**Net: 1 → 8 distinct operator surfaces.** Some are simulated rather than built (tutor app, manager app), but each is a real operational concept V3 commits to.

### Cadence and runtime

V2: 1 run per week (Thursday 3 PM).
V3: 5-7 runs per week (per-session T-72hrs + Monday 3:30 PM consolidated), autonomous through weekends, cron-style scheduler.

**Net: ~6x more runs per week.** Each run is smaller and more focused, but the runtime footprint is real.

---

## 4. The honest read — where it earns its weight, where it might not

### Where V3 clearly earns the cost

**The feedback ecosystem (V3-FB-01).** This is the biggest cost — 4 new tables (`tutors`, `feedback`, `term_meal_preferences`, `meal_requests`) plus `order_lines` promotion plus `session_tutor_assignments`. It also drives the largest set of agent reasoning patterns (rolling means, decline detection, rotation chain).

**Verdict: clearly earns it.** The brief names food quality maintenance as one of two top concerns. Without this group, V3 has no signal on food quality and no mechanism to act when it declines. The cost is the value.

**Real Gmail bidirectional (V3-CM-01).** One new table (`outbound_emails`), three new tools (send, poll, fetch), 11 email types. Demo-mode address rewrite flag. Approval workflow for commercial messages.

**Verdict: clearly earns it.** Demo-day Taste call. Without it, the demo shows simulation; with it, the demo shows a working system. The brief's "Functionality" and "Taste" criteria both reward this. The audit table is a genuine operational asset.

**Per-session cadence (V3-AI-01).** No new tables (existing ones extended), but a meaningful architectural shift. Cron-style scheduler, weekend autonomy, two new email templates, Monday consolidated summary as canonical spending document.

**Verdict: clearly earns it.** Demo narrative ("we noticed the existing cadence was a human-calendar artifact") directly hits the brief's "make requirements less dumb" framing. Fair to every caterer. Late-absence handling tightens.

### Where V3 earns it but barely

**Date-driven enrolment lifecycle (V3-EL-01).** Three new date columns on enrolments. Two new tools (date-parameterised queries). Discipline of "every query takes a date parameter" across the tool layer.

**Verdict: earns it through unblocking.** Standalone the brief doesn't name lifecycle as a problem. But it unblocks the safety traceability scenario (was Sam at MBBC on March 14th?), continuous-across-terms operation, and re-enrolment cases. Three date columns is genuinely cheap. The accepted dietary-history gap is a memo flag, not a system feature.

**Distance-radius RFP targeting (V3-CR-01).** Three new columns (caterer postcode, caterer max_delivery_km, school postcode). One new tool. No new tables.

**Verdict: earns it because the rotation chain depends on it.** Without V3-CR-01, V3-FB-01's RFP step has no recipient list. The cost is genuinely 2/5 complexity — three columns and a geopy wrap is minimal. The cut version of V1's capability matrix would have been 4/5. This is a clean win.

**Three-tier escalation urgency (V3-OE-01).** One enum field change. Sort + colour logic in the decision log renderer. Per-run regeneration with weekly grouping.

**Verdict: earns it as V3's escalation volume grew.** V2 worked without tiers because operator read everything. V3's 8-10 escalation types make scan-ability genuinely useful. Cost is 1/5 — basically a free win.

### Where V3 paid a real cost for something deletion-shaped

**Zero operational margin + walkup deletion (V3-MP-01).** This is the "we deleted the part" success. Two columns dropped from V2 (`margin_meals_per_session`, `tutor_buffer_meals_per_session`). One small addition (opt-back-in checkbox + send-once tracking). No prediction infrastructure. No reconciliation table.

**Verdict: pure win.** Net subtraction from V2's complexity in exchange for explicit operational rules ("walkups suffer one week of no-meal" as forcing function). Memo-worthy.

**Cutting the caterer_school_capabilities matrix (V3-CR-01).** V1 wanted a full relational matrix. V3 replaced it with three columns. Easily the biggest "deletion ledger" win in the document.

**Verdict: pure win.** Strong Learning-criterion sentence — "we considered it carefully and rejected it for V3" — and the document explains why thoroughly.

### Where I'd flag honest concerns

**The feedback ecosystem is the V3 darling but also its biggest fragility.**

The whole quality story depends on tutors and managers actually filling in the boxes consistently and using the 1-5 scale with calibrated meaning. The system surfaces this as a "memo flag: training is a system precondition" — which is honest, but it also means a real chunk of V3's value lives outside the system, in human discipline.

If tutors don't fill in boxes well, the rolling means are noisy, the decline detection fires false positives or misses true ones, and the rotation chain loses credibility. The fix in V4 (rater normalisation, divergence detection) addresses this — but at V3 demo time, a judge could reasonably ask "what if tutors don't probe the 1-5 anchoring?"

The honest answer is: the data quality risk is real, the system can't fix it alone, and that's why training is named as a precondition. Worth being explicit about this in the memo.

**The popularity-ranked canonical order is a small-but-clever feature with a long explanation.**

The popularity snapshot at term start + caterer change does real work for MOQ alignment, but it's a non-obvious mechanic. The memo flag describes it well — "kids with overlapping preferences tend to land on the same meal in the same week without any explicit clustering" — but a judge skimming might not immediately see why this is clever.

Worth a 1-sentence demo callout: "we sort the menu by popularity once per term so kids' rotations cluster naturally and we beat MOQ more often."

**Real Gmail introduces a real operational dependency that the demo needs to handle gracefully.**

OAuth token expiry, demo-mode flag, Gmail spam filtering on first sends. Each is memo-flagged. But on demo day, any of these going wrong is visible to judges. The mitigations (default to demo mode, env-variable check at startup, "warmup" emails) are right but not zero-risk.

Worth running the full email flow once a day for the three days leading up to the demo so the account is warmed up and the OAuth token is fresh.

**Per-session cadence creates more runs but also more opportunities for runs to silently fail.**

V2's single weekly run was easy to notice if it didn't fire. V3's 5-7 runs per week means a silent failure on a Saturday Friday-for-Tuesday run might not get caught until Monday's consolidated summary surfaces the discrepancy. Idempotent runs reduce risk but don't eliminate it.

Worth a small "run-success" log surface — even just a one-line confirmation in the decision log after each run — so the operator can confirm at a glance that all expected runs fired on time.

---

## Bottom line for the memo

- **Tables:** V2's 10 → V3's 19 (and 5 V2 columns dropped, ~14 added).
- **Tools:** V2's 6 → V3's ~16.
- **Email types:** V2's 1 → V3's 11.
- **Operator surfaces:** V2's 1 → V3's 8.
- **Run cadence:** V2's 1/week → V3's 5-7/week.

**The big wins (clearly earn the cost):** Feedback ecosystem (closes brief's #1 and #2 named problems), real Gmail (Taste + Functionality), per-session cadence (Learning-criterion "less dumb requirements" sentence).

**The clean deletes:** Caterer capability matrix (replaced by 3 columns), zero operational margin (cut prediction/reconciliation/buffer stack), V2 manager_name/manager_phone columns (replaced by per-session assignment table), all history tables.

**The deferred-with-trigger items:** ML predictions, payment integration, PII/auth, attendance system integration, cross-school identity, mid-term enrolment automation, dietary severity, network analytics — 14 explicit V4 build triggers documented.

**The honest concerns:** Tutor/manager training is a real system precondition the demo needs to acknowledge. Real Gmail has demo-day operational risk. Per-session cadence amplifies silent-run-failure risk. Popularity-rank canonical order is clever but needs a 1-sentence explanation.

---

## Memo-ready claims

The memo can use these tallies directly to anchor specific claims:

- "V3 roughly doubled the table count (10 → 19) but cut V2's prediction/margin/buffer subsystem entirely."
- "Where we added back, we tied each addition to a brief-named problem; where we deferred, we documented a build trigger."
- "The biggest deletion ledger entry was the caterer-school capability matrix — replaced with three columns and a distance-radius query."
- "Five email types in V2-conception became eleven in V3, because the audit table and approval workflow earned their place at V3 scale."
- "Every cut item carries a documented V4 build trigger — deletion was active, not passive."
