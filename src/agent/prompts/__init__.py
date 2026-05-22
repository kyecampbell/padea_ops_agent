# src/agent/prompts/
#
# System prompts, few-shot examples, and instruction fragments for the agent.
# Keeping prompts here (rather than inline in code) makes them easy to version,
# review, and iterate on without touching logic files.
#
# Expected files as the agent matures:
#   system.py / system.md   — Core identity and behavioural instructions
#   tools.py                — Per-tool usage hints injected into context
#   escalation.py           — Language used when handing off to a human
