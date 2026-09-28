"""Stores generated report/workbook files (pptx/docx/xlsx) as blobs in
Postgres instead of the local output/ folder. Vercel's serverless
filesystem is read-only outside /tmp and /tmp doesn't persist across
invocations, so a file written by one request (e.g. api/generate) can't
be assumed to still be on disk for a later request (e.g. /download, or
Medtronic's "build on last week's file" pattern) - the database is the
one thing every invocation can reach. Each file is keyed by the same
filename that used to be its path under output/."""

import psycopg2
import psycopg2.extras
from psycopg2 import errors

from .db import get_connection

_UNDEFINED_TABLE = errors.lookup("42P01")  # UndefinedTable

CONTENT_TYPES = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _content_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return CONTENT_TYPES.get(ext, "application/octet-stream")


def _ensure_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS generated_reports (
            filename      TEXT PRIMARY KEY,
            content_type  TEXT NOT NULL,
            file_bytes    BYTEA NOT NULL,
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def save_report(filename: str, data: bytes) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            _ensure_table(cur)
            cur.execute(
                """
                INSERT INTO generated_reports (filename, content_type, file_bytes, updated_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (filename) DO UPDATE SET
                    content_type = EXCLUDED.content_type,
                    file_bytes = EXCLUDED.file_bytes,
                    updated_at = now()
                """,
                (filename, _content_type(filename), psycopg2.Binary(data)),
            )


def load_report(filename: str):
    """Returns (file_bytes, content_type), or None if not found."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT content_type, file_bytes FROM generated_reports WHERE filename = %s",
                    (filename,),
                )
                row = cur.fetchone()
    except _UNDEFINED_TABLE:
        return None
    if not row:
        return None
    return bytes(row["file_bytes"]), row["content_type"]


def latest_report_matching(prefix: str):
    """Most recently saved report whose filename starts with `prefix` -
    used by Medtronic to find the last generated report to build the next
    week's page on top of. Returns (filename, file_bytes), or None."""
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT filename, file_bytes FROM generated_reports
                    WHERE filename LIKE %s ESCAPE '\\'
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%",),
                )
                row = cur.fetchone()
    except _UNDEFINED_TABLE:
        return None
    if not row:
        return None
    return row["filename"], bytes(row["file_bytes"])
