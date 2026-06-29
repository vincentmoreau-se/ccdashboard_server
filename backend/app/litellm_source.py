"""Optional LiteLLM data source.

Every Claude Code request goes through the LiteLLM proxy, so LiteLLM holds usage
for *everyone*, while the ccdashboard client only covers participants who installed
it. This background poller pulls per-key daily usage from LiteLLM and fills in the
gaps — but only for (user, day) pairs the ccdashboard client did not already cover,
so tokens are never double-counted.

Identity pivot: a LiteLLM virtual key is stored as `sha256_hex(key)`, and the
ccdashboard client derives `user_id = "key:" + sha256_hex(key)` from the very same
key. So `user_id = "key:" + <LiteLLM token hash>` joins the two sources exactly, and
the participant CSV enrichment (joined by user_id) applies unchanged.

Disabled unless CCSRV_LITELLM_ENABLED=true.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import get_settings
from app.db import get_conn, write_lock
from app.ingest import persist_sessions
from app.models import SessionIn, Usage

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0)
PROJECT_LABEL = "(litellm)"


def _parse_dt(value: str | None) -> datetime | None:
    """Parse a LiteLLM ISO timestamp; tolerate a trailing 'Z' and naive values."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _fetch_daily_activity(
    client: httpx.Client, base_url: str, start: str, end: str
) -> list[dict]:
    """Fetch all pages of /user/daily/activity for [start, end] (YYYY-MM-DD)."""
    results: list[dict] = []
    page = 1
    while True:
        resp = client.get(
            f"{base_url}/user/daily/activity",
            params={
                "start_date": start,
                "end_date": end,
                "page": page,
                "page_size": 1000,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        results.extend(body.get("results", []))
        total_pages = (body.get("metadata") or {}).get("total_pages")
        if not total_pages or page >= total_pages:
            break
        page += 1
    return results


def _fetch_last_active(client: httpx.Client, base_url: str) -> dict[str, datetime]:
    """Map each key's sha256 token -> its last_active timestamp (best effort).

    /key/list caps page size at 100, so we paginate. `last_active` is often null;
    fall back to `updated_at`.
    """
    out: dict[str, datetime] = {}
    page = 1
    while True:
        try:
            resp = client.get(
                f"{base_url}/key/list",
                params={"return_full_object": "true", "page": page, "size": 100},
            )
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPError:
            logger.warning("litellm /key/list failed; live flag will rely on day only")
            break
        keys = body.get("keys", body) if isinstance(body, dict) else body
        for k in keys or []:
            if not isinstance(k, dict):
                continue
            token = k.get("token")
            ts = _parse_dt(k.get("last_active")) or _parse_dt(k.get("updated_at"))
            if token and ts:
                out[token] = ts
        total_pages = body.get("total_pages") if isinstance(body, dict) else None
        if not total_pages or page >= total_pages:
            break
        page += 1
    return out


def _aggregate(results: list[dict]) -> dict[tuple[str, str], dict]:
    """Sum LiteLLM daily metrics per (token hash, date) across all models."""
    agg: dict[tuple[str, str], dict] = {}
    for day in results:
        date = day.get("date")
        if not date:
            continue
        models = ((day.get("breakdown") or {}).get("models")) or {}
        for model_name, mdata in models.items():
            akb = (mdata or {}).get("api_key_breakdown") or {}
            for token, entry in akb.items():
                m = (entry or {}).get("metrics") or {}
                acc = agg.setdefault(
                    (token, date),
                    {
                        "input": 0,
                        "output": 0,
                        "cache_read": 0,
                        "cache_creation": 0,
                        "spend": 0.0,
                        "requests": 0,
                        "models": set(),
                    },
                )
                acc["input"] += m.get("prompt_tokens", 0) or 0
                acc["output"] += m.get("completion_tokens", 0) or 0
                acc["cache_read"] += m.get("cache_read_input_tokens", 0) or 0
                acc["cache_creation"] += m.get("cache_creation_input_tokens", 0) or 0
                acc["spend"] += m.get("spend", 0.0) or 0.0
                acc["requests"] += m.get("api_requests", 0) or 0
                if model_name:
                    acc["models"].add(model_name)
    return agg


def _ccdashboard_coverage() -> set[tuple[str, str]]:
    """(user_id, YYYY-MM-DD) pairs already covered by the ccdashboard client."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT user_id, substr(started_at, 1, 10) AS d "
        "FROM session WHERE data_source = 'ccdashboard' AND started_at IS NOT NULL"
    ).fetchall()
    return {(r["user_id"], r["d"]) for r in rows}


def poll_once() -> int:
    """Pull recent LiteLLM usage and upsert gap-filling sessions. Returns count."""
    settings = get_settings()
    base_url = settings.litellm_base_url.rstrip("/")
    if not settings.litellm_master_key:
        logger.warning("litellm poll skipped: CCSRV_LITELLM_MASTER_KEY is empty")
        return 0

    today = datetime.now(timezone.utc).date()
    start = (today - timedelta(days=max(0, settings.litellm_lookback_days))).isoformat()
    end = today.isoformat()
    today_str = today.isoformat()

    headers = {"Authorization": f"Bearer {settings.litellm_master_key}"}
    with httpx.Client(timeout=_TIMEOUT, headers=headers) as client:
        results = _fetch_daily_activity(client, base_url, start, end)
        last_active = _fetch_last_active(client, base_url)

    agg = _aggregate(results)
    covered = _ccdashboard_coverage()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.live_window_seconds)

    # Group gap-filling sessions per user; collect covered rows to purge.
    by_user: dict[str, list[SessionIn]] = {}
    stale_uids: list[str] = []
    for (token, date), acc in agg.items():
        user_id = f"key:{token}"
        source_key = f"litellm|{user_id}|default"
        if (user_id, date) in covered:
            # ccdashboard owns this day → drop any LiteLLM row we wrote earlier.
            stale_uids.append(f"{source_key}::litellm:{date}")
            continue
        seen = last_active.get(token)
        is_active = date == today_str and seen is not None and seen >= cutoff
        ended_at = (
            seen.isoformat() if seen is not None else f"{date}T23:59:59+00:00"
        )
        by_user.setdefault(user_id, []).append(
            SessionIn(
                session_id=f"litellm:{date}",
                project=PROJECT_LABEL,
                started_at=f"{date}T00:00:00+00:00",
                ended_at=ended_at,
                is_active=is_active,
                models=sorted(acc["models"]),
                message_count=acc["requests"],
                usage=Usage(
                    input=acc["input"],
                    output=acc["output"],
                    cache_read=acc["cache_read"],
                    cache_write_5m=acc["cache_creation"],
                ),
                cost=round(acc["spend"], 6),
                cost_known=True,
            )
        )

    if stale_uids:
        conn = get_conn()
        with write_lock():
            conn.execute("BEGIN")
            conn.executemany(
                "DELETE FROM session WHERE session_uid = ?",
                [(uid,) for uid in stale_uids],
            )
            conn.commit()

    written = 0
    for user_id, sessions in by_user.items():
        written += persist_sessions(
            source_key=f"litellm|{user_id}|default",
            machine_id="litellm",
            user_id=user_id,
            instance_id="default",
            sessions=sessions,
            data_source="litellm",
        )
    logger.info(
        "litellm poll: %d sessions written, %d ccdashboard-covered days skipped",
        written,
        len(stale_uids),
    )
    return written


async def litellm_poll_loop() -> None:
    interval = get_settings().litellm_poll_interval_seconds
    while True:
        try:
            await asyncio.to_thread(poll_once)
        except Exception:  # noqa: BLE001 — never let a transient error kill the loop
            logger.exception("litellm poll failed")
        await asyncio.sleep(interval)
