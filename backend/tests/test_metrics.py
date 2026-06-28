from __future__ import annotations


def test_overview_totals(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    ov = logged_in.get("/api/overview").json()
    assert ov["session_count"] == 2
    assert ov["participant_count"] == 1
    # tokens = sum of input+output+cache for both sessions
    # sess-1: 12000+8000+3000+0+50000 = 73000 ; sess-2: 5000+3000+1000+0+10000 = 19000
    assert ov["total_tokens"] == 92000
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
