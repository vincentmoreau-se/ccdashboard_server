from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.db import get_conn


def _eur(usd: float | None) -> float:
    """Convert a stored USD cost to the display currency (rounded to 4 decimals).

    Stored costs are USD (Anthropic list prices client-side, LiteLLM `spend`); the
    dashboard labels everything "€". The single conversion point keeps both sources
    consistent. Rate defaults to 1.0 (no-op) unless CCSRV_USD_EUR_RATE is set.
    """
    return round((usd or 0.0) * get_settings().usd_eur_rate, 4)


# Boundary of "today" for the period filter is the local civil day in France,
# not UTC (a UTC midnight would flip "today" at 02:00 Paris time in summer).
PARIS_TZ = ZoneInfo("Europe/Paris")

# "tokens" everywhere = input + output (generated/consumed tokens), matching the
# local ccdashboard headline. Cache tokens (cache_read dominates, ~100x) are NOT
# counted here — they're surfaced separately as cache_efficiency / cache_* fields.
TOKENS_SQL = "(in_tokens + out_tokens)"

# A session is "live" if the server saw it recently AND the client flagged it
# active. is_active alone is unreliable (a dead client leaves it stuck at 1).
TEAM_EXPR = "COALESCE(p.team_id, 'UNKNOWN')"
LOC_EXPR = "COALESCE(p.localisation, 'UNKNOWN')"


def _live_cutoff(live_window_seconds: int) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=live_window_seconds)
    return cutoff.isoformat()


def _start_of_today_utc() -> str:
    """Midnight (Europe/Paris) of the current day, as a UTC ISO string.

    Comparable lexicographically to the +00:00 ISO timestamps stored in the
    session table (started_at), so it can be used directly in a SQL `>=` bound.
    """
    now_local = datetime.now(PARIS_TZ)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(timezone.utc).isoformat()


def _period_clause(period: str, alias: str = "s") -> tuple[str, list]:
    """WHERE fragment (+ params) restricting sessions to ones STARTED "today".

    We filter on started_at (when the session actually ran), NOT server_updated_at:
    ingest is at-least-once and re-sends whole sessions, so server_updated_at gets
    bumped to "now" for every still-reported session — making it equal to the
    all-time total. started_at is rewritten identically on each re-send, so it is
    immune to that. A session straddling midnight is attributed to its start day
    (same convention as timeseries()). period != "today" adds no constraint.
    """
    if period == "today":
        return f"{alias}.started_at >= ?", [_start_of_today_utc()]
    return "", []


# --------------------------------------------------------------------------
# Historical / cumulative
# --------------------------------------------------------------------------


def overview() -> dict:
    conn = get_conn()
    row = conn.execute(
        f"""
        SELECT
            COUNT(*)                       AS session_count,
            COUNT(DISTINCT user_id)        AS participant_count,
            COALESCE(SUM(in_tokens), 0)    AS input,
            COALESCE(SUM(out_tokens), 0)   AS output,
            COALESCE(SUM(cache_read), 0)   AS cache_read,
            COALESCE(SUM(cache_write_5m + cache_write_1h), 0) AS cache_write,
            COALESCE(SUM({TOKENS_SQL}), 0) AS total_tokens,
            COALESCE(SUM(cost), 0.0)       AS total_cost,
            MIN(CASE WHEN cost_known=0 THEN 0 ELSE 1 END) AS cost_known
        FROM session
        """
    ).fetchone()
    teams = conn.execute(
        f"""
        SELECT COUNT(DISTINCT {TEAM_EXPR}) AS n
        FROM session s LEFT JOIN participant p ON p.user_id = s.user_id
        """
    ).fetchone()
    cache_total = row["cache_read"] + row["cache_write"]
    cache_eff = (row["cache_read"] / cache_total) if cache_total else 0.0
    return {
        "session_count": row["session_count"],
        "participant_count": row["participant_count"],
        "team_count": teams["n"],
        "total_tokens": row["total_tokens"],
        "input_tokens": row["input"],
        "output_tokens": row["output"],
        "cache_read_tokens": row["cache_read"],
        "cache_write_tokens": row["cache_write"],
        "cache_efficiency": round(cache_eff, 4),
        "total_cost": _eur(row["total_cost"]),
        "cost_known": bool(row["cost_known"]) if row["cost_known"] is not None else True,
    }


def timeseries(bucket: str = "hour", metric: str = "cost") -> list[dict]:
    """Cumulative attribution to each session's started_at bucket.

    Smooth live curves come from agg_snapshot; this is the at-rest historical
    distribution and is fully idempotent (re-sends overwrite the session row).
    """
    conn = get_conn()
    # SQLite strftime on ISO timestamps. hour -> 'YYYY-MM-DD HH:00', day -> date.
    fmt = "%Y-%m-%d %H:00" if bucket == "hour" else "%Y-%m-%d"
    rows = conn.execute(
        f"""
        SELECT strftime('{fmt}', started_at) AS bucket,
               COUNT(*) AS session_count,
               COALESCE(SUM({TOKENS_SQL}), 0) AS tokens,
               COALESCE(SUM(cost), 0.0) AS cost
        FROM session
        WHERE started_at IS NOT NULL
        GROUP BY bucket
        ORDER BY bucket
        """
    ).fetchall()
    return [
        {
            "bucket": r["bucket"],
            "session_count": r["session_count"],
            "tokens": r["tokens"],
            "cost": _eur(r["cost"]),
            "value": r["tokens"] if metric == "tokens" else _eur(r["cost"]),
        }
        for r in rows
    ]


# Leaderboards can be ranked by any of these keys. None (no evaluation yet) sorts
# last; ties keep their relative order. Rank is recomputed in Python so it always
# matches the active sort criterion.
_SORT_KEYS = {"cost": "cost", "eval": "_sort_eval", "volume": "volume"}


def _sorted_with_rank(rows: list[dict], sort: str) -> list[dict]:
    key = _SORT_KEYS.get(sort, "cost")
    rows.sort(key=lambda r: (r.get(key) is None, -(r.get(key) or 0)))
    for rank, r in enumerate(rows, 1):
        r["rank"] = rank
        r.pop("_sort_eval", None)
    return rows


def leaderboard_teams(sort: str = "cost", period: str = "total") -> list[dict]:
    conn = get_conn()
    clause, params = _period_clause(period)
    where_sql = f"WHERE {clause}" if clause else ""
    rows = conn.execute(
        f"""
        SELECT {TEAM_EXPR} AS team_id,
               COUNT(DISTINCT s.user_id) AS participant_count,
               COUNT(*) AS session_count,
               COALESCE(SUM({TOKENS_SQL}), 0) AS tokens,
               COALESCE(SUM(s.cost), 0.0) AS cost,
               COALESCE(SUM(s.lines_generated), 0) AS volume,
               COALESCE(SUM(s.cache_read), 0) AS cache_read,
               COALESCE(SUM(s.cache_write_5m + s.cache_write_1h), 0) AS cache_write
        FROM session s
        LEFT JOIN participant p ON p.user_id = s.user_id
        {where_sql}
        GROUP BY team_id
        """,
        params,
    ).fetchall()
    # Team evaluation = average of its members' latest scores (per user_id, joined
    # to team via the participant CSV). Computed separately to avoid multiplying the
    # score by each member's session count in the GROUP BY above.
    eval_rows = conn.execute(
        """
        SELECT COALESCE(p.team_id, 'UNKNOWN') AS team_id, AVG(e.score) AS eval_score
        FROM evaluation e
        LEFT JOIN participant p ON p.user_id = e.user_id
        GROUP BY team_id
        """
    ).fetchall()
    eval_by_team = {r["team_id"]: r["eval_score"] for r in eval_rows}

    out = []
    for r in rows:
        cache_total = r["cache_read"] + r["cache_write"]
        eval_score = eval_by_team.get(r["team_id"])
        out.append(
            {
                "team_id": r["team_id"],
                "participant_count": r["participant_count"],
                "session_count": r["session_count"],
                "tokens": r["tokens"],
                "cost": _eur(r["cost"]),
                "avg_cost": _eur(
                    r["cost"] / r["participant_count"]
                ) if r["participant_count"] else 0.0,
                "volume": r["volume"],
                "eval_score": round(eval_score, 1) if eval_score is not None else None,
                "_sort_eval": eval_score,
                "cache_efficiency": round(
                    (r["cache_read"] / cache_total) if cache_total else 0.0, 4
                ),
            }
        )
    return _sorted_with_rank(out, sort)


def leaderboard_locations(sort: str = "cost", period: str = "total") -> list[dict]:
    conn = get_conn()
    clause, params = _period_clause(period)
    where_sql = f"WHERE {clause}" if clause else ""
    rows = conn.execute(
        f"""
        SELECT {LOC_EXPR}  AS localisation,
               COUNT(DISTINCT {TEAM_EXPR}) AS team_count,
               COUNT(DISTINCT s.user_id) AS participant_count,
               COUNT(*) AS session_count,
               COALESCE(SUM({TOKENS_SQL}), 0) AS tokens,
               COALESCE(SUM(s.cost), 0.0) AS cost,
               COALESCE(SUM(s.lines_generated), 0) AS volume,
               COALESCE(SUM(s.cache_read), 0) AS cache_read,
               COALESCE(SUM(s.cache_write_5m + s.cache_write_1h), 0) AS cache_write
        FROM session s
        LEFT JOIN participant p ON p.user_id = s.user_id
        {where_sql}
        GROUP BY localisation
        """,
        params,
    ).fetchall()
    # Location evaluation = average of its members' latest scores, joined to a
    # localisation via the participant CSV (separate query to avoid inflating the
    # score by each member's session count in the GROUP BY above).
    eval_rows = conn.execute(
        """
        SELECT COALESCE(p.localisation, 'UNKNOWN') AS localisation, AVG(e.score) AS eval_score
        FROM evaluation e
        LEFT JOIN participant p ON p.user_id = e.user_id
        GROUP BY localisation
        """
    ).fetchall()
    eval_by_loc = {r["localisation"]: r["eval_score"] for r in eval_rows}

    out = []
    for r in rows:
        cache_total = r["cache_read"] + r["cache_write"]
        eval_score = eval_by_loc.get(r["localisation"])
        out.append(
            {
                "localisation": r["localisation"],
                "team_count": r["team_count"],
                "participant_count": r["participant_count"],
                "session_count": r["session_count"],
                "tokens": r["tokens"],
                "cost": _eur(r["cost"]),
                "avg_cost": _eur(
                    r["cost"] / r["participant_count"]
                ) if r["participant_count"] else 0.0,
                "volume": r["volume"],
                "eval_score": round(eval_score, 1) if eval_score is not None else None,
                "_sort_eval": eval_score,
                "cache_efficiency": round(
                    (r["cache_read"] / cache_total) if cache_total else 0.0, 4
                ),
            }
        )
    return _sorted_with_rank(out, sort)


def leaderboard_participants(sort: str = "cost", period: str = "total") -> list[dict]:
    conn = get_conn()
    clause, params = _period_clause(period)
    where_sql = f"WHERE {clause}" if clause else ""
    rows = conn.execute(
        f"""
        SELECT s.user_id AS user_id,
               COALESCE(p.display_name, s.user_id) AS display_name,
               {TEAM_EXPR} AS team_id,
               COUNT(*) AS session_count,
               COALESCE(SUM({TOKENS_SQL}), 0) AS tokens,
               COALESCE(SUM(s.cost), 0.0) AS cost,
               COALESCE(SUM(s.lines_generated), 0) AS volume,
               GROUP_CONCAT(DISTINCT s.data_source) AS data_sources
        FROM session s
        LEFT JOIN participant p ON p.user_id = s.user_id
        {where_sql}
        GROUP BY s.user_id, display_name, team_id
        """,
        params,
    ).fetchall()
    eval_rows = conn.execute("SELECT user_id, score FROM evaluation").fetchall()
    eval_by_user = {r["user_id"]: r["score"] for r in eval_rows}

    out = [
        {
            "user_id": r["user_id"],
            "display_name": r["display_name"],
            "team_id": r["team_id"],
            "session_count": r["session_count"],
            "tokens": r["tokens"],
            "cost": _eur(r["cost"]),
            "volume": r["volume"],
            "data_sources": sorted((r["data_sources"] or "").split(",")) if r["data_sources"] else [],
            "score": (
                round(eval_by_user[r["user_id"]], 1)
                if eval_by_user.get(r["user_id"]) is not None
                else None
            ),
            "_sort_eval": eval_by_user.get(r["user_id"]),
        }
        for r in rows
    ]
    return _sorted_with_rank(out, sort)


def team_detail(team_id: str) -> dict:
    conn = get_conn()
    rows = conn.execute(
        f"""
        SELECT s.*, {TEAM_EXPR} AS _team, {LOC_EXPR} AS _loc
        FROM session s
        LEFT JOIN participant p ON p.user_id = s.user_id
        WHERE {TEAM_EXPR} = ?
        ORDER BY s.server_updated_at DESC
        """,
        (team_id,),
    ).fetchall()
    sessions = [_session_brief(r) for r in rows]
    members = sorted({r["user_id"] for r in rows})
    models = Counter()
    for r in rows:
        for m in json.loads(r["models"] or "[]"):
            models[m] += 1
    return {
        "team_id": team_id,
        "localisation": rows[0]["_loc"] if rows else "UNKNOWN",
        "participants": members,
        "session_count": len(sessions),
        "models": [{"model": m, "session_count": c} for m, c in models.most_common()],
        "sessions": sessions,
    }


def model_distribution() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        f"SELECT models, provider, {TOKENS_SQL} AS tokens, cost FROM session"
    ).fetchall()
    agg: dict[str, dict] = defaultdict(
        lambda: {"session_count": 0, "tokens": 0, "cost": 0.0, "provider": "anthropic"}
    )
    for r in rows:
        models = json.loads(r["models"] or "[]") or ["(unknown)"]
        for m in models:
            agg[m]["session_count"] += 1
            agg[m]["tokens"] += r["tokens"]
            agg[m]["cost"] += r["cost"]
            agg[m]["provider"] = r["provider"]
    out = [
        {"model": m, **v, "cost": _eur(v["cost"])} for m, v in agg.items()
    ]
    out.sort(key=lambda x: x["tokens"], reverse=True)
    return out


def provider_split() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        f"""
        SELECT provider,
               COUNT(*) AS session_count,
               COALESCE(SUM({TOKENS_SQL}), 0) AS tokens,
               COALESCE(SUM(cost), 0.0) AS cost
        FROM session GROUP BY provider ORDER BY cost DESC
        """
    ).fetchall()
    return [
        {
            "provider": r["provider"],
            "session_count": r["session_count"],
            "tokens": r["tokens"],
            "cost": _eur(r["cost"]),
        }
        for r in rows
    ]


# The only session columns this helper may aggregate. `col` is interpolated into
# the SQL (sqlite can't bind an identifier), so it is validated against this
# whitelist — a guard so the private helper can't misbehave if reused with an
# unvetted column name.
_AGGREGATABLE_COLUMNS = frozenset(
    {
        "tool_counts",
        "language_counts",
        "framework_counts",
        "builtin_tool_counts",
        "user_tool_counts",
        "skill_counts",
        "mcp_server_counts",
        "subagent_counts",
        "slash_command_counts",
    }
)


def _aggregate_json_column(conn, col: str) -> Counter:
    """Aggregate a single JSON column ({name: count}) across all sessions.

    Robust to NULL (treated as empty) and invalid JSON (silently skipped so
    one corrupt session never breaks the aggregate).
    """
    if col not in _AGGREGATABLE_COLUMNS:
        raise ValueError(f"refusing to aggregate unknown column: {col!r}")
    rows = conn.execute(f"SELECT {col} FROM session").fetchall()
    counter: Counter = Counter()
    for r in rows:
        raw = r[col]
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            for name, n in data.items():
                counter[name] += n
    return counter


def tools_breakdown(limit: int = 20) -> list[dict]:
    conn = get_conn()
    counter = _aggregate_json_column(conn, "tool_counts")
    return [{"tool": t, "count": c} for t, c in counter.most_common(limit)]


def technologies_breakdown(limit: int = 20) -> dict:
    """Aggregate language_counts and framework_counts across all sessions.

    Returns:
        {
          "languages": [{"language": str, "count": int}, ...],
          "frameworks": [{"framework": str, "count": int}, ...]
        }
    """
    conn = get_conn()
    lang_counter = _aggregate_json_column(conn, "language_counts")
    fw_counter = _aggregate_json_column(conn, "framework_counts")
    return {
        "languages": [
            {"language": lang, "count": c}
            for lang, c in lang_counter.most_common(limit)
        ],
        "frameworks": [
            {"framework": fw, "count": c}
            for fw, c in fw_counter.most_common(limit)
        ],
    }


def tooling_breakdown(limit: int = 20) -> dict:
    """Aggregate tool-related JSON columns across all sessions.

    Item key is "tool" for all sub-lists (builtin, user, skills, mcp_servers,
    subagents, slash_commands) — a uniform key lets the frontend D3 layer bind
    by "tool" across every category without conditional logic.

    Returns:
        {
          "builtin":        [{"tool": str, "count": int}, ...],
          "user":           [...],
          "skills":         [...],
          "mcp_servers":    [...],
          "subagents":      [...],
          "slash_commands": [...]
        }
    The builtin/user split is sent as-is from the client; the server never
    reclassifies tool names between the two categories.
    """
    conn = get_conn()
    _cols = [
        ("builtin", "builtin_tool_counts"),
        ("user", "user_tool_counts"),
        ("skills", "skill_counts"),
        ("mcp_servers", "mcp_server_counts"),
        ("subagents", "subagent_counts"),
        ("slash_commands", "slash_command_counts"),
    ]
    return {
        key: [
            {"tool": t, "count": c}
            for t, c in _aggregate_json_column(conn, col).most_common(limit)
        ]
        for key, col in _cols
    }


def sessions_list(active: bool = False, limit: int = 100, live_window: int = 120) -> list[dict]:
    conn = get_conn()
    where = ""
    params: list = []
    if active:
        where = "WHERE s.is_active = 1 AND s.server_updated_at >= ?"
        params.append(_live_cutoff(live_window))
    rows = conn.execute(
        f"""
        SELECT s.*, {TEAM_EXPR} AS _team
        FROM session s
        LEFT JOIN participant p ON p.user_id = s.user_id
        {where}
        ORDER BY s.server_updated_at DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [_session_brief(r) for r in rows]


def _session_brief(r) -> dict:
    keys = r.keys()
    team = r["_team"] if "_team" in keys else None
    return {
        "session_id": r["session_id"],
        "user_id": r["user_id"],
        "team_id": team,
        "project": r["project"],
        "ai_title": r["ai_title"],
        "models": json.loads(r["models"] or "[]"),
        "provider": r["provider"],
        "is_active": bool(r["is_active"]),
        "data_source": r["data_source"] if "data_source" in keys else None,
        "message_count": r["message_count"],
        "duration_seconds": r["duration_seconds"],
        "tokens": r["in_tokens"] + r["out_tokens"],
        "cost": _eur(r["cost"]),
        "started_at": r["started_at"],
        "ended_at": r["ended_at"],
    }
