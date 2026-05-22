# Padea Operations Agent

An AI-powered operations agent for Padea, built to automate and streamline
catering operations workflows.

---

## Architecture Overview

The project is divided into four conceptual layers. Each layer has a single,
clear responsibility — nothing crosses boundaries without going through a
defined interface.

### `src/workflows/` — Business Processes
Workflows are named, end-to-end business processes that Padea actually runs:
"handle an incoming catering enquiry", "reconcile a month-end invoice", etc.
A workflow knows *what needs to happen* and in what order. It coordinates calls
to tools and hands context to the agent loop — but it contains no raw SQL,
no direct API calls, and no prompt text.

### `src/agent/` — Reasoning & Orchestration
The agent layer is the brain. It receives a task and a set of tools, then
reasons about what to do next — calling tools, interpreting results, and
deciding when to stop or escalate. Key files:

| File | Purpose |
|---|---|
| `loop.py` | Core tool-call / response loop (model-agnostic in its control flow) |
| `escalation.py` | Conditions and routing for handing off to a human |
| `prompts/` | System prompts and instruction fragments, versioned separately from code |

The agent does not know what any specific workflow is doing. It knows only:
"I have been given a task and these tools — figure it out."

### `src/tools/` — Reusable Primitives
Tools are atomic, self-contained functions the agent can call: look up an order,
send a draft email, query a price list, validate an address. Each tool should be:
- **Stateless** where possible (no hidden side-effects)
- **Reusable** — designed for this agent but not coupled to it, so future agents
  or scripts can import the same tool
- **Independently testable** in `tests/unit/`

### `config/` — Rules & Thresholds
Anything that is a *policy decision* rather than *logic* lives here: escalation
thresholds, retry limits, feature flags, confidence cut-offs. Keeping these in
one place means a non-engineer can review and adjust operational parameters
without reading business logic.

Values that are *secrets or environment-specific* (API keys, DB URLs) belong
in `.env` — see `.env.example`.

### `logs/` — Audit Trail & Decision History
Every agent run writes a structured log to `logs/runs/`. Logs capture the full
decision trace: what the agent was given, which tools it called, what it decided,
and whether it escalated. Human-readable HTML renderings go to `logs/html/`.
Logs are the primary tool for debugging unexpected behaviour and for building
trust with stakeholders.

---

## Project Layout

```
padea_ops_agent/
├── README.md                   — This file
├── PROJECT_CONTEXT.md          — Business context, goals, and background
├── DECISIONS.md                — Architectural and design decisions log
├── requirements.txt            — Python dependencies
├── .env.example                — Template for environment variables (copy to .env)
├── .gitignore
│
├── config/
│   └── settings.py             — Rules, thresholds, and tunable parameters
│
├── schema/
│   └── schema.sql              — Database schema (not yet defined)
│
├── docs/
│   ├── schema_notes.md         — Notes on data model choices
│   ├── memo_notes.md           — Notes from memos and internal documents
│   └── process_diagram_notes.md — Notes from process/workflow diagrams
│
├── data/
│   ├── raw/                    — Untouched source data (PDFs, exports, etc.)
│   └── processed/              — Cleaned / transformed data
│
├── src/
│   ├── importers/              — Scripts that ingest raw data into the DB
│   ├── tools/                  — Reusable primitives the agent (and others) can call
│   ├── workflows/              — Named business processes that orchestrate tools
│   └── agent/
│       ├── loop.py             — Core reasoning / tool-call loop
│       ├── escalation.py       — Human hand-off logic and routing
│       └── prompts/            — System prompts and instruction fragments
│
├── emails/
│   ├── incoming/               — Inbound email samples / fixtures
│   └── outgoing/               — Outbound email drafts / templates
│
├── logs/
│   ├── runs/                   — Structured JSON logs, one file per agent run
│   └── html/                   — Human-readable HTML renderings of run logs
│
└── tests/
    ├── unit/                   — Fast, offline tests for tools and helpers
    └── adversarial/            — Edge-case scenarios to stress-test agent behaviour
```

---

## Getting Started

> Setup instructions will be added once the stack is decided.
>
> Quick-start checklist (draft):
> 1. `python -m venv .venv && source .venv/bin/activate`
> 2. `pip install -r requirements.txt`
> 3. `cp .env.example .env` — fill in API keys and DB URL
> 4. `pytest tests/unit/` — confirm tools work offline
