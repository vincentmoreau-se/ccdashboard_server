from __future__ import annotations

import asyncio
import logging

from app.config import get_settings
from app.db import get_conn, now_utc, write_lock
from app.metrics import TEAM_EXPR, TOKENS_SQL, _live_cutoff

logger = logging.getLogger(__name__)


def write_snapshot() -> None:
    """Snapshot global + per-team cumulative aggregates with a server timestamp.

    Live rates (tokens/min, cost/hour) are derived by diffing consecutive
    snapshots — this is immune to at-least-once re-sends because we read the
    current aggregate of the session table, not client deltas.
    """
    settings = get_settings()
    conn = get_conn()
    ts = now_utc()
    cutoff = _live_cutoff(settings.live_window_seconds)

    glob = conn.execute(
        f"""
        SELECT COALESCE(SUM({TOKENS_SQL}), 0) AS tokens,
               COALESCE(SUM(cost), 0.0) AS cost,
               COALESCE(SUM(CASE WHEN is_active=1 AND server_updated_at >= ?
                                 THEN 1 ELSE 0 END), 0) AS active
        FROM session
        """,
        (cutoff,),
    ).fetchone()

    teams = conn.execute(
        f"""
        SELECT {TEAM_EXPR} AS team_id,
               COALESCE(SUM({TOKENS_SQL}), 0) AS tokens,
               COALESCE(SUM(s.cost), 0.0) AS cost,
               COALESCE(SUM(CASE WHEN s.is_active=1 AND s.server_updated_at >= ?
                                 THEN 1 ELSE 0 END), 0) AS active
        FROM session s
        LEFT JOIN participant p ON p.user_id = s.user_id
        GROUP BY team_id
        """,
        (cutoff,),
    ).fetchall()

    rows = [("global", glob["tokens"], glob["cost"], glob["active"])]
    rows += [
        (f"team:{t['team_id']}", t["tokens"], t["cost"], t["active"]) for t in teams
    ]
    with write_lock():
        conn.executemany(
            "INSERT OR REPLACE INTO agg_snapshot "
            "(ts, scope, total_tokens, total_cost, active_sessions) "
            "VALUES (?, ?, ?, ?, ?)",
            [(ts, scope, tok, cost, act) for (scope, tok, cost, act) in rows],
        )
        conn.commit()


async def snapshot_loop() -> None:
    interval = get_settings().snapshot_interval_seconds
    while True:
        try:
            await asyncio.to_thread(write_snapshot)
        except Exception:  # noqa: BLE001
            logger.exception("snapshot write failed")
        await asyncio.sleep(interval)
