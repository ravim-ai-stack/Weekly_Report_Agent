-- Schema for weekly_report_agent, replacing the two flat-JSON stores
-- (data/weekly_updates.json and data/medtronic_timesheet_entries.json).

-- Each project gets its own weekly_updates_<slug> table (rather than one
-- shared table filtered by a `project` column) - an explicit choice for
-- this app. updates_store.py auto-creates a project's table the first
-- time someone saves an update for it (see _ensure_table()), validating
-- the project name against teams_config.KNOWN_PROJECTS first so a table
-- is never built from unvalidated input. The CREATE TABLEs below just
-- pre-seed the projects already configured in teams_config.py on a fresh
-- database; adding a new project to TEAMS or PROJECT_REPORT_CONFIG needs
-- no schema change - its table appears automatically on first save.
--
-- Within a project's table, rows are one per person's saved weekly
-- update, keyed by (team, start_date, end_date) plus id order (matching
-- the old JSON store's per-week list, in save order).
CREATE TABLE IF NOT EXISTS weekly_updates_nova_bio (
    id           BIGSERIAL PRIMARY KEY,
    team         TEXT NOT NULL,
    start_date   DATE NOT NULL,
    end_date     DATE NOT NULL,
    person_name  TEXT NOT NULL,
    update_text  TEXT NOT NULL,
    locked       BOOLEAN NOT NULL DEFAULT TRUE,
    saved_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_weekly_updates_nova_bio_week
    ON weekly_updates_nova_bio (team, start_date, end_date);

CREATE TABLE IF NOT EXISTS weekly_updates_phibro (
    id           BIGSERIAL PRIMARY KEY,
    team         TEXT NOT NULL,
    start_date   DATE NOT NULL,
    end_date     DATE NOT NULL,
    person_name  TEXT NOT NULL,
    update_text  TEXT NOT NULL,
    locked       BOOLEAN NOT NULL DEFAULT TRUE,
    saved_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_weekly_updates_phibro_week
    ON weekly_updates_phibro (team, start_date, end_date);

CREATE TABLE IF NOT EXISTS weekly_updates_medtronic (
    id           BIGSERIAL PRIMARY KEY,
    team         TEXT NOT NULL,
    start_date   DATE NOT NULL,
    end_date     DATE NOT NULL,
    person_name  TEXT NOT NULL,
    update_text  TEXT NOT NULL,
    locked       BOOLEAN NOT NULL DEFAULT TRUE,
    saved_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_weekly_updates_medtronic_week
    ON weekly_updates_medtronic (team, start_date, end_date);

CREATE TABLE IF NOT EXISTS weekly_updates_hmh (
    id           BIGSERIAL PRIMARY KEY,
    team         TEXT NOT NULL,
    start_date   DATE NOT NULL,
    end_date     DATE NOT NULL,
    person_name  TEXT NOT NULL,
    update_text  TEXT NOT NULL,
    locked       BOOLEAN NOT NULL DEFAULT TRUE,
    saved_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_weekly_updates_hmh_week
    ON weekly_updates_hmh (team, start_date, end_date);

-- Mirrors medtronic_timesheet.py's JSON store: one row per (date,
-- person), merged (hrs added, description appended) on repeat
-- same-day submission by the same person - see add_daily_entry(). Not
-- split per-project since it only ever holds Medtronic's daily entries.
CREATE TABLE IF NOT EXISTS timesheet_entries (
    id           BIGSERIAL PRIMARY KEY,
    entry_date   DATE NOT NULL,
    person       TEXT NOT NULL,
    description  TEXT NOT NULL,
    hrs          NUMERIC(5,2) NOT NULL CHECK (hrs > 0 AND hrs <= 24),
    saved_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ,
    UNIQUE (entry_date, person)
);

CREATE INDEX IF NOT EXISTS idx_timesheet_entries_date
    ON timesheet_entries (entry_date);

-- Generated report/workbook files (pptx/docx/xlsx), stored as blobs
-- rather than under output/ - see reports_store.py. Needed for Vercel:
-- its serverless filesystem is read-only/ephemeral, so a file written by
-- one request can't be assumed to exist for a later one (including
-- Medtronic's "build the next week on top of last week's file" pattern).
CREATE TABLE IF NOT EXISTS generated_reports (
    filename      TEXT PRIMARY KEY,
    content_type  TEXT NOT NULL,
    file_bytes    BYTEA NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
