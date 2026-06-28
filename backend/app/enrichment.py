from __future__ import annotations

import csv
import io
import os

from app.db import get_conn, write_lock

UNKNOWN = "UNKNOWN"


def _normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for raw in rows:
        # tolerate header case / whitespace variations
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        user_id = row.get("user_id") or row.get("user") or row.get("email")
        if not user_id:
            continue
        out.append(
            {
                "user_id": user_id,
                "team_id": row.get("team_id") or row.get("team") or UNKNOWN,
                "localisation": row.get("localisation")
                or row.get("location")
                or None,
                "display_name": row.get("display_name") or row.get("name") or None,
            }
        )
    return out


def _replace_participants(rows: list[dict[str, str]]) -> int:
    conn = get_conn()
    with write_lock():
        conn.execute("DELETE FROM participant")
        conn.executemany(
            "INSERT OR REPLACE INTO participant "
            "(user_id, team_id, localisation, display_name) "
            "VALUES (:user_id, :team_id, :localisation, :display_name)",
            rows,
        )
        conn.commit()
    return len(rows)


def load_from_text(text: str) -> int:
    """Parse CSV text and (re)load the participant table. Returns row count."""
    reader = csv.DictReader(io.StringIO(text))
    rows = _normalize_rows(list(reader))
    return _replace_participants(rows)


def load_from_path(path: str) -> int:
    """Load participants from a CSV file at startup. Missing file is tolerated."""
    if not path or not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8-sig") as fh:
        return load_from_text(fh.read())


def known_user_ids() -> set[str]:
    conn = get_conn()
    rows = conn.execute("SELECT user_id FROM participant").fetchall()
    return {r["user_id"] for r in rows}


def unknown_users_in_sessions() -> list[str]:
    """user_ids that have ingested sessions but are absent from the CSV."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT s.user_id FROM session s "
        "LEFT JOIN participant p ON p.user_id = s.user_id "
        "WHERE p.user_id IS NULL ORDER BY s.user_id"
    ).fetchall()
    return [r["user_id"] for r in rows]
