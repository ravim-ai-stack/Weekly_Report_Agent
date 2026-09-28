"""Shared PostgreSQL connection helper for the weekly-report data stores
(updates_store.py, medtronic_timesheet.py), which used to be flat JSON
files under data/ and now live in the weekly_report_agent database
(see db/schema.sql) at DATABASE_URL."""

import os
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv

load_dotenv()


@contextmanager
def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set - check .env.")
    conn = psycopg2.connect(database_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
