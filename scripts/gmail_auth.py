"""
scripts/gmail_auth.py
ONE-OFF, HUMAN-RUN Gmail OAuth consent. NOT part of the agent loop.

Run this once from a machine with a browser:

    python scripts/gmail_auth.py

It opens a browser, asks you to grant the Padea Desktop-app OAuth client access
to padea.catering@gmail.com, and writes the resulting token to
settings.gmail_token_path (config/gmail_token.json, gitignored). After that the
agent loads and refreshes the token automatically via src/tools/gmail_client.py —
this script never runs again unless the token is revoked or scopes change.

Sign in as the account in GMAIL_ADDRESS (padea.catering@gmail.com), NOT the demo
sink. The agent SENDS as this account and POLLS this account's inbox.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python scripts/gmail_auth.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from config.settings import settings  # noqa: E402
from src.tools.gmail_client import SCOPES  # noqa: E402


def main() -> None:
    creds_path = Path(settings.gmail_credentials_path)
    token_path = Path(settings.gmail_token_path)

    if not creds_path.exists():
        raise SystemExit(
            f"OAuth client not found at {creds_path}. "
            "Download the Desktop-app credentials from Google Cloud Console first."
        )

    print(f"Using OAuth client: {creds_path}")
    print(f"Requesting scopes:  {SCOPES}")
    print(f"Sign in as:         {settings.gmail_address}")
    print("A browser window will open for consent...\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    print(f"\nToken written to {token_path}")
    print("Done. The agent will load and refresh this token automatically.")


if __name__ == "__main__":
    main()
