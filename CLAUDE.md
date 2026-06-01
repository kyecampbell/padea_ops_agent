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
| `config/gmail_token.json`, `config/gmail_credentials.json` | Gmail OAuth token + creds (gitignored) |

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

**Last updated: 2026-06-01 — Blocks A, B, and C are all COMPLETE and committed. The demo database was reset to the clean seed baseline today via `scripts/reset_demo.py` (54 seed orders + 378 feedback rows preserved; all agent-generated runs/steps/emails and agent-composed orders cleared — `agent_runs` now 0). The renderer is in LIVE mode and currently blank; it repopulates automatically as new live runs happen. Only Block D (deliverables + submission) remains.**

> **▶ Next session start here:** Read the latest `chat_history/` handoff for full context. **Next steps:** (1) rebuild the demo timeline with a fresh sequence of live runs — the previously curated demo runs were cleared by the reset and are NOT recoverable, so the on-camera decision log starts fresh; (2) do a full demo dry-run (every scene end-to-end, no recording); (3) finish **Block D** — video ≤5 min + one-page two-column memo PDF + simplified process diagram + Supabase link tested in incognito + public GitHub repo + AI-usage transcripts → submit to dylan@padea.com.au. Block D in progress: `docs/v4_optimised/FINALDIAGRAM.png` and `docs/v4_optimised/video_script.md` are drafted (untracked).

### What's built (all committed)

- ✅ **V4 design + schema** — `docs/v4_optimised/` is authoritative (`Schema/v4_schema.sql`, `v4_summary.md`, `optimisations.md` covering OPT-01–07). Schema deployed to Supabase (PostgreSQL 17.6) and verified end-to-end. Modify only with approval. `docs/v3_reinstatements/` kept as historical record — do not build from it.
- ✅ **Project scaffolding** — `config/settings.py` (Pydantic, reads `.env` + `runtime_config.yaml`) + `requirements.txt` (`psycopg[binary]` v3), deps installed in `.venv` (Python 3.12). Chat-history system + Stop hook (`.claude/hooks/save_transcript.py` archives each session's full transcript to `chat_history/transcripts/` and indexes it in `sessions.log`). `scripts/test_db_connection.py` smoke test passes.
- ✅ **Data seeded** (`src/ingest/`, reproducible via `run_all.py`) — core: 6 schools, 4 caterers, 7 tutors, 40 menu items, 320 enrolments + dietary tags/links, 11 session slots + tutor assignments, absences, exclusions, `enrolment_session_slots`. Demo substrate: 54 historical orders across 5 weeks, manager + tutor feedback on a declining Terrific trend (`SLOT_RATING_OVERRIDE` keeps MacGregor healthy while JPC collapses, so per-school monitoring visibly matters), term meal preferences, upcoming exclusions/absences. Source data is the competition-supplied **synthetic** dataset — safe to publish, no PII scrub needed.
- ✅ **Tools layer** (`src/tools/`) — `enrolments`, `meals`, `orders` (`compose_session_order` with dietary-safety checks on all paths + `compose_order_email`), `sessions`, `absences`, `quality` (`compute_rolling_mean`, as-of-pinnable, NULL ratings excluded), `caterers` (range via QLD-postcode + geopy, `project_weekly_cost`, `check_weekly_moq`), `infrastructure` (run/step logging + crash recovery), `weekly_summary`, `gmail` (real outbound + queue-for-approval), `gmail_client` (thin Gmail API client), `inbound` (poll + Haiku classify). Money in integer cents, GST normalised at the boundary.
- ✅ **Agent loop** (`src/agent/loop.py`) — tool schemas/registry, dispatch with type coercion + loop-injected `run_id`, hard per-run call cap, unconditional safety-record logging. Backed by `scripts/test_dispatch.py`, `test_loop_cap.py`, `test_safety_records.py`, `test_options_c.py`. Model: `claude-sonnet-4-6` (Haiku used ONLY in `classify_inbound_email`). System prompt + tunable thresholds live in `agent_context/`.
- ✅ **Option C — vegetarian-option safety fallback** — VO is a safety fallback only (never a menu choice or stored preference). `order_lines.variant` + `menu_items.has_vegetarian_option` (15 VO items flagged); `safe=True` computed as item_tags ⊇ (student_tags − {vegetarian}); order email renders ⚑ VEGETARIAN OPTION; loop logs a `vo_variant_requested` informational step.
- ✅ **Block A — Monday consolidated summary** — `generate_weekly_summary` (ISO week, idempotency guard, GST-normalised cost incl. delivery × sessions, MOQ shortfall priced at the floor) + a payment-only caterer summary email; sustained-decline detection → queued warning email. Decline rule: `mean_4w < 3.0 AND (mean_12w − mean_4w) ≥ 0.5`. Caterer-swap analysis is ANALYSIS-ONLY (capped, never mutates `schools.current_caterer_id`).
- ✅ **Block B — real Gmail** — `gmail_client.py` (scopes gmail.send + gmail.modify) + one-off `scripts/gmail_auth.py` consent flow. Live outbound: demo mode really sends to the demo sink while preserving the real intended recipient + a single `[DEMO — Intended for: …]` prefix; commercial emails always queue for approval and never auto-send; send failure → `status='failed'` row + raise. Inbound poll reads the real inbox (isolated from the demo send-rewrite), dedups via `inbound_email_records`, Haiku-classifies, Sonnet escalates. All 4 caterers' `contact_email` set to non-routable `.example`.
- ✅ **Block C — operator decision-log renderer** (`scripts/build_renderer.py` → `renderer/index.html`; single self-contained offline file, READ-ONLY SELECTs only, no framework/CDN/server, one-command rebuild). PADEA masthead; current-state panel (escalations needing attention / recent runs / upcoming sessions, next 7 days); all-schools at-a-glance; per-school satisfaction charts (student-rating decimals, 3.0 floor reference line, low-n note, hand-rolled inline SVG); per-caterer cost chart (one bar reconciles to one invoice, summary-basis pricing); humanised timeline with runs labelled by real Brisbane date/time, inline email cards (✓ SENT / ⏸ QUEUED badges) + browser-only "Approve & Send" (pure DOM, no DB write). `DEMO_RUN_IDS = []` → live mode (auto-discovers all runs oldest-first); set explicit ids only to pin a curated narrative order.

### Invariants — keep these true

(These complement the Non-negotiable rules above — build-specifics, not a repeat of them.)

- Renderer is **READ-ONLY** (SELECT only; no agent calls, no writes).
- `agent_model` stays `claude-sonnet-4-6`; Haiku only in `classify_inbound_email`.
- Demo mode rewrites SENDING only; the inbound poll must NEVER be redirected to the demo sink.
- Caterer `contact_email` addresses stay non-routable `.example`.
- GST normalised once at the boundary (money is integer cents — see Python conventions).

> Detailed per-session build history (run IDs, step-by-step decisions, superseded states) lives in `chat_history/`. This block is the current-state summary, not the changelog.
