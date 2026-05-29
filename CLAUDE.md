# CLAUDE.md — Padea Operations Agent

## Read this at every session start

1. **Check `chat_history/`** — read the most recent `YYYY-MM-DD_NNN.md` file there. That's where the last session's decisions and context live. Don't start working without it.
2. **Check `agent_context/`** — the system prompt, domain knowledge, runtime config, and tools reference for the Padea ops agent live there. You'll need them when building code.
3. **The venv is `.venv/`** — always use `source .venv/bin/activate` or `uv run` before running Python. Python version: 3.12.

---

## What this project is

An AI agent (Claude Sonnet 4.6) that runs the end-to-end catering workflow for Padea, a tutoring company at 6 Queensland schools. The agent sends real emails via Gmail, orders meals from caterers T-72hrs before each session, collects quality feedback, and surfaces escalations via an HTML decision log.

**This is a competition submission.** Judges see a live demo: real Supabase Postgres database, real Gmail emails. Quality of the demo matters.

**Design version: V4 is final.** Do not propose re-designing schema or architecture. Build it.

**V4 is the only live reference.** `docs/v4_optimised/` is authoritative for all design decisions. Everything in `docs/v1_initials/`, `docs/v2_cuts/`, `docs/v3_reinstatements/`, and `docs/archive/` is archived history — never pull a rule, constraint, or behaviour from those folders. If there is a conflict between an older doc and V4, V4 wins without question.

---

## Key file map

| File | What it is |
|---|---|
| `docs/v4_optimised/Schema/v4_schema.sql` | Authoritative DB schema — run this in Supabase, don't modify |
| `docs/v4_optimised/v4_summary.md` | Plain-English system description |
| `docs/v3_reinstatements/` | V3 base schema — historical record, do not build from |
| `agent_context/system_prompt.md` | System prompt the Padea agent gets at each run |
| `agent_context/tools_reference.md` | Tool catalog + build spec for `src/tools/` |
| `agent_context/runtime_config.yaml` | All configurable thresholds |
| `config/settings.py` | Pydantic settings loader — reads `.env` + runtime_config.yaml |
| `chat_history/` | Session summaries — read the latest one at session start |
| `.env` | Secrets — DATABASE_URL, ANTHROPIC_API_KEY (gitignored, see .env.example) |
| `.secrets/` | Gmail OAuth tokens (gitignored) |

---

## Non-negotiable rules (never violate these in code)

1. **Zero operational margin** — no tutor buffer, no contingency lines, no exclusion buffer. Walk-backs (absent students who show up) are an accepted gap — the session manager redistributes any surplus from other absences, or the student misses that session's meal.
2. **Commercial emails need approval** — `warning`, `rfp`, `cancellation`, `rfp_loser_courtesy` go to `queued_for_approval` status. Never call `gmail_send` for these directly.
3. **Dietary students always get a meal** — even if absent or year-level excluded. Only exception: whole-school exclusion where school is physically closed.
4. **Date parameters are always explicit** — never query enrolment as of "today" implicitly. Always pass the session date, report date, or incident date.
5. **Demo mode is default** — `email_mode: demo` in `runtime_config.yaml`. Never flip to production during development.

---

## Python conventions for this project

- **Package manager**: uv (`uv pip install`, `uv run`, `uv venv`)
- **Python version**: 3.12 (`.venv/` created with `uv venv --python 3.12`)
- **Imports**: use absolute imports from project root (`from src.tools.orders import create_order`)
- **Money**: always stored as integers (cents), never floats
- **Timestamps**: always `timestamptz` in DB, always timezone-aware `datetime` in Python
- **Enums**: use string literals matching the Postgres enum values — don't re-define Python enums unless the type system genuinely helps

---

## Working style preferences

- **Be direct** — short answers where possible, detailed only when the detail matters
- **Ask before assuming** on anything structural — if adding a new table or changing the schema feels needed, ask first
- **Session handoff — ask first** — at the end of a meaningful session (design decisions made, code built, schema changed), ask whether to write a `chat_history/YYYY-MM-DD_NNN.md` summary. Don't write it automatically. If the session was only a small bug fix with no design decisions, skip the question and optionally add one short line to `chat_history/sessions.log` instead.
- **Update build status** — when the user confirms a summary should be written, also update the Build status block in this file and set the `▶ Next session start here:` pointer.
- **Update this CLAUDE.md** whenever a new preference or convention is discovered that should persist — that's the point of this file

---

## Build status (updated each session)

**Last updated: 2026-05-29 (Session 025 — BLOCK B STOPs 1–3 LANDED. Real Gmail outbound live-verified (demo sends to sink, keeps real intended_to, single prefix, real gmail_message_id; commercial types can't auto-send). Inbound poll + Haiku classify wired (no live test yet). STOP 4 + two PRE-STOP-4 de-risks pending. Block B work UNCOMMITTED.)**

> **▶ Next session start here:** Read `chat_history/2026-05-29_025.md`. **Block A DONE; Block B STOPs 1–3 DONE (real outbound verified live; inbound poll+classify wired).** Next: the **two PRE-STOP-4 de-risks, then STOP 4 live inbound test** — (1) ONE synthetic `classify_inbound_email` call to verify `claude-haiku-4-5-20251001` against the live API (synthetic gmail_message_id; DELETE that `inbound_email_records` row after; report the label; fix the model string if it errors); (2) add `classify_inbound_email` to the **INBOUND section of `system_prompt.md` ONLY** (never the order-composition section). Then STOP 4: user emails FROM kyec898 TO padea.catering; trigger an inbound poll run; report inbox read, Haiku label, urgent step, dedup-on-second-poll. After Block B: **Block C — decision-log/dashboard HTML renderer** (static HTML + Python build script over `agent_steps`/`agent_runs`/`orders`/`outbound_emails`/`feedback`/`caterers`; timeline must-have, charts bonus) — HIGHEST VALUE remaining for the demo video. Then Block D — video + submission. **Locked: agent_model stays `claude-sonnet-4-6` (Haiku ONLY in `classify_inbound_email`); commercial emails always queue_for_approval; demo mode rewrites SENDING ONLY (inbound poll must NEVER be redirected to kyec898); caterer addresses stay `.example`.** **HARD pre-public-push blocker: `src/ingest/seed_*.py` embed real student PII inline — must be scrubbed before the repo is shared. `backups/` stays gitignored.** Pre-video cleanup (not now): delete orphan empty run_id=15; purge stale emails 5/6/9/11.

- ✅ V4 design locked (V3 base → optimisations applied → V4 final)
- ✅ `docs/v4_optimised/Schema/v4_schema.sql` — **authoritative schema**, deployed to Supabase (triggers, enums, denorm `caterer_id`, GST snapshot, enrolment_session_slots junction). Modify only with user approval.
- ✅ `docs/v4_optimised/optimisations.md` — OPT-01 through OPT-07 documented
- ✅ `docs/v4_optimised/v4_summary.md` — V4 plain-English description
- ✅ `docs/v3_reinstatements/` — V3 base schema preserved as historical record. Do not build from these.
- ✅ `agent_context/` folder fully populated
- ✅ `config/settings.py` + `requirements.txt` implemented, deps installed in `.venv`
- ✅ Chat history system + Stop hook
- ✅ Supabase project created (`padea-ops-agent`, `ap-southeast-1`, IPv4 via Session pooler)
- ✅ V4 schema deployed and verified — smoke test passes, PostgreSQL 17.6
- ✅ `enrolment_session_slots` table + indexes deployed (V4-OPT-07)
- ✅ `.env` configured with `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY` (gitignored)
- ✅ `scripts/test_db_connection.py` — smoke test passes end-to-end
- ✅ `requirements.txt` updated: `psycopg[binary]>=3.1.0` (psycopg v3)
- ✅ `data/source/` — all 7 source files (REAL Padea data)
- ✅ `data/data_inventory.md` — Phase 2 ingest planning + 10 locked decisions + dummy data section
- ✅ `src/ingest/` — 14 seed scripts + run_all.py (10 core + 4 dummy demo scripts)
- ✅ DB core data seeded: 11 dietary_tags, 6 schools, 4 caterers, 7 tutors, 40 menu_items, 205 dietary tag links, 11 session_slots, 11 session_tutor_assignments, 320 enrolments, 61 enrolment_dietary_tags, 10 absences, 4 exclusions, 320 enrolment_session_slots
- ✅ DB dummy demo data seeded: term_meal_preferences, term_meal_preference_items, canonical_menu_order on caterers, 55 historical orders (5 weeks), 55 manager feedback rows (Terrific on declining trend), 9 upcoming exclusions (ISHS camp + school holidays), ~11 upcoming absences. order_lines = 0 rows (conscious scope cut — manager ratings alone exercise the decline→warning→RFP arc; see memo_material.md)
- ✅ `src/tools/enrolments.py` — `get_enrolments_for_session` (now returns `other_allergy_notes`), `get_enrolment_dietary_tags` ✓
- ✅ `src/tools/meals.py` — `item_is_safe_for_enrolment`, `auto_pick_dietary_meal`, `get_meal_request`, `consume_meal_request`, `get_next_rotation_meal` (bug fix: ol.created_at → MAX(o.session_date) via JOIN) ✓
- ✅ `src/tools/orders.py` — `compose_session_order` (safety hole closed: item_is_safe_for_enrolment on ALL three paths; safety_records in return dict), `create_order` ✓
- ✅ `src/tools/infrastructure.py` — `create_agent_run`, `complete_agent_run`, `log_agent_step`, `check_and_resolve_crashed_runs` ✓
- ✅ `src/tools/sessions.py` — `get_sessions_needing_orders`, `get_session_slot` ✓
- ✅ `src/tools/absences.py` — `get_absence`, `upsert_absence` (DO NOTHING), `get_exclusions`, `get_year_level_exclusions` ✓
- ✅ `src/tools/quality.py` — `get_feedback_for_session` (+ full manager checklist), `compute_rolling_mean` (as_of pinnable, NULL ratings excluded), `get_feedback_since` ✓
- ✅ `src/tools/caterers.py` — `caterers_within_range` (hardcoded QLD postcode dict + geopy geodesic), `project_weekly_cost` (int cents, GST-normalised, delivery × sessions, moq_5 assumed), `check_weekly_moq` (shortfall returned as data, GST-normalised) ✓
- ✅ `src/tools/orders.py` additions — `compose_order_email` (cost-free per V4 ruling; per-student meal brief with dietary safety: meal_tags ⊇ student_tags containment check, ⚠ UNSAFE MATCH flag, ⚠ ALLERGY NOTE (unverified) for free-text; deliver_by = dinner_time − 10 min; location deduped building==room) ✓
- ✅ `scripts/test_compose_session_order.py` — proves safe=False caught on request-source violation; urgent agent_steps row verified in DB ✓
- ✅ `src/agent/loop.py` — TOOL_SCHEMAS (21), TOOL_REGISTRY (20), _PARAM_TYPES (12), _serialise(), dispatch(); run() STEP 3a done (skeleton) ✓
- ✅ `src/agent/loop.py` run() STEP 3b — hard-cap logic approved (urgency "none"→"informational" fix; json.dumps defensive wrap; 16 tests pass)
- ✅ `src/agent/__init__.py` — empty package marker
- ✅ `scripts/test_dispatch.py` — 32 dispatch unit tests pass (mocked, no DB)
- ✅ `scripts/test_loop_cap.py` — 16 tests pass (13 cap + 3 shortfall urgency)
- ✅ `src/agent/loop.py` run() STEP 3c — safety_records unconditional logging (231/231 tests pass: 19 unit + 212 integration; integration check caught real/mock field mismatch — `reason` field absent in real data)
- ✅ `scripts/test_safety_records.py` — 231 tests pass (Part 1 mocked, Part 2 real DB shape check)
- ✅ STEP 4 first live run (run_id=5, 2026-05-29) — CAP HIT at 15/15; loop infra worked perfectly (cap tripped clean, urgent logged, zero mutations, honest report); root cause: prompt, not code
- ✅ `agent_context/system_prompt.md` — pipeline fixed: 8 steps → 5 (compose_session_order direct; 6 forbidden internals listed; one-session-per-run; quality 24h skip-out)
- ✅ `agent_context/runtime_config.yaml` — `max_tool_calls_per_run: 20` (was 15; worst-case single-session ≈ 13 calls, 7 headroom)
- ✅ STEP 4 RE-RUN — order 132 (slot 3, JPC Wed, Terrific, 33 lines, $676.50, run_id=6, 9 calls) + order 133 (slot 11, CHAC Wed, GYG, 38 lines, $570.00, run_id=7, 8 calls). Both clean. 2 urgent no_safe_meal escalations in slot 3 (Aanya Desai enr 63, Edward Cook enr 77 — vegetarian, Terrific has no inherently-VG items) → root cause of Option C
- ✅ Option C design approved: VO = safety fallback only (never a menu item, never a preference). Schema: `ALTER TABLE order_lines ADD COLUMN variant text` + `ALTER TABLE menu_items ADD COLUMN has_vegetarian_option bool` + UPDATE 15 VO items (ids 6,10,13,15,16,17,23,24,25,27,31,32,35,36,37). Source stays 'dietary_auto_pick'. safe=True computed as item_tags ⊇ (student_tags−{vegetarian}). Full spec in chat_history/2026-05-29_019.md
- ✅ Option C STEP 1 — pg_dump backup (`backups/pre_option_c_2026-05-29.sql`, 478K); 3 ALTERs applied: `order_lines.variant text`, `menu_items.has_vegetarian_option bool NOT NULL DEFAULT false`, 15 VO items flagged (verified against PDF, 0 wrong/missed). Halal derivation confirmed correct.
- ✅ Option C STEP 2 — `compose_session_order` VO fallback: `_auto_pick_vo_meal` + `_vo_safe_for_enrolment` in `src/tools/orders.py`; variant in order_lines + safety_records dicts; create_order INSERT writes variant; 7 smoke assertions pass
- ✅ Option C STEP 3 — `compose_order_email`: `ol.variant` in SELECT; `_format_order_line` renders ⚑ VEGETARIAN OPTION; UNSAFE MATCH suppressed only for vegetarian label gap on VO lines
- ✅ Option C STEP 4 — `loop.py` STEP 3c: `vo_variant_requested` informational step at loop.py:1021–1041, unconditional, loop-owned
- ✅ Option C STEP 5 — `scripts/test_options_c.py` T1–T6 (26/26 pass); `data/data_inventory.md` Grilled Pork Vermicelli VO-cell marked VO
- ✅ Option C STEP 6 — live JPC Tue run_id=9 (2026-05-29): order 136 (slot 2, 2026-06-02, 28 lines); Pooja (enr 36) item 13 VO, Rashid (enr 23) item 15 VO (halal, NOT pork); 2 vo_variant_requested steps; all 28 safe=True; 0 escalations; 9/20 calls
- ✅ Block A Chunk 1 — `src/tools/weekly_summary.py`: `generate_weekly_summary` (ISO week, already_completed guard, GST normalisation, MOQ absolute SET, quality rolling means, sustained_decline) + `compose_weekly_summary_email` (cost/GST block, MOQ note, quality block, decline alert, demo prefix); 4/4 integration tests pass
- ✅ Block A Chunk 2 STEP 0a — delivery folded into `grand_total_cents`: `total_delivery_cents = delivery_fee_cents × sessions_count`; `ex_subtotal = meals + delivery`; ONE round at GST boundary → Terrific week 2026-06-01: grand_total 144155, gst 13105 (was 137555/12505). Delivery now a line inside the email total block. `total_delivery_cents` added to return dict. 4/4 tests updated + pass
- ✅ Block A Chunk 2 STEP 0b — MOQ shortfall priced at `min(mi.price_cents)` not `avg` (operator-favourable floor top-up); same GST normalisation. NOT exercised by tests (variety=7, no MOQ tier) — flag G
- ✅ Block A Chunk 2 STEP 1 — `src/tools/gmail.py` stubs: `gmail_send` (→ outbound_emails status='sent', sent_at=now(), gmail_message_id NULL; enum routine types session_order/weekly_consolidated_summary) + `queue_email_for_approval` (→ status='queued_for_approval'; commercial types warning/rfp/cancellation/rfp_loser_courtesy; never sends). Demo mode keeps intended_to_address real, prefixes body `[DEMO — Intended for: {to}]`. No real Gmail call (creds not obtained)
- ✅ Block A Chunk 2 STEP 2 — 4 tools wired into `loop.py`: TOOL_SCHEMAS 21→25, TOOL_REGISTRY 20→24, _PARAM_TYPES 12→14 (generate_weekly_summary week_of→date, as_of→datetime). gmail_send/queue_email_for_approval enum-restricted in schemas. Dispatch tests 32/32. Flag E fixed: `tools_reference.md` week_ending_date→week_of
- ✅ Block A Chunk 2 STEP 3 — `agent_context/system_prompt.md` new "Monday consolidated summary" section (6 steps: generate→MOQ note→compose+send→decline check→decline response→terminal note; idempotency gate; decline iff mean_4w<3.0 AND mean_12w−mean_4w>=0.5 as literals; swap analysis ANALYSIS-ONLY capped 2 schools × 2 alts; urgency tiers). Order-composition section + `_load_system_prompt()` UNTOUCHED
- ✅ Block A Chunk 2 STEP 4 — Scenario-4 precheck: `caterers_within_range(school_id=2, exclude_caterer_id=2)` returned 3 in-range caterers (Lakehouse 14.3 km, Kenko 19.3 km, +1) → Scenario 4 viable, kill-switch NOT needed
- ✅ Block A Chunk 2 STEP 5 — re-ran Scenario 1 (GYG slot 11) & Scenario 2 (Terrific slot 2) on fresh dates via `scripts/step5_live_run.py`; `gmail_send` wrote real `outbound_emails` rows (emails 5 & 6, status=sent, type=session_order, real intended_to_address, `[DEMO — Intended for: …]` body prefix); ⚑ VEGETARIAN OPTION rendered for VO students. (Query gotcha: order-workflow gmail_send sets `related_order_id`, NOT `related_run_id` — motivated the run_id fix below)
- ✅ run_id injection fix (commit `c6fa3a4`) — model cannot see its own run_id at tool-call time, so loop `dispatch` now injects `coerced["related_run_id"] = run_id` for `gmail_send`/`queue_email_for_approval`; removed `related_run_id` from both schemas' props and from `queue_email_for_approval` required list (now `["email_type","to","subject","body"]`). Loop-owned, not model discretion
- ✅ date round-trip fix (commit `c8c8239`) — `_serialise` stringifies dict date fields to the model; model round-trips them back as ISO strings; `compose_weekly_summary_email` crashed on `.weekday()`. Added `_as_date()`/`_fmt_date()` coercion at the tool boundary in `weekly_summary.py`; `week_start`/`week_end` coerced. 4/4 tests pass
- ✅ Block A Chunk 2 STEP 6 — **live Monday run LANDED clean** (run_id=13; first attempt run_id=12 hit the date bug above → fixed in code → re-ran ONCE). REAL means computed from live feedback: 4w=2.0, 12w=3.2, drop=1.2 → sustained decline (2.0<3.0 AND 1.2≥0.5, both literals met). Wrote email 9 (`weekly_consolidated_summary`, status=sent, TOTAL DUE $1,441.55) + email 10 (`warning`, status=queued_for_approval, related_run_id=13 populated). Swap analysis logged notable (Kenko $713/wk, Lakehouse $4,851/wk vs incumbent $1,441.55) — ANALYSIS ONLY, schools.current_caterer_id unchanged (mutation guard clean). 13/20 calls. All 10 review criteria pass (one cosmetic exception, criterion 7). **THE REVIEW GATE IS CLEARED — Block A landed.**
- ✅ Block B STOP 1 — Auth scaffolding: `src/tools/gmail_client.py` (thin client, SCOPES=[gmail.send, gmail.modify], `load_credentials`/`get_service`/`send_message`/`list_messages`/`get_message`/`mark_read`, userId="me") + `scripts/gmail_auth.py` (one-off consent → `config/gmail_token.json`, token minted) + `settings.gmail_address`; token/creds paths → `config/...`
- ✅ Block B STOP 2 — Real outbound (live-verified, run_id=16): `src/tools/gmail.py` rewritten. Demo mode REALLY sends to demo sink (kyec898) while keeping `intended_to_address`=real recipient + idempotent `[DEMO — Intended for: {real}]` prefix (double-prefix bug fixed via `_DEMO_PREFIX_MARKER`). Commercial types (`warning/rfp/cancellation/rfp_loser_courtesy`) raise in `gmail_send` — can't auto-send. Send failure → `status='failed'` row + failure_reason + raise (never swallowed). Success → `status='sent'` + real `gmail_message_id`. Gmail API read-back confirmed To=kyec898/From=padea.catering/[SENT]/single prefix. All 4 caterers' `contact_email` → non-routable `.example` (4-row UPDATE, did NOT touch PII seed scripts)
- ✅ Block B STOP 3 — Inbound poll + Haiku classify (wiring only, no live test): `src/tools/inbound.py` imports ONLY `gmail_client` (poll isolated from demo SEND rewrite). `gmail_poll_inbox` reads `in:inbox is:unread` from REAL inbox, dedups via `inbound_email_records`. `classify_inbound_email` uses `settings.classifier_model` (Haiku — ONLY Haiku use), unclassified fallback, ON CONFLICT DO NOTHING. `loop.py`: 27 schemas / 26 registry / 15 _PARAM_TYPES; model call still Sonnet. `classifier_model: claude-haiku-4-5-20251001` in settings + yaml
- ⏳ Block B PRE-STOP-4 de-risks — (1) NOT DONE: ONE synthetic `classify_inbound_email` call to verify `claude-haiku-4-5-20251001` live (synthetic id, DELETE the row after, report label); (2) NOT DONE: add `classify_inbound_email` to INBOUND prompt section ONLY
- ❌ Block B STOP 4 — live Scenario 5 inbound test NOT DONE; **Block B changes UNCOMMITTED** (M gmail.py/loop.py/settings.py/runtime_config.yaml; ?? gmail_client.py/inbound.py/gmail_auth.py)
- 📌 Swap-check (Session 025, closed): run_id=13 Kenko ~$713/wk vs Lakehouse ~$4,851/wk spread is a REAL per-meal price diff (~$5.50 vs ~$38.50 GST-incl), not a `project_weekly_cost` artifact. Caveat: alternatives projected at 126 meals (63×2) vs incumbent actual 61-meal $1,441.55 — needs one-line memo/voiceover caveat
