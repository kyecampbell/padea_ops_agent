# src/agent/loop.py
#
# The core agent execution loop.
#
# Responsibility:
#   - Accept a task description and initial context.
#   - Send the task + available tools to the Claude API.
#   - Parse the model's response: if it calls a tool, execute it and loop back;
#     if it returns a final answer, surface it and exit.
#   - Enforce iteration limits and timeout guards (from config/settings.py).
#   - Write a structured run log to logs/runs/ after every execution.
#
# This module is intentionally tool-agnostic — it does not know what any
# specific tool does. Tools are registered and passed in from the workflow
# or entrypoint that calls this loop.
