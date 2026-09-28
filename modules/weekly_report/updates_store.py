"""PostgreSQL-backed store for stage-2 per-person weekly updates - one
table per project (weekly_updates_<slug>, see teams_config.project_slug),
auto-created on that project's first save. Keeping projects in separate
tables (rather than one shared table filtered by a `project` column) was
an explicit choice for this app over the normalized default.

Within a project's table, rows are keyed by (team, start_date, end_date)
so anyone who opens the same team/project for the same week sees everyone
else's already-saved (locked) entries. Entries are only ever appended once
a person ticks/saves their own update - there is no partial/draft state on
the server."""

import psycopg2.extras
from psycopg2 import errors, sql

from .db import get_connection
from .teams_config import project_slug

_UNDEFINED_TABLE = errors.lookup("42P01")  # UndefinedTable


def _table_name(project: str) -> str:
    return f"weekly_updates_{project_slug(project)}"


def _ensure_table(cur, table: sql.Identifier) -> None:
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
        sql.SQL("CREATE INDEX IF NOT EXISTS {idx} ON {table} (team, start_date, end_date)").format(
            idx=sql.Identifier(f"idx_{table.strings[0]}_week"), table=table
        )
    )


def _fetch_rows(cur, table: sql.Identifier, team: str, start_date: str, end_date: str) -> list:
    cur.execute(
        sql.SQL(
            """
            SELECT id, person_name, update_text, locked, saved_at
            FROM {table}
            WHERE team = %s AND start_date = %s AND end_date = %s
            ORDER BY id
            """
        ).format(table=table),
        (team, start_date, end_date),
    )
    return cur.fetchall()


def _to_public(rows: list) -> list:
    return [
        {
            "name": r["person_name"],
            "update": r["update_text"],
            "locked": r["locked"],
            "saved_at": r["saved_at"].isoformat(),
        }
        for r in rows
    ]


def get_entries(team: str, project: str, start_date: str, end_date: str) -> list:
    table = sql.Identifier(_table_name(project))
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                rows = _fetch_rows(cur, table, team, start_date, end_date)
    except _UNDEFINED_TABLE:
        return []  # nobody has saved anything for this project yet
    return _to_public(rows)


def add_entry(team: str, project: str, start_date: str, end_date: str, name: str, update: str) -> list:
    table = sql.Identifier(_table_name(project))
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            _ensure_table(cur, table)
            cur.execute(
                sql.SQL(
                    """
                    INSERT INTO {table} (team, start_date, end_date, person_name, update_text, locked)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    """
                ).format(table=table),
                (team, start_date, end_date, name, update),
            )
            rows = _fetch_rows(cur, table, team, start_date, end_date)
    return _to_public(rows)


def remove_entry(team: str, project: str, start_date: str, end_date: str, index: int) -> list:
    table = sql.Identifier(_table_name(project))
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                rows = _fetch_rows(cur, table, team, start_date, end_date)
                if 0 <= index < len(rows):
                    cur.execute(sql.SQL("DELETE FROM {table} WHERE id = %s").format(table=table), (rows[index]["id"],))
                    rows = _fetch_rows(cur, table, team, start_date, end_date)
    except _UNDEFINED_TABLE:
        return []
    return _to_public(rows)
