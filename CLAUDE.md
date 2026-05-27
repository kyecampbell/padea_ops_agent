# CLAUDE.md — Padea Operations Agent

## Read this at every session start

1. **Check `chat_history/`** — read the most recent `YYYY-MM-DD_NNN.md` file there. That's where the last session's decisions and context live. Don't start working without it.
2. **Check `agent_context/`** — the system prompt, domain knowledge, runtime config, and tools reference for the Padea ops agent live there. You'll need them when building code.
3. **The venv is `.venv/`** — always use `source .venv/bin/activate` or `uv run` before running Python. Python version: 3.12.

---

## What this project is

An AI agent (Claude Sonnet 4.6) that runs the end-to-end catering workflow for Padea, a tutoring company at 6 Queensland schools. The agent sends real emails via Gmail, orders meals from caterers T-72hrs before each session, collects quality feedback, and surfaces escalations via an HTML decision log.

**This is a competition submission.** Judges see a live demo: real Supabase Postgres database, real Gmail emails. Quality of the demo matters.

**Design version: V3 is final.** Do not propose re-designing schema or architecture. Build it.

---

## Key file map

| File | What it is |
|---|---|
| `docs/v3_final/Schema/v3_schema.sql` | Authoritative DB schema — run this in Supabase, don't modify |
| `docs/v3_final/v3_summary.md` | Plain-English system description |
| `agent_context/system_prompt.md` | System prompt the Padea agent gets at each run |
| `agent_context/tools_reference.md` | Tool catalog + build spec for `src/tools/` |
| `agent_context/runtime_config.yaml` | All configurable thresholds |
| `config/settings.py` | Pydantic settings loader — reads `.env` + runtime_config.yaml |
| `chat_history/` | Session summaries — read the latest one at session start |
| `.env` | Secrets — DATABASE_URL, ANTHROPIC_API_KEY (gitignored, see .env.example) |
| `.secrets/` | Gmail OAuth tokens (gitignored) |

---

## Non-negotiable rules (never violate these in code)

1. **Zero operational margin** — no tutor buffer, no contingency lines. Only the 10% exclusion buffer for year-level exclusions.
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
- **Write the session summary** at the end of each conversation to `chat_history/YYYY-MM-DD_NNN.md` — cover: what was decided, what was built, key decisions with brief reasoning, where to pick up next session
- **Update this CLAUDE.md** whenever a new preference or convention is discovered that should persist — that's the point of this file

---

## Build status (updated each session)

**Last updated: 2026-05-27 (Session 002)**

> **▶ Next session start here:** Write ingest scripts to seed real Padea data — populate `schools`, `caterers`, `students`, and `upcoming_sessions` from source files in `data/source/` (`.xlsx` + `.pdf`). That's Phase 2.

- ✅ V3 design locked, V4/V5 cancelled
- ✅ `agent_context/` folder fully populated
- ✅ `config/settings.py` + `requirements.txt` implemented, deps installed in `.venv`
- ✅ Chat history system + Stop hook
- ✅ Supabase project created (`padea-ops-agent`, `ap-southeast-1`, IPv4 via Session pooler)
- ✅ V3 schema deployed and verified — `schools` table queryable, returns 0 rows as expected
- ✅ `.env` configured with `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY` (gitignored)
- ✅ `scripts/test_db_connection.py` — smoke test passes end-to-end (PostgreSQL 17.6)
- ✅ `requirements.txt` updated: `psycopg[binary]>=3.1.0` (psycopg v3, replaces psycopg2)
- ❌ Source data not ingested (`data/source/*.xlsx`, `*.pdf`) ← **Phase 2**
- ❌ `src/tools/` — all stubs
- ❌ `src/agent/loop.py` — stub
- ❌ Gmail API credentials not obtained
