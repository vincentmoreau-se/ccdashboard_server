from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone

# A single process-wide connection. SQLite in WAL mode allows concurrent reads
# while a write is in flight; we serialize writes with an explicit lock so the
# at-least-once ingest upserts never race each other.
_conn: sqlite3.Connection | None = None
_write_lock = threading.Lock()


SCHEMA = """
CREATE TABLE IF NOT EXISTS source_instance (
    source_key   TEXT PRIMARY KEY,
    machine_id   TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    instance_id  TEXT NOT NULL,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session (
    session_uid       TEXT PRIMARY KEY,
    source_key        TEXT NOT NULL,
    user_id           TEXT NOT NULL,
    session_id        TEXT NOT NULL,
    project           TEXT NOT NULL,
    cwd               TEXT,
    file_path         TEXT,
    ai_title          TEXT,
    git_branch        TEXT,
    cc_version        TEXT,
    started_at        TEXT,
    ended_at          TEXT,
    duration_seconds  REAL,
    is_active         INTEGER NOT NULL DEFAULT 0,
    provider          TEXT NOT NULL DEFAULT 'anthropic',
    models            TEXT NOT NULL DEFAULT '[]',
    message_count     INTEGER NOT NULL DEFAULT 0,
    in_tokens         INTEGER NOT NULL DEFAULT 0,
    out_tokens        INTEGER NOT NULL DEFAULT 0,
    cache_write_5m    INTEGER NOT NULL DEFAULT 0,
    cache_write_1h    INTEGER NOT NULL DEFAULT 0,
    cache_read        INTEGER NOT NULL DEFAULT 0,
    web_search        INTEGER NOT NULL DEFAULT 0,
    web_fetch         INTEGER NOT NULL DEFAULT 0,
    cost              REAL NOT NULL DEFAULT 0,
    cost_known        INTEGER NOT NULL DEFAULT 1,
    tool_counts       TEXT NOT NULL DEFAULT '{}',
    skipped_lines     INTEGER NOT NULL DEFAULT 0,
    lines_generated   INTEGER NOT NULL DEFAULT 0,
    language_counts   TEXT NOT NULL DEFAULT '{}',
    framework_counts  TEXT NOT NULL DEFAULT '{}',
    builtin_tool_counts  TEXT NOT NULL DEFAULT '{}',
    user_tool_counts  TEXT NOT NULL DEFAULT '{}',
    skill_counts      TEXT NOT NULL DEFAULT '{}',
    mcp_server_counts TEXT NOT NULL DEFAULT '{}',
    subagent_counts   TEXT NOT NULL DEFAULT '{}',
    slash_command_counts TEXT NOT NULL DEFAULT '{}',
    server_updated_at TEXT NOT NULL,
    data_source       TEXT NOT NULL DEFAULT 'ccdashboard'
);
CREATE INDEX IF NOT EXISTS idx_session_user    ON session(user_id);
CREATE INDEX IF NOT EXISTS idx_session_started ON session(started_at);
CREATE INDEX IF NOT EXISTS idx_session_updated ON session(server_updated_at);
CREATE INDEX IF NOT EXISTS idx_session_active  ON session(is_active);

CREATE TABLE IF NOT EXISTS participant (
    user_id      TEXT PRIMARY KEY,
    team_id      TEXT NOT NULL,
    localisation TEXT,
    display_name TEXT
);

CREATE TABLE IF NOT EXISTS agg_snapshot (
    ts              TEXT NOT NULL,
    scope           TEXT NOT NULL,
    total_tokens    INTEGER NOT NULL,
    total_cost      REAL NOT NULL,
    active_sessions INTEGER NOT NULL,
    PRIMARY KEY (ts, scope)
);
CREATE INDEX IF NOT EXISTS idx_snapshot_ts ON agg_snapshot(ts);

-- Skill-submitted evaluation score per participant. UPSERT on user_id keeps the
-- latest submission (a participant can re-run the skill).
CREATE TABLE IF NOT EXISTS evaluation (
    user_id           TEXT PRIMARY KEY,
    score             REAL NOT NULL,
    max_score         REAL NOT NULL DEFAULT 100,
    feedback          TEXT,
    evaluated_at      TEXT,
    server_updated_at TEXT NOT NULL
);
"""


def now_utc() -> str:
    """Server-clock ISO8601 timestamp (the only clock we trust for ordering)."""
    return datetime.now(timezone.utc).isoformat()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    """Add a column to an existing table if missing.

    `CREATE TABLE IF NOT EXISTS` never alters a table that already exists, so new
    columns must be backfilled here for databases created before this code shipped.
    """
    existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init_db(db_path: str) -> sqlite3.Connection:
    """Open (or reopen) the process-wide connection and ensure the schema."""
    global _conn
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    _ensure_column(conn, "session", "lines_generated", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "session", "language_counts", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "session", "framework_counts", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "session", "builtin_tool_counts", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "session", "user_tool_counts", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "session", "skill_counts", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "session", "mcp_server_counts", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "session", "subagent_counts", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "session", "slash_command_counts", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(conn, "session", "data_source", "TEXT NOT NULL DEFAULT 'ccdashboard'")
    conn.commit()
    _conn = conn
    return conn


def get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Database not initialized; call init_db() first")
    return _conn


def write_lock() -> threading.Lock:
    return _write_lock


def close_db() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
