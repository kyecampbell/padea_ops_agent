# Agent Context

This folder is the **bridge between the design documents and the running code**. It contains everything the Claude Sonnet 4.6 agent needs to reason correctly at runtime — its system prompt, domain rules, configurable thresholds, and a reference of every tool available to it.

## Contents

| File | Purpose |
|---|---|
| `system_prompt.md` | The full system prompt injected at every agent run. This is what `src/agent/loop.py` reads and passes to Claude. |
| `domain_knowledge.md` | Compact reference of business rules, controlled vocabularies, and data model highlights. The agent can consult this inline when reasoning. |
| `runtime_config.yaml` | Configurable thresholds and operational parameters. Loaded by `config/settings.py` at startup. Change values here without touching business logic. |
| `tools_reference.md` | Catalog of every tool the agent can call — name, signature, when to call it. Also serves as the build spec for the tool layer in `src/tools/`. |
| `email_templates/` | Python format-string templates for each outbound email type. One file per `email_type` enum value. Loaded by the email composition layer. |

## Design decisions reflected here

- **Templates in code, not DB** (V3-CM-01): All email templates are Python format strings here. Non-engineering operators can't edit them through the system; that is intentional for V3. V4 migration trigger: when operators need to edit copy without a deployment cycle.
- **System prompt is source-controlled**: Changes to the agent's reasoning instructions go through git, so behavioural regressions are auditable.
- **runtime_config.yaml is the only tuning surface**: Thresholds (quality floor, MOQ tier, pattern detection %) live here. The agent never hardcodes these values — it reads from config at startup.

## How it connects to the codebase

```
agent_context/system_prompt.md  ──►  src/agent/loop.py (reads at run start)
agent_context/runtime_config.yaml ──►  config/settings.py (loaded via PyYAML)
agent_context/tools_reference.md ──►  src/tools/ (build spec)
agent_context/email_templates/  ──►  src/agent/email_composer.py (imports)
```
