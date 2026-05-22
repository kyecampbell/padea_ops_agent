# config/settings.py
#
# Central place for rules, thresholds, and tunable parameters that should
# NOT be hardcoded in business logic or agent prompts.
#
# Examples of what belongs here:
#   - Order-value thresholds that trigger escalation
#   - Retry counts / timeout durations
#   - Feature flags (e.g. enable_email_drafting = True)
#   - Confidence cut-offs for agent decisions
#
# Values that come from the environment (API keys, credentials) belong
# in .env / environment variables — see .env.example.
