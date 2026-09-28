"""One-time import of the old flat-JSON stores (data/weekly_updates.json,
data/medtronic_timesheet_entries.json) into the weekly_report_agent
Postgres database, run once after applying db/schema.sql and before
relying on updates_store.py/medtronic_timesheet.py's DB-backed versions.
Safe to re-run: skips rows that already exist."""

import json
import os
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_THIS_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")

load_dotenv(os.path.join(BASE_DIR, ".env"))
DATABASE_URL = os.getenv("DATABASE_URL")


def migrate_weekly_updates(conn) -> int:
    path = os.path.join(DATA_DIR, "weekly_updates.json")
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    with conn.cursor() as cur:
        for key, entries in data.items():
            team, project, start_date, end_date = key.split("||")
            for e in entries:
                cur.execute(
                    """
                    INSERT INTO weekly_updates
                        (team, project, start_date, end_date, person_name, update_text, locked, saved_at)
                    SELECT %s, %s, %s, %s, %s, %s, %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM weekly_updates
                        WHERE team = %s AND project = %s AND start_date = %s AND end_date = %s
                          AND person_name = %s AND saved_at = %s
                    )
                    """,
                    (
                        team, project, start_date, end_date,
                        e["name"], e["update"], e.get("locked", True), e["saved_at"],
                        team, project, start_date, end_date, e["name"], e["saved_at"],
                    ),
                )
                count += cur.rowcount
    return count


def migrate_timesheet_entries(conn) -> int:
    path = os.path.join(DATA_DIR, "medtronic_timesheet_entries.json")
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    count = 0
    with conn.cursor() as cur:
        for e in entries:
            cur.execute(
                """
                INSERT INTO timesheet_entries
                    (entry_date, person, description, hrs, saved_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (entry_date, person) DO NOTHING
                """,
                (
                    e["date"], e["person"], e["description"], e["hrs"],
                    e["saved_at"], e.get("updated_at"),
                ),
            )
            count += cur.rowcount
    return count


def main() -> None:
    if not DATABASE_URL:
        print("DATABASE_URL is not set - check .env.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    try:
        updates_count = migrate_weekly_updates(conn)
        timesheet_count = migrate_timesheet_entries(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"Inserted {updates_count} weekly_updates row(s).")
    print(f"Inserted {timesheet_count} timesheet_entries row(s).")


if __name__ == "__main__":
    main()
