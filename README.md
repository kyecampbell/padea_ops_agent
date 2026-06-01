# Padea Operations Agent

An AI agent (Claude Sonnet 4.6) that runs the end-to-end catering workflow for
Padea, a tutoring company operating at six Queensland schools. The agent orders
meals from caterers ahead of each tutoring session, sends real emails via Gmail,
collects quality feedback, and surfaces escalations through a human-readable
decision log.

It is built against a live Supabase Postgres database and a real Gmail account.
A self-contained HTML decision log (`renderer/index.html`) renders every agent
run — its reasoning, tool calls, emails, charts, and escalations — for review.

---

## What the agent does

- **Orders meals** T-72h before each session, composing a per-student order that
  respects dietary tags, allergies, year-level exclusions, and absences.
- **Sends caterer order emails** via Gmail (demo mode redirects sending to a sink
  inbox while preserving the real intended recipient).
- **Runs a Monday consolidated summary** per caterer — costs, MOQ, GST, and a
  rolling quality check that can trigger a warning when satisfaction declines.
- **Polls inbound mail**, classifies it (Claude Haiku), and escalates issues.
- **Escalates to a human** for anything commercial: warnings, RFPs, and
  cancellations are queued for operator approval, never auto-sent.

The full system description lives in `docs/v4_optimised/v4_summary.md`.

---

## Repository layout

```
padea_ops_agent/
├── CLAUDE.md                     — Project guide + running build status (start here)
├── README.md                     — This file
├── requirements.txt              — Python dependencies (installed via uv)
├── .env.example                  — Template for secrets (copy to .env)
│
├── agent_context/                — Everything the agent reads at runtime
│   ├── system_prompt.md          — System prompt injected each run
│   ├── domain_knowledge.md       — Business rules + controlled vocabularies
│   ├── runtime_config.yaml       — Tunable thresholds (the only tuning surface)
│   └── tools_reference.md        — Tool catalog / build spec for src/tools/
│
├── config/
│   └── settings.py               — Pydantic settings (reads .env + runtime_config.yaml)
│
├── src/
│   ├── agent/loop.py             — Core reasoning / tool-call loop
│   ├── tools/                    — Reusable primitives the agent calls
│   │   ├── orders.py meals.py enrolments.py absences.py caterers.py
│   │   ├── sessions.py quality.py weekly_summary.py infrastructure.py
│   │   └── gmail.py gmail_client.py inbound.py
│   └── ingest/                   — Seed scripts that load the source data into Postgres
│
├── scripts/                      — Tests, live-run drivers, and build_renderer.py
├── renderer/index.html           — Self-contained offline decision log (the deliverable)
│
├── docs/
│   └── v4_optimised/             — AUTHORITATIVE design (schema, summary, optimisations)
│       └── Schema/v4_schema.sql  — The deployed DB schema
│
├── data/source/                  — Competition-supplied source dataset (synthetic)
└── chat_history/                 — Per-session handoff notes (sessions.log = heartbeat)
```

> Older design folders (`docs/v1_initials/`, `docs/v2_cuts/`,
> `docs/v3_reinstatements/`, `docs/archive/`) are historical record only. **V4 is
> final** — `docs/v4_optimised/` wins on any conflict.

---

## Getting started

Prerequisites: Python 3.12 and [uv](https://github.com/astral-sh/uv).

```bash
uv venv --python 3.12               # create .venv/
source .venv/bin/activate
uv pip install -r requirements.txt  # install dependencies

cp .env.example .env                # then fill in DATABASE_URL, ANTHROPIC_API_KEY, etc.

python scripts/test_db_connection.py   # smoke-test the Supabase connection
```

Run the test suite (offline, mocked) and rebuild the decision log:

```bash
python scripts/test_dispatch.py        # dispatch + tool unit tests
python scripts/build_renderer.py       # regenerate renderer/index.html (READ-ONLY)
```

---

## Conventions

- **Package manager:** uv. **Python:** 3.12.
- **Money:** always integer cents, never floats.
- **Timestamps:** `timestamptz` in the DB, timezone-aware `datetime` in Python.
- **Demo mode is default** (`email_mode: demo` in `runtime_config.yaml`) — sending
  is redirected to a sink inbox; never flipped to production during development.
- **Commercial emails** (warning / RFP / cancellation) are queued for human
  approval, never auto-sent.

See `CLAUDE.md` for the full set of project rules and the current build status.
```
