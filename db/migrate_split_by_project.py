"""One-time split of the original shared weekly_updates table (project
as a column) into one weekly_updates_<slug> table per project, per the
per-project-tables redesign (see updates_store.py). Run once, after the
JSON->Postgres migration and before relying on the new updates_store.py.

Includes "ACT" even though it is no longer a configured project in
teams_config.py (TEAMS/PROJECT_REPORT_CONFIG) - its 4 existing rows are
legacy data to preserve, not a project the app should let new saves go to
going forward (see updates_store.project_slug's KNOWN_PROJECTS check)."""

import os
import re
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from psycopg2 import sql

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(_THIS_DIR)

load_dotenv(os.path.join(BASE_DIR, ".env"))
DATABASE_URL = os.getenv("DATABASE_URL")


def _slug(project: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", project.lower()).strip("_")


def main() -> None:
    if not DATABASE_URL:
        print("DATABASE_URL is not set - check .env.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT to_regclass('weekly_updates') IS NOT NULL AS exists
                """
            )
            if not cur.fetchone()["exists"]:
                print("No shared weekly_updates table found - already migrated.")
                return

            cur.execute("SELECT DISTINCT project FROM weekly_updates ORDER BY project")
            projects = [r["project"] for r in cur.fetchall()]

            total_before = 0
            for project in projects:
                table = sql.Identifier(f"weekly_updates_{_slug(project)}")

                cur.execute(
                    sql.SQL(
                        """
                        CREATE TABLE IF NOT EXISTS {table} (
                            id           BIGSERIAL PRIMARY KEY,
                            team         TEXT NOT NULL,
                            start_date   DATE NOT NULL,
                            end_date     DATE NOT NULL,
                            person_name  TEXT NOT NULL,
                            update_text  TEXT NOT NULL,
                            locked       BOOLEAN NOT NULL DEFAULT TRUE,
                            saved_at     TIMESTAMPTZ NOT NULL DEFAULT now()
                        )
                        """
                    ).format(table=table)
                )
                cur.execute(
                    sql.SQL(
                        "CREATE INDEX IF NOT EXISTS {idx} ON {table} (team, start_date, end_date)"
                    ).format(idx=sql.Identifier(f"idx_weekly_updates_{_slug(project)}_week"), table=table)
                )

                cur.execute(
                    sql.SQL(
                        """
                        INSERT INTO {table} (team, start_date, end_date, person_name, update_text, locked, saved_at)
                        SELECT team, start_date, end_date, person_name, update_text, locked, saved_at
                        FROM weekly_updates WHERE project = %s
                        ORDER BY id
                        """
                    ).format(table=table),
                    (project,),
                )
                moved = cur.rowcount
                total_before += moved
                print(f"  {project} -> weekly_updates_{_slug(project)}: {moved} row(s)")

            cur.execute("SELECT count(*) AS n FROM weekly_updates")
            original_count = cur.fetchone()["n"]

            if total_before != original_count:
                raise RuntimeError(
                    f"Row count mismatch: copied {total_before}, original had {original_count}. "
                    "Not dropping weekly_updates - investigate before re-running."
                )

            cur.execute("DROP TABLE weekly_updates")
            print(f"Verified {total_before}/{original_count} rows copied. Dropped shared weekly_updates table.")

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
