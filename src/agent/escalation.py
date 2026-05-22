# src/agent/escalation.py
#
# Escalation logic — decides when the agent should stop and hand off to a human.
#
# Responsibility:
#   - Define the conditions that require human review (e.g. order value above
#     threshold, ambiguous client intent, repeated tool failures).
#   - Produce a structured escalation payload: what the agent was trying to do,
#     what it found, and what specific decision it cannot make autonomously.
#   - Route the escalation (Slack message, email draft, task in project mgmt)
#     depending on urgency — routing rules live in config/settings.py.
#
# The loop in loop.py calls into this module; escalation.py does not call
# back into the loop (no circular dependency).
