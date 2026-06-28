from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_ingest_token
from app.db import get_conn, now_utc, write_lock
from app.enrichment import known_user_ids
from app.models import EvalIn, EvalResponse, IngestPayload, IngestResponse, SessionIn

logger = logging.getLogger(__name__)

router = APIRouter()

SUPPORTED_SCHEMA = 1

_UPSERT_SQL = """
INSERT INTO session (
    session_uid, source_key, user_id, session_id, project, cwd, file_path,
    ai_title, git_branch, cc_version, started_at, ended_at, duration_seconds,
    is_active, provider, models, message_count,
    in_tokens, out_tokens, cache_write_5m, cache_write_1h, cache_read,
    web_search, web_fetch, cost, cost_known, tool_counts, skipped_lines,
    lines_generated, server_updated_at
) VALUES (
    :session_uid, :source_key, :user_id, :session_id, :project, :cwd, :file_path,
    :ai_title, :git_branch, :cc_version, :started_at, :ended_at, :duration_seconds,
    :is_active, :provider, :models, :message_count,
    :in_tokens, :out_tokens, :cache_write_5m, :cache_write_1h, :cache_read,
    :web_search, :web_fetch, :cost, :cost_known, :tool_counts, :skipped_lines,
    :lines_generated, :server_updated_at
)
ON CONFLICT(session_uid) DO UPDATE SET
    source_key=excluded.source_key,
    user_id=excluded.user_id,
    project=excluded.project,
    cwd=excluded.cwd,
    file_path=excluded.file_path,
    ai_title=excluded.ai_title,
    git_branch=excluded.git_branch,
    cc_version=excluded.cc_version,
    started_at=excluded.started_at,
    ended_at=excluded.ended_at,
    duration_seconds=excluded.duration_seconds,
    is_active=excluded.is_active,
    provider=excluded.provider,
    models=excluded.models,
    message_count=excluded.message_count,
    in_tokens=excluded.in_tokens,
    out_tokens=excluded.out_tokens,
    cache_write_5m=excluded.cache_write_5m,
    cache_write_1h=excluded.cache_write_1h,
    cache_read=excluded.cache_read,
    web_search=excluded.web_search,
    web_fetch=excluded.web_fetch,
    cost=excluded.cost,
    cost_known=excluded.cost_known,
    tool_counts=excluded.tool_counts,
    skipped_lines=excluded.skipped_lines,
    lines_generated=excluded.lines_generated,
    server_updated_at=excluded.server_updated_at
"""


def _iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None


def _session_row(s: SessionIn, source_key: str, user_id: str, server_ts: str) -> dict:
    return {
        "session_uid": f"{source_key}::{s.session_id}",
        "source_key": source_key,
        "user_id": user_id,
        "session_id": s.session_id,
        "project": s.project,
        "cwd": s.cwd,
        "file_path": s.file_path,
        "ai_title": s.ai_title,
        "git_branch": s.git_branch,
        "cc_version": s.cc_version,
        "started_at": _iso(s.started_at),
        "ended_at": _iso(s.ended_at),
        "duration_seconds": s.duration_seconds,
        "is_active": 1 if s.is_active else 0,
        "provider": s.provider,
        "models": json.dumps(s.models),
        "message_count": s.message_count,
        "in_tokens": s.usage.input,
        "out_tokens": s.usage.output,
        "cache_write_5m": s.usage.cache_write_5m,
        "cache_write_1h": s.usage.cache_write_1h,
        "cache_read": s.usage.cache_read,
        "web_search": s.usage.web_search,
        "web_fetch": s.usage.web_fetch,
        "cost": s.cost,
        "cost_known": 1 if s.cost_known else 0,
        "tool_counts": json.dumps(s.tool_counts),
        "skipped_lines": s.skipped_lines,
        "lines_generated": s.lines_generated,
        "server_updated_at": server_ts,
    }


@router.post(
    "/ingest",
    response_model=IngestResponse,
    dependencies=[Depends(require_ingest_token)],
)
def ingest(payload: IngestPayload) -> IngestResponse:
    if payload.schema_version != SUPPORTED_SCHEMA:
        logger.warning(
            "rejected ingest: unsupported schema_version=%s", payload.schema_version
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported schema_version {payload.schema_version}",
        )

    src = payload.source
    source_key = f"{src.machine_id}|{src.user_id}|{src.instance_id}"
    server_ts = now_utc()
    rows = [
        _session_row(s, source_key, src.user_id, server_ts) for s in payload.sessions
    ]

    conn = get_conn()
    try:
        with write_lock():
            conn.execute("BEGIN")
            conn.execute(
                "INSERT INTO source_instance "
                "(source_key, machine_id, user_id, instance_id, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(source_key) DO UPDATE SET last_seen=excluded.last_seen",
                (source_key, src.machine_id, src.user_id, src.instance_id,
                 server_ts, server_ts),
            )
            if rows:
                conn.executemany(_UPSERT_SQL, rows)
            conn.commit()
    except Exception:  # noqa: BLE001 — surface as 500 so the client retries
        conn.rollback()
        logger.exception("ingest failed; rolling back")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ingest failed",
        )

    known = known_user_ids()
    unknown = [src.user_id] if src.user_id not in known else []
    return IngestResponse(
        status="ok", accepted_sessions=len(rows), unknown_users=unknown
    )


_EVAL_UPSERT_SQL = """
INSERT INTO evaluation (
    user_id, score, max_score, feedback, evaluated_at, server_updated_at
) VALUES (
    :user_id, :score, :max_score, :feedback, :evaluated_at, :server_updated_at
)
ON CONFLICT(user_id) DO UPDATE SET
    score=excluded.score,
    max_score=excluded.max_score,
    feedback=excluded.feedback,
    evaluated_at=excluded.evaluated_at,
    server_updated_at=excluded.server_updated_at
"""


@router.post(
    "/ingest/eval",
    response_model=EvalResponse,
    dependencies=[Depends(require_ingest_token)],
)
def ingest_eval(payload: EvalIn) -> EvalResponse:
    if payload.max_score <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="max_score must be positive",
        )
    if not (0 <= payload.score <= payload.max_score):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"score must be within [0, {payload.max_score}]",
        )

    server_ts = now_utc()
    row = {
        "user_id": payload.user_id,
        "score": payload.score,
        "max_score": payload.max_score,
        "feedback": payload.feedback,
        "evaluated_at": _iso(payload.evaluated_at),
        "server_updated_at": server_ts,
    }

    conn = get_conn()
    try:
        with write_lock():
            conn.execute("BEGIN")
            conn.execute(_EVAL_UPSERT_SQL, row)
            conn.commit()
    except Exception:  # noqa: BLE001 — surface as 500 so the client retries
        conn.rollback()
        logger.exception("eval ingest failed; rolling back")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="eval ingest failed",
        )

    return EvalResponse(
        status="ok",
        user_id=payload.user_id,
        known_user=payload.user_id in known_user_ids(),
    )
