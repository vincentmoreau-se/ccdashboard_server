from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.auth import is_authenticated, require_dashboard
from app.config import Settings, get_settings
from app.db import get_conn
from app.metrics import (
    TEAM_EXPR,
    TOKENS_SQL,
    _eur,
    _live_cutoff,
)

router = APIRouter()


def _rate_from_snapshots(scope: str = "global", window: int = 3) -> dict:
    """tokens/min and cost/hour from the last `window` snapshots of a scope.

    Clamps negative deltas to 0 (client truncation/restart can lower totals).
    Returns nulls until at least 2 snapshots exist ("warming up").
    """
    conn = get_conn()
    rows = conn.execute(
        "SELECT ts, total_tokens, total_cost FROM agg_snapshot "
        "WHERE scope = ? ORDER BY ts DESC LIMIT ?",
        (scope, window),
    ).fetchall()
    if len(rows) < 2:
        return {"tokens_per_min": None, "cost_per_hour": None}
    newest, oldest = rows[0], rows[-1]
    dt = (
        datetime.fromisoformat(newest["ts"]) - datetime.fromisoformat(oldest["ts"])
    ).total_seconds()
    if dt <= 0:
        return {"tokens_per_min": None, "cost_per_hour": None}
    d_tokens = max(0, newest["total_tokens"] - oldest["total_tokens"])
    d_cost = max(0.0, newest["total_cost"] - oldest["total_cost"])
    return {
        "tokens_per_min": round(d_tokens / (dt / 60.0), 1),
        "cost_per_hour": _eur(d_cost / (dt / 3600.0)),
    }


def live_snapshot(settings: Settings) -> dict:
    conn = get_conn()
    cutoff = _live_cutoff(settings.live_window_seconds)

    counts = conn.execute(
        f"""
        SELECT COUNT(*) AS active_sessions,
               COUNT(DISTINCT s.user_id) AS active_participants,
               COUNT(DISTINCT {TEAM_EXPR}) AS active_teams,
               COALESCE(SUM({TOKENS_SQL}), 0) AS live_tokens,
               COALESCE(SUM(s.cost), 0.0) AS live_cost
        FROM session s
        LEFT JOIN participant p ON p.user_id = s.user_id
        WHERE s.is_active = 1 AND s.server_updated_at >= ?
        """,
        (cutoff,),
    ).fetchone()

    top_teams = conn.execute(
        f"""
        SELECT {TEAM_EXPR} AS team_id,
               COUNT(*) AS active_sessions,
               COALESCE(SUM({TOKENS_SQL}), 0) AS tokens
        FROM session s
        LEFT JOIN participant p ON p.user_id = s.user_id
        WHERE s.is_active = 1 AND s.server_updated_at >= ?
        GROUP BY team_id
        ORDER BY tokens DESC
        LIMIT 10
        """,
        (cutoff,),
    ).fetchall()

    models_rows = conn.execute(
        "SELECT models FROM session WHERE is_active = 1 AND server_updated_at >= ?",
        (cutoff,),
    ).fetchall()
    model_counts: dict[str, int] = {}
    for r in models_rows:
        for m in json.loads(r["models"] or "[]"):
            model_counts[m] = model_counts.get(m, 0) + 1

    rate = _rate_from_snapshots("global")
    return {
        "ts": _now_iso(),
        "active_sessions": counts["active_sessions"],
        "active_participants": counts["active_participants"],
        "active_teams": counts["active_teams"],
        "live_tokens": counts["live_tokens"],
        "live_cost": _eur(counts["live_cost"]),
        "tokens_per_min": rate["tokens_per_min"],
        "cost_per_hour": rate["cost_per_hour"],
        "top_teams": [
            {"team_id": t["team_id"], "active_sessions": t["active_sessions"],
             "tokens": t["tokens"]}
            for t in top_teams
        ],
        "models_in_use": [
            {"model": m, "count": c}
            for m, c in sorted(model_counts.items(), key=lambda x: -x[1])
        ],
        "currency": settings.currency,
    }


def _now_iso() -> str:
    from app.db import now_utc

    return now_utc()


@router.get("/api/live/snapshot", dependencies=[Depends(require_dashboard)])
def live_snapshot_endpoint(settings: Settings = Depends(get_settings)) -> dict:
    return live_snapshot(settings)


@router.get("/api/live/stream")
async def live_stream(
    request: Request, settings: Settings = Depends(get_settings)
) -> EventSourceResponse:
    # EventSource cannot send an Authorization header, so we authenticate via
    # the signed session cookie that the browser sends automatically.
    if not is_authenticated(request, settings):
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            data = await asyncio.to_thread(live_snapshot, settings)
            yield {"event": "live_snapshot", "data": json.dumps(data)}
            await asyncio.sleep(5)

    return EventSourceResponse(event_generator())
