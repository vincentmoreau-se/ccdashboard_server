from __future__ import annotations

import json


def test_overview_totals(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    ov = logged_in.get("/api/overview").json()
    assert ov["session_count"] == 2
    assert ov["participant_count"] == 1
    # tokens = sum of input+output for both sessions (cache surfaced separately)
    # sess-1: 12000+8000 = 20000 ; sess-2: 5000+3000 = 8000
    assert ov["total_tokens"] == 28000
    assert ov["input_tokens"] == 17000
    assert ov["cache_read_tokens"] == 60000
    assert abs(ov["total_cost"] - 1.7345) < 1e-6


def test_cache_efficiency_math(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    ov = logged_in.get("/api/overview").json()
    # cache_read = 60000 ; cache_write = 3000+1000 = 4000 ; eff = 60000/64000
    assert abs(ov["cache_efficiency"] - (60000 / 64000)) < 1e-4


def test_team_leaderboard_ordering(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    teams = logged_in.get("/api/leaderboard/teams").json()
    # alice's two sessions both map to team-rocket
    rocket = next(t for t in teams if t["team_id"] == "team-rocket")
    assert rocket["rank"] == 1
    assert rocket["session_count"] == 2
    assert abs(rocket["cost"] - 1.7345) < 1e-6


def test_participant_leaderboard(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    parts = logged_in.get("/api/leaderboard/participants").json()
    assert parts[0]["user_id"] == "alice@example.com"
    assert parts[0]["display_name"] == "Alice"
    assert parts[0]["team_id"] == "team-rocket"


def test_leaderboard_period_today_filters_by_started_at(
    client, payload, auth_headers, logged_in
):
    """period=today restricts to sessions STARTED since local midnight (started_at);
    the default (period=total) keeps the all-time cumulative view.

    Crucially, the filter must use started_at, NOT server_updated_at: an old
    session that was re-ingested today has a fresh server_updated_at but must
    still be excluded from "today". We reproduce exactly that here."""
    from app.db import get_conn, now_utc

    client.post("/ingest", json=payload, headers=auth_headers)
    conn = get_conn()
    # sess-1 ran today; sess-2 is an old session. Both were just ingested, so both
    # carry a "now" server_updated_at — only started_at distinguishes them.
    conn.execute(
        "UPDATE session SET started_at = ? WHERE session_id = 'sess-1'",
        (now_utc(),),
    )
    conn.execute(
        "UPDATE session SET started_at = '2020-01-01T00:00:00+00:00' WHERE session_id = 'sess-2'"
    )
    conn.commit()

    # Default and explicit total see both of alice's sessions.
    total = logged_in.get("/api/leaderboard/participants?period=total").json()
    assert next(p for p in total if p["user_id"] == "alice@example.com")["session_count"] == 2
    default = logged_in.get("/api/leaderboard/participants").json()
    assert next(p for p in default if p["user_id"] == "alice@example.com")["session_count"] == 2

    # Today drops the aged session.
    today = logged_in.get("/api/leaderboard/participants?period=today").json()
    assert next(p for p in today if p["user_id"] == "alice@example.com")["session_count"] == 1

    # Same filtering applies to the teams board (cost shrinks to sess-1 only).
    teams_today = logged_in.get("/api/leaderboard/teams?period=today").json()
    rocket = next(t for t in teams_today if t["team_id"] == "team-rocket")
    assert rocket["session_count"] == 1


def test_leaderboard_period_invalid_falls_back_to_total(
    client, payload, auth_headers, logged_in
):
    """An unknown period value is normalized to the all-time default, never rejected."""
    client.post("/ingest", json=payload, headers=auth_headers)
    bogus = logged_in.get("/api/leaderboard/teams?period=nonsense")
    assert bogus.status_code == 200
    rocket = next(t for t in bogus.json() if t["team_id"] == "team-rocket")
    assert rocket["session_count"] == 2


def test_model_distribution(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    models = logged_in.get("/api/models").json()
    names = {m["model"] for m in models}
    assert "claude-opus-4-8" in names
    assert "claude-sonnet-4-6" in names


def test_tools_breakdown(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    tools = logged_in.get("/api/tools").json()
    by_tool = {t["tool"]: t["count"] for t in tools}
    assert by_tool["Read"] == 14  # 10 + 4
    assert by_tool["Edit"] == 5


def test_provider_split(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    providers = logged_in.get("/api/providers").json()
    assert providers[0]["provider"] == "anthropic"
    assert providers[0]["session_count"] == 2


def test_timeseries_buckets(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    ts = logged_in.get("/api/timeseries?bucket=hour&metric=cost").json()
    assert len(ts) == 2  # sessions started at 08:00 and 09:30 -> 2 hour buckets
    total = sum(b["cost"] for b in ts)
    assert abs(total - 1.7345) < 1e-6


# --- technologies_breakdown -------------------------------------------------


def test_technologies_breakdown_function(client, payload, auth_headers):
    """technologies_breakdown() aggregates language_counts + framework_counts."""
    from app import metrics

    client.post("/ingest", json=payload, headers=auth_headers)
    result = metrics.technologies_breakdown()

    # sess-1 has language_counts {"python": 8, "typescript": 3}
    # sess-2 has no language_counts (defaults to {}), so only sess-1 contributes
    langs = {item["language"]: item["count"] for item in result["languages"]}
    assert langs["python"] == 8
    assert langs["typescript"] == 3

    # sess-1 has framework_counts {"fastapi": 4, "react": 2}
    fws = {item["framework"]: item["count"] for item in result["frameworks"]}
    assert fws["fastapi"] == 4
    assert fws["react"] == 2


def _second_payload_with_overlap(payload):
    """A distinct ingest (different machine_id => distinct session_uid) whose
    session reuses overlapping tech/tooling map keys so cross-session
    summation can be verified."""
    import copy

    p = copy.deepcopy(payload)
    p["source"]["machine_id"] = "laptop-02"
    s = p["sessions"][0]
    s["session_id"] = "sess-3"
    s["language_counts"] = {"python": 5, "go": 2}
    s["framework_counts"] = {"fastapi": 3, "django": 1}
    s["builtin_tool_counts"] = {"Read": 7, "Grep": 4}
    # keep only this one session to keep the assertions focused
    p["sessions"] = [s]
    return p


def test_technologies_tooling_sum_across_sessions(client, payload, auth_headers):
    """Counts for an overlapping key must SUM across distinct sessions."""
    from app import metrics

    client.post("/ingest", json=payload, headers=auth_headers)
    client.post(
        "/ingest", json=_second_payload_with_overlap(payload), headers=auth_headers
    )

    tech = metrics.technologies_breakdown()
    langs = {item["language"]: item["count"] for item in tech["languages"]}
    fws = {item["framework"]: item["count"] for item in tech["frameworks"]}
    # python: 8 (sess-1) + 5 (sess-3) = 13 ; fastapi: 4 + 3 = 7
    assert langs["python"] == 13
    assert langs["go"] == 2  # only sess-3
    assert fws["fastapi"] == 7
    assert fws["django"] == 1

    tooling = metrics.tooling_breakdown()
    builtin = {item["tool"]: item["count"] for item in tooling["builtin"]}
    # Read: 10 (sess-1) + 7 (sess-3) = 17
    assert builtin["Read"] == 17
    assert builtin["Grep"] == 4  # only sess-3


def test_aggregate_json_column_rejects_unknown_column(client, payload, auth_headers):
    """The private helper guards against non-whitelisted column names."""
    import pytest

    from app import metrics
    from app.db import get_conn

    client.post("/ingest", json=payload, headers=auth_headers)
    with pytest.raises(ValueError):
        metrics._aggregate_json_column(get_conn(), "cost")


def test_technologies_breakdown_route(client, payload, auth_headers, logged_in):
    """GET /api/technologies returns the correct structure and values."""
    client.post("/ingest", json=payload, headers=auth_headers)
    resp = logged_in.get("/api/technologies")
    assert resp.status_code == 200
    result = resp.json()
    assert "languages" in result
    assert "frameworks" in result

    langs = {item["language"]: item["count"] for item in result["languages"]}
    fws = {item["framework"]: item["count"] for item in result["frameworks"]}
    assert langs["python"] == 8
    assert fws["fastapi"] == 4


def test_technologies_breakdown_requires_auth(client, payload, auth_headers):
    """GET /api/technologies must reject unauthenticated requests."""
    client.post("/ingest", json=payload, headers=auth_headers)
    resp = client.get("/api/technologies")
    assert resp.status_code in (401, 403)


def test_technologies_breakdown_robust_to_corrupt_json(client, payload, auth_headers):
    """A session with invalid JSON in language_counts must not break the aggregate."""
    from app import metrics
    from app.db import get_conn

    client.post("/ingest", json=payload, headers=auth_headers)
    # Corrupt one session's language_counts directly in the DB
    conn = get_conn()
    conn.execute(
        "UPDATE session SET language_counts = ? WHERE session_id = 'sess-2'",
        ("INVALID_JSON",),
    )
    conn.commit()

    result = metrics.technologies_breakdown()
    langs = {item["language"]: item["count"] for item in result["languages"]}
    # sess-1 still contributes; sess-2 is silently skipped
    assert langs["python"] == 8
    assert langs["typescript"] == 3


# --- tooling_breakdown -------------------------------------------------------


def test_tooling_breakdown_function(client, payload, auth_headers):
    """tooling_breakdown() aggregates all six tool-category columns correctly."""
    from app import metrics

    client.post("/ingest", json=payload, headers=auth_headers)
    result = metrics.tooling_breakdown()

    # All six keys must be present
    for key in ("builtin", "user", "skills", "mcp_servers", "subagents", "slash_commands"):
        assert key in result, f"missing key: {key}"

    # builtin: {"Read": 10, "Edit": 5, "Bash": 3} from sess-1
    builtin = {item["tool"]: item["count"] for item in result["builtin"]}
    assert builtin["Read"] == 10
    assert builtin["Edit"] == 5
    assert builtin["Bash"] == 3

    # user: {"my-custom-tool": 1} from sess-1
    user = {item["tool"]: item["count"] for item in result["user"]}
    assert user["my-custom-tool"] == 1

    # skills: {"deploy-nas": 2, "frontend-design": 1} from sess-1
    skills = {item["tool"]: item["count"] for item in result["skills"]}
    assert skills["deploy-nas"] == 2
    assert skills["frontend-design"] == 1

    # mcp_servers: {"filesystem": 5, "github": 2} from sess-1
    mcp = {item["tool"]: item["count"] for item in result["mcp_servers"]}
    assert mcp["filesystem"] == 5
    assert mcp["github"] == 2

    # subagents: {"general-purpose": 3, "Explore": 1} from sess-1
    subagents = {item["tool"]: item["count"] for item in result["subagents"]}
    assert subagents["general-purpose"] == 3
    assert subagents["Explore"] == 1

    # slash_commands: {"review": 2, "deploy": 1} from sess-1
    slash = {item["tool"]: item["count"] for item in result["slash_commands"]}
    assert slash["review"] == 2
    assert slash["deploy"] == 1


def test_tooling_breakdown_builtin_user_distinct(client, payload, auth_headers):
    """builtin and user tool lists are kept strictly separate (server never reclassifies)."""
    from app import metrics

    client.post("/ingest", json=payload, headers=auth_headers)
    result = metrics.tooling_breakdown()

    builtin_names = {item["tool"] for item in result["builtin"]}
    user_names = {item["tool"] for item in result["user"]}

    # "my-custom-tool" is user-only; standard tools (Read, Edit, Bash) are builtin-only
    assert "my-custom-tool" not in builtin_names
    assert "Read" not in user_names
    assert builtin_names.isdisjoint(user_names), (
        f"builtin/user overlap detected: {builtin_names & user_names}"
    )


def test_tooling_breakdown_route(client, payload, auth_headers, logged_in):
    """GET /api/tooling returns the correct structure."""
    client.post("/ingest", json=payload, headers=auth_headers)
    resp = logged_in.get("/api/tooling")
    assert resp.status_code == 200
    result = resp.json()

    for key in ("builtin", "user", "skills", "mcp_servers", "subagents", "slash_commands"):
        assert key in result
        assert isinstance(result[key], list)

    builtin = {item["tool"]: item["count"] for item in result["builtin"]}
    assert builtin["Read"] == 10
    user = {item["tool"]: item["count"] for item in result["user"]}
    assert user["my-custom-tool"] == 1


def test_tooling_breakdown_requires_auth(client, payload, auth_headers):
    """GET /api/tooling must reject unauthenticated requests."""
    client.post("/ingest", json=payload, headers=auth_headers)
    resp = client.get("/api/tooling")
    assert resp.status_code in (401, 403)
