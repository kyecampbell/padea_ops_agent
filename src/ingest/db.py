"""Shared DB connection helper for ingest scripts."""
import os
import psycopg
from dotenv import load_dotenv

def get_conn() -> psycopg.Connection:
    load_dotenv()
    return psycopg.connect(os.environ["DATABASE_URL"])
