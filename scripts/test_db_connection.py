"""
scripts/test_db_connection.py

Smoke test: verify the Supabase Postgres connection is alive and the schema
has been deployed (schools table exists).

Usage:
    source .venv/bin/activate
    python scripts/test_db_connection.py
"""

import os
import sys
from pathlib import Path

# ── Load .env from project root ───────────────────────────────────────────────
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
print(f"  Loaded .env from {env_path}")

# ── Read DATABASE_URL ─────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("✗  DATABASE_URL is missing or empty in .env — cannot continue.")
    sys.exit(1)
print("✓  DATABASE_URL found in environment")

# ── Connect ───────────────────────────────────────────────────────────────────
import psycopg  # psycopg v3

conn = None
try:
    conn = psycopg.connect(DATABASE_URL)
    print("✓  Connected to Postgres")
except Exception as e:
    print(f"✗  Connection failed: {e}")
    sys.exit(1)

# ── Query 1: Postgres version ─────────────────────────────────────────────────
try:
    with conn.cursor() as cur:
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
    print(f"✓  SELECT version() → {version}")
except Exception as e:
    print(f"✗  SELECT version() failed: {e}")

# ── Query 2: schools row count ────────────────────────────────────────────────
try:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM schools;")
        count = cur.fetchone()[0]
    print(f"✓  SELECT COUNT(*) FROM schools → {count} rows")
except Exception as e:
    print(f"✗  SELECT COUNT(*) FROM schools failed: {e}")
    print("   (Is the schema deployed? Run docs/v3_final/Schema/v3_schema.sql in Supabase.)")

# ── Close ─────────────────────────────────────────────────────────────────────
finally:
    if conn:
        conn.close()
        print("✓  Connection closed cleanly")
