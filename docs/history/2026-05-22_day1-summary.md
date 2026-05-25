# Day 1 Summary — PADEA Operations Agent

**Date:** Friday 22 May 2026
**Project:** Padea Operations Engineer Competition Entry
**Submission deadline:** Friday 29 May 2026, 11:59pm
**Days remaining after today:** 7

---

## What we did today, in one paragraph

Today was deliberately a thinking day, not a building day. We resisted the pull to start writing code and instead spent the bulk of our time on Steps 1–4 of the Musk framework (requirements, deletion, simplification, cycle time) before touching Step 5 (automation). The output is: a locked-in goal and priority stack, a defended architecture, a refined understanding of the dataset's hidden requirements, a clear list of what we will and won't build, an 8-day roadmap, and a clean scaffolded repository pushed to private GitHub with all the joinery in place for the actual build to start tomorrow.

The competition rewards Steps 1–4 at least as heavily as Step 5. Today was the investment that buys the rest of the week's execution. Every decision we made is documented so future agents — and the judges — can follow the reasoning.

---

## Why we worked the way we did

Three forces shaped today's approach.

**The judging criteria.** Two of three criteria — Learning and Taste — are judged on the memo and the quality of decisions, not on shipping features. Functionality leads with "how not dumb are your requirements" before asking about execution. So time spent thinking out loud is the deliverable, not a detour. We made our reasoning visible in the chat because the chat may be referenced in submission.

**The hint in the task sheet.** *"What is the goal of this system? Hint: it is not just that meals are ordered and delivered each week."* Combined with explicit statements about food quality declining and students complaining about meal preferences, the hint reframes the problem: catering exists to support student satisfaction → re-enrolment → revenue. We let that reframe drive every priority decision.

**The role being hired.** Dylan is hiring an Operations Engineer who fixes bottlenecks with AI agents. The competition is a proxy for the job. The right build is one that demonstrates how a real operations engineer would think, not one that demonstrates the most impressive feature list. Restraint and architectural foresight are part of what's being tested.

---

## The goal we committed to

The system is **a continuous improvement loop for student catering satisfaction**, designed as an **agentic catering operator module** built to plug into Padea's larger future agentic stack. Ordering, delivery, and feedback are the steps of the loop, not the goal of the system.

Important refinement made mid-conversation: the system must work even if feedback is patchy. Learning is a bonus, not the spine. The spine is correct, safe, on-time meal delivery with the coordinator out of the bottleneck.

### The six priorities, in order

1. **Safety and correctness** — every non-opted-out student gets a meal that doesn't violate dietary restrictions, at the right place and time. Non-negotiable floor.
2. **Coordinator out of the bottleneck** — system proposes, coordinator approves big calls.
3. **Feedback loop closes** — per-student preferences and per-caterer ratings accumulate over time.
4. **Rotation has teeth** — when a caterer's rolling rating drops, alternatives surface from the "able to serve" list; coordinator decides.
5. **Build is legible** — every decision has an auditable reasoning trail (this is also infrastructure for future agents, not just for judges).
6. **Fails gracefully** — escalates rather than guessing when uncertain.

Cost optimisation is a constraint, not a goal. We optimise satisfaction subject to reasonable cost.

---

## Key architectural decisions

### Run cadence: hybrid (not batch)
The agent has a single entry point that decides what to do based on date and pending events. Five trigger types: weekly ordering (scheduled Thursday), absence intake (reactive), pre-delivery reminders (scheduled day-of), post-session feedback (reactive), coordinator ad-hoc (manual). Same reasoning loop, different triggers. Aligns with Dylan's tutor-absence agent example.

**Why:** Pure weekly batch is what the coordinator currently does badly; building an agent that only mirrors that doesn't earn the role. Hybrid stress-tests modularity — if you can't write a single entry point that handles multiple triggers, you haven't built a real agent, just a script with an LLM call.

### Per-student meal labelling: yes
The caterer receives a labelled manifest tying each meal to a specific student.

**Why:** Solves three problems at once — dietary safety (the wrong box can't go to the wrong student), preference tracking (feedback tied to specific meals), and on-site distribution speed (manager and driver hand boxes out faster). May require slight compensation for caterer extra time; that's a small operational cost for a large safety and learning benefit.

### Escalation: confidence-aware, not binary
Agent emits a confidence score with every decision. Threshold for auto-act vs escalate is configurable per decision type, starts conservative, gets more permissive as approval history accumulates.

**Why:** This is the *infrastructure* for the gradual human-to-agent handoff Dylan described, not just a binary "approve every time." Without this, "minimal human input now, less later" is a promise; with this, it's a mechanism.

### Preference capture: at enrolment, not weekly polling
Preferences are a property of the student, captured once per term at enrolment. Opt-in weekly customisation surface (a link to override next week's pick). Default behaviour: system picks based on dietary requirements + stated preferences + observed past ratings.

**Why:** Rejected the weekly-poll-every-student idea because (1) response rates degrade and become selection-biased, (2) adds friction to a system whose job is removing friction, (3) asks the same stable question every week. Preferences are durable data; meals are variable. Build durable data structures and learn from rating signal, not survey signal.

### Absence prediction: calendar rules only, no ML
A small rules table handles term-end, exam fortnight, public holiday Mondays, parent-teacher nights. No machine learning model.

**Why:** Considered training an ML model on weather + uni timetables + sporting events + term position. Rejected after analysis: data volume too thin (tens of observations per per-school per-day cell), base-rate ceiling too low ($15-30k/year theoretical maximum savings, much less in practice), Thursday order cadence breaks the model (weather forecasts past 3-4 days are weak, day-of signals arrive too late), and the buffer mechanism self-defeats (trust the model → smaller buffer → less training signal → can't keep trusting). Memo framing: "When operations scale 5-10x, the rule engine graduates to a learned model with the rules as the prior." Reading as judgement, not absence.

### Tutor meal buffer: a primitive, not a workaround
Consistent meals for tutors alongside students. Sized to absorb normal absence variance. Self-tuning loop: regularly half-eaten → shrink, regularly exhausted → expand.

**Why:** Improves tutor retention and hiring (better working conditions), removes "what do we do with extras" judgement from the manager, removes the food-waste problem, and creates a clean feedback signal on buffer sizing. Framed as deliberate design, not a workaround — tutors eating a guaranteed meal is just a better operating model than "tutors maybe get fed if there are leftovers."

### Food quality management: real performance system, not coercion
Rolling 4-week averages (not single-session noise). Cross-source rating corroboration (students, manager, tutors). Qualitative reasons required for extreme ratings. Per-student reliability scoring. Weekly anonymised feedback mirror to caterer. Proactive rotation as freshness mechanism (trial alternatives at low-risk schools regardless of ratings). Concrete service expectations: <3.5 over 4 weeks triggers conversation, <3.0 triggers alternative trial, >4.0 earns priority for new assignments.

**Why:** Considered "loss of work as blackmail/extortion" framing. Rejected because it would read badly in the memo even though the underlying lever (rotation) is legitimate. The "able to serve" overlap list IS the leverage — caterers know we have alternatives. Visible measurement is the discipline mechanism. No threats needed.

### Database: SQLite dev, Supabase mirror at submission
Build in SQLite for speed of iteration. One-way push to Supabase before submitting. Submission requires a viewable link; SQLite is too painful to develop against remotely.

**Why:** Spec says Airtable (easier) or Supabase (harder). SQLite plus mirror gives us local development speed with hosted-database submission. Don't build against Supabase from day one — too much friction in the iterative phase.

### Email I/O: simulated from day one
`emails/incoming/` and `emails/outgoing/` text files. Not real Gmail.

**Why:** Real Gmail is auth complexity we don't need in v1, but agent reasoning must handle the same messiness real caterers will produce (replies like "ok", "can you confirm 17 not 20?", "we're closed Tuesday"). Production swap-out is a tool-layer change only.

---

## What we discovered in the data

The dataset is deliberately messy. Finding the hidden requirements is how the submission stands out. We documented these edge cases and the choices they force.

### The dataset shape
6 schools, 4 caterers, 11 sessions per week, ~290 students. Schools run sessions on different days; some schools run multiple days; managers cover multiple schools. Most dinners are 5pm, but JPC is 6pm and MSHS is 4:45pm.

### Critical fine print
- **MOQ is per-caterer-per-week, not per-session.** Stated in a footnote on the caterers spreadsheet. Scales with menu variety (4 items = lower MOQ, 6 items = higher). Variety has a built-in cost.
- **"Assume all non-pork meals are halal"** — a single sentence in the menu PDF that does a lot of work. Halal students can be matched to any non-pork menu item.
- **VO ≠ Vegetarian.** The Chicken/Bacon/Avo Wrap is marked VO. "VO" means the caterer will swap to a vegetarian version on request, not that the dish is vegetarian. Treating VO as veg would be a safety bug.

### Data ambiguity we made calls on
- **GYG's "$50 per trip" delivery.** Other caterers say "per school per trip" explicitly; GYG just says "per trip." Read it as per-school per-trip — consistent with peers and conservative on cost. Documented as assumption.
- **GST inconsistency.** Lakehouse and Terrific quoted ex-GST. Kenko and GYG quoted inc-GST. We'll normalise to ex-GST in all comparisons and display.

### Free-text dietary mess
At least 15 distinct strings appear across student sheets: "No Beef", "No Pork", "No Fish", "No Seafood", "No Shellfish", "No Red Meat", "Nut Free", "Vegetarian", "Halal", "Gluten Free", "Dairy Free", "Opted out of Catering", and combinations. Key distinctions:
- "No Seafood" ≠ "No Shellfish" (different restrictions)
- "Opted out" can combine with real restrictions (e.g. "Nut Free, No Shellfish, Opted out of Catering") — opt-out is operative, but parse the rest in case they un-opt-out

We'll build a controlled vocabulary and a mapping table during ingest.

### Structural quirks
- Same student name across schools ("Noah Hall" at ISHS-Thursday and CHAC-Monday) — must key students by (school, name) or generated ID. Absence matching requires school context.
- Exclusions can be partial — CHAC 3 May cancels Y10 and Y12 but Y11 still attends. Exclusion model needs year-level granularity.
- Absences arrive *after* the Thursday order is sent. Cannot always be amended in time. Known operational leak we document rather than pretend to solve.
- Spreadsheet structure: empty row 0, school-day header row 1, column headers row 2, data row 3+. Sheet names mix conventions.

### Caterer contact quirks
- Carmen at Lakehouse has a Padea-domain email (proxy/forwarder?). Medium Giraffe at GYG has Dylan's submission address. James Chern's email/name pairing is ambiguous in the PDF.
- CC preferences are per-person, not uniform: GYG chef wants cc'd, James at Terrific explicitly does not. Config flag per contact.

### Structural risks
- **Kenko is the single supplier for ISHS.** Highest MOQ, lowest per-meal price. If quality drops, no rotation option. Flag in memo as known risk; don't solve in v1.

---

## What we're building and what we're not

### v1 commitment (Phase 2 of the roadmap)
- Database schema and ingest with all the data quirks handled
- Tool layer (DB queries, email I/O, workflow logging)
- Agent skeleton with hybrid trigger model
- Thursday weekly ordering trigger (full)
- Absence intake trigger (full)
- Pre-delivery reminder trigger (light)
- Decision log (HTML, regenerated per agent run)

### v1 over-engineering (the edge case work — Phase 3 of the roadmap)
**High priority — fully built:**
1. Adversarial test harness (caterer closes, school cancels late, duplicate feedback, name collisions, etc.). The single highest-leverage thing for the demo because edge-case handling is what the judges look for.
2. Inbound email parsing for caterer chaos (Claude classifies intent, routes accordingly).

**Medium priority — partial, demonstrate seams:**
3. Confidence-aware escalation (config-driven thresholds).
4. Per-student preference learning with cold-start (Claude reasons over feedback history, not classical ML).

### Acknowledged in memo, not built
5. "Why did you do this" interface for coordinator queries.
6. What-if simulator for rotation projections.
7. Anomaly detection on inputs (enrolment changes, price changes, overlapping manager schedules).
8. Caterer rotation as explore/exploit logic.

### Not in scope at all
- Sick-tutor replacement agent (different module — architecture supports it, but building it is scope creep)
- Real Gmail integration (simulated email is sufficient)
- Web app, auth, payment, complex deployment

---

## What we built today (concrete deliverables)

### Repository structure (scaffolded, committed, pushed)
GitHub repo at `github.com/kyecampbell/padea_ops_agent` (private).

```
padea_ops_agent/
├── README.md                       # Project overview + layout
├── PROJECT_CONTEXT.md              # Business context + goals
├── DECISIONS.md                    # Architectural decision log
├── .env.example                    # Template for API keys
├── .gitignore                      # Excludes .env, *.db, __pycache__, etc.
├── requirements.txt                # Python dependencies
├── config/                         # Rules and thresholds (not code)
│   └── settings.py
├── data/
│   ├── raw/                        # Untouched source files
│   └── processed/                  # Cleaned/transformed data
├── docs/
│   ├── memo_notes.md
│   ├── process_diagram_notes.md
│   └── schema_notes.md
├── emails/
│   ├── incoming/                   # Simulated inbound emails
│   └── outgoing/                   # Simulated outbound drafts
├── logs/
│   ├── runs/                       # Structured JSON per agent run
│   └── html/                       # Rendered decision logs
├── schema/
│   └── schema.sql                  # Placeholder, schema not yet designed
├── src/
│   ├── agent/
│   │   ├── loop.py                 # Agent reasoning loop (placeholder)
│   │   ├── escalation.py           # Escalation logic (placeholder)
│   │   └── prompts/                # Prompt templates folder
│   ├── importers/                  # Data ingest scripts
│   ├── tools/                      # Reusable primitives for any agent
│   └── workflows/                  # Trigger entry points
└── tests/
    ├── adversarial/                # Scenario-level edge case tests
    └── unit/                       # Tool-level unit tests
```

### Documentation written today
- **PROJECT_CONTEXT.md** — comprehensive business context, goals, dataset summary, all edge cases identified, every decision made and why. This file is the source-of-truth spec for the build.
- **DECISIONS.md** — architectural decision log, templated for ADR-style entries.
- **README.md** — project overview, layout diagram, architecture explanation (workflows = trigger entry points, agent = shared reasoning loop, tools = reusable primitives, config = rules/thresholds, logs = audit trail).

### Tooling decisions locked in
- Python as the language
- SQLite for development, Supabase for submission
- Anthropic SDK with Claude Sonnet 4.6 (reasoning) and Haiku 4.5 (routing)
- Tool-calling pattern, ~15 tool calls per agent run maximum
- Claude Code as the build assistant (in VS Code or terminal)
- Git for version control, GitHub for hosting

### Environment setup
- API account funded ($20 credit)
- Project moved out of iCloud-synced Desktop to `~/Projects/padea_ops_agent`
- Git configured with proper identity (Kye Campbell / kyec898@gmail.com)
- GitHub CLI installed and authenticated
- Repo pushed to GitHub as private, ready to share with Dylan at submission

---

## The roadmap going forward

### Phase 1: Foundations — Saturday 23 May
**Schema design session** (here in chat, 60–90 min focus block). Tables, columns, relationships, why each table exists. This is the most important thinking session of the build — schema is the contract everything else depends on, including future agents. Once locked, ingest scripts almost write themselves.

Then: build schema in SQLite, write ingest scripts handling all the data quirks identified today (VO ≠ veg, halal rule, opt-out combinations, name collisions, partial exclusions, GST normalisation, controlled dietary vocabulary).

**Bar for end of Saturday:** populated database with all 6 schools, 4 caterers, 11 sessions, ~290 students.

### Phase 1 continued: Sunday 24 May
Shared Python tool layer (DB queries, email I/O, workflow log writer). Agent skeleton with the hybrid trigger model. One end-to-end run with a dummy trigger.

**Bar for end of Sunday:** `python agent.py --trigger thursday_order` does something observable.

### Phase 2: Core workflow — Monday & Tuesday
**Monday:** Order generation — read next week's sessions, compute eligibility, apply MOQ across the week, pick menu items respecting dietary distribution, per-student meal assignments. Write draft orders to DB. No emails sent yet.

**Tuesday:** Email drafting, sending, decision log generator. HTML timeline log per run.

**Bar for end of Tuesday:** Full ordering workflow produces emails I'd send to a real caterer, plus readable decision log.

### Phase 3: Edge cases — Wednesday & Thursday
**Wednesday:** Adversarial test harness + inbound email parsing.

**Thursday:** Calendar-aware quantity adjustment + tutor buffer + absence intake trigger.

**Bar for end of Thursday:** Build is feature-complete.

### Phase 4: Deliverables — Friday 29 May
Demo video (5 min), one-page memo, process diagram, Supabase mirror, polish. Submit by 8pm, not 11:59pm.

---

## Open decisions for tomorrow

Nothing blocking schema design. Two minor calls deferred:

1. **Where to put `config/` rules** — Python file (current) vs YAML/JSON data files. Lean toward data files but not urgent.
2. **Whether `src/agent/prompts/` folder is premature** — Claude Code created it; we'll see whether we have enough prompt files to justify the folder by mid-week.

---

## How today maps to the judging criteria

**Functionality** ("how not dumb are your requirements?"):
- Goal reframe from "ordering tool" to "satisfaction loop"
- Hybrid trigger model vs batch
- Per-student labelling for safety
- Calendar rules vs ML for absences
- Tutor buffer as primitive
- Real performance management vs coercion

**Learning** (judged from memo):
- Documented every decision with reasoning
- Showed range of options considered before each choice
- Named known leaks honestly (absence timing, Kenko single-source, GST/delivery ambiguity)
- Demonstrated knowing when NOT to build (ML model, scope-creep into other modules)

**Taste** (deliberately vague):
- Clean separation of concerns in repo layout
- Documentation as infrastructure, not afterthought
- Restraint on features
- Architecture-with-room-to-grow over breadth-with-no-depth

---

## What tomorrow looks like

Block 90 minutes of focus, ideally morning. Open this conversation. Type "ready for schema." We work through:

- What entities exist (school, session, student, enrolment, caterer, menu_item, dietary_tag, capability, order, order_line, feedback, contact, etc.)
- What each table holds
- How they relate (foreign keys, junction tables)
- Why each table exists (and what we deliberately don't include)
- The controlled dietary vocabulary as a real table

Then you take the agreed schema to Claude Code with a clear specification, and Claude Code writes the SQL. We commit, run the ingest scripts together, and Sunday starts with a populated database.

Good day of work. Rest up.
