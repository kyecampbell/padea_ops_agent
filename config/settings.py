"""
config/settings.py

Loads all runtime configuration from two sources (in order of precedence):
  1. Environment variables / .env file (secrets: API keys, DB URL, etc.)
  2. agent_context/runtime_config.yaml (tunable thresholds and operational params)

Usage:
    from config.settings import settings
    print(settings.agent_model)
    print(settings.email_mode)
"""

import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# ---------------------------------------------------------------------------
# Load .env first so env vars are available before settings initialise.
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).parent.parent / ".env")

# ---------------------------------------------------------------------------
# Load agent_context/runtime_config.yaml
# ---------------------------------------------------------------------------
_CONFIG_PATH = Path(__file__).parent.parent / "agent_context" / "runtime_config.yaml"

def _load_yaml_config() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}

_yaml = _load_yaml_config()


class Settings(BaseSettings):
    """
    All configuration the agent needs at runtime.

    Secrets (DB URL, API keys) come from .env / environment variables.
    Thresholds and operational params come from runtime_config.yaml.
    Environment variables always win over yaml defaults.
    """

    # -----------------------------------------------------------------------
    # Secrets — must live in .env, never in runtime_config.yaml
    # -----------------------------------------------------------------------

    # Supabase Postgres connection string.
    # Format: postgresql://postgres:[password]@[host]:5432/postgres
    database_url: str = Field(default=os.getenv("DATABASE_URL", ""))

    # Anthropic API key for Claude.
    anthropic_api_key: str = Field(default=os.getenv("ANTHROPIC_API_KEY", ""))

    # -----------------------------------------------------------------------
    # Order composition
    # -----------------------------------------------------------------------
    order_hours_before_session: int = _yaml.get("order_hours_before_session", 72)
    exclusion_buffer_rate: float = _yaml.get("exclusion_buffer_rate", 0.10)
    standard_contingency_meals: int = _yaml.get("standard_contingency_meals", 0)

    # -----------------------------------------------------------------------
    # MOQ
    # -----------------------------------------------------------------------
    moq_shortfall_urgency: Literal["urgent", "notable", "informational"] = (
        _yaml.get("moq_shortfall_urgency", "notable")
    )

    # -----------------------------------------------------------------------
    # Quality monitoring
    # -----------------------------------------------------------------------
    quality_floor: float = _yaml.get("quality_floor", 3.0)
    quality_decline_threshold: float = _yaml.get("quality_decline_threshold", 0.5)
    tutor_1_pattern_threshold: float = _yaml.get("tutor_1_pattern_threshold", 0.25)

    # -----------------------------------------------------------------------
    # Monday consolidated summary
    # -----------------------------------------------------------------------
    weekly_summary_day: int = _yaml.get("weekly_summary_day", 1)      # 1 = Monday
    weekly_summary_hour: int = _yaml.get("weekly_summary_hour", 15)
    weekly_summary_minute: int = _yaml.get("weekly_summary_minute", 30)
    weekly_summary_window_minutes: int = _yaml.get("weekly_summary_window_minutes", 15)

    # -----------------------------------------------------------------------
    # Email
    # -----------------------------------------------------------------------
    email_mode: Literal["demo", "production"] = _yaml.get("email_mode", "demo")
    demo_email_address: str = _yaml.get("demo_email_address", "")

    gmail_token_path: str = _yaml.get("gmail_token_path", ".secrets/gmail_token.json")
    gmail_credentials_path: str = _yaml.get(
        "gmail_credentials_path", ".secrets/gmail_credentials.json"
    )

    # The Gmail account the agent sends as and polls. Lives in .env (secret-ish:
    # identifies the production inbox). Demo mode rewrites SEND targets to
    # demo_email_address but never changes which account we authenticate as.
    gmail_address: str = Field(default=os.getenv("GMAIL_ADDRESS", ""))

    # -----------------------------------------------------------------------
    # Agent loop
    # -----------------------------------------------------------------------
    max_tool_calls_per_run: int = _yaml.get("max_tool_calls_per_run", 15)
    agent_model: str = _yaml.get("agent_model", "claude-sonnet-4-6")
    crashed_run_staleness_minutes: int = _yaml.get("crashed_run_staleness_minutes", 30)

    # Haiku is permitted in EXACTLY ONE place: classify_inbound_email (inbound
    # routing). Every other model call uses agent_model (Sonnet). Referenced only
    # in src/tools/inbound.py.
    classifier_model: str = _yaml.get("classifier_model", "claude-haiku-4-5-20251001")

    # -----------------------------------------------------------------------
    # Caterer reach
    # -----------------------------------------------------------------------
    default_caterer_max_delivery_km: int = _yaml.get("default_caterer_max_delivery_km", 50)

    class Config:
        # Allow extra fields — future yaml keys won't crash old code.
        extra = "ignore"


# ---------------------------------------------------------------------------
# Singleton — import this everywhere.
# ---------------------------------------------------------------------------
settings = Settings()


# ---------------------------------------------------------------------------
# Startup validation — called from the agent's main() before any run begins.
# ---------------------------------------------------------------------------
def validate_settings() -> list[str]:
    """
    Returns a list of error strings. Empty list = all good.
    Caller should log errors and abort if the list is non-empty.
    """
    errors = []

    if not settings.database_url:
        errors.append("DATABASE_URL is not set. Add it to .env.")

    if not settings.anthropic_api_key:
        errors.append("ANTHROPIC_API_KEY is not set. Add it to .env.")

    if settings.email_mode == "demo" and not settings.demo_email_address:
        errors.append("email_mode is 'demo' but demo_email_address is not set in runtime_config.yaml.")

    if settings.email_mode == "production":
        errors.append(
            "WARNING: email_mode is 'production'. All emails will go to real recipients. "
            "Make sure this is intentional."
        )

    gmail_token = Path(settings.gmail_token_path)
    gmail_creds = Path(settings.gmail_credentials_path)
    if not gmail_token.exists():
        errors.append(f"Gmail token not found at {settings.gmail_token_path}. Run the OAuth flow first.")
    if not gmail_creds.exists():
        errors.append(f"Gmail credentials not found at {settings.gmail_credentials_path}. Download from Google Cloud Console.")

    return errors
