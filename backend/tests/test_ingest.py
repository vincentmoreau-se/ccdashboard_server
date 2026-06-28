from __future__ import annotations

import json


def test_ingest_happy_path(client, payload, auth_headers):
    resp = client.post("/ingest", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["accepted_sessions"] == 2
    assert body["unknown_users"] == []  # alice is in the CSV


def test_ingest_idempotent_resend(client, payload, auth_headers, logged_in):
    # Send the same payload 3 times -> exactly 2 session rows, totals unchanged.
    for _ in range(3):
        assert client.post("/ingest", json=payload, headers=auth_headers).status_code == 200
    ov = logged_in.get("/api/overview").json()
    assert ov["session_count"] == 2
    # total cost = 1.2345 + 0.5 (not summed 3x)
    assert abs(ov["total_cost"] - 1.7345) < 1e-6


def test_ingest_incremental_overwrite(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    # Re-send sess-1 with more tokens + later ended_at -> overwrite, not add.
    one = {
        "schema_version": 1,
        "source": payload["source"],
        "sent_at": "2026-06-28T10:05:00+00:00",
        "sessions": [{**payload["sessions"][0], "cost": 2.0,
                      "ended_at": "2026-06-28T10:04:00+00:00",
                      "message_count": 99}],
        "projects": [],
    }
    assert client.post("/ingest", json=one, headers=auth_headers).status_code == 200
    ov = logged_in.get("/api/overview").json()
    assert ov["session_count"] == 2  # still 2 sessions
    # cost = 2.0 (overwritten sess-1) + 0.5 (sess-2), not 1.2345+2.0+0.5
    assert abs(ov["total_cost"] - 2.5) < 1e-6


def test_ingest_dedup_across_machines(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    # Same session_id from a different machine -> distinct row.
    other = {
        "schema_version": 1,
        "source": {"machine_id": "laptop-02", "user_id": "alice@example.com",
                   "instance_id": "default"},
        "sent_at": "2026-06-28T10:00:00+00:00",
        "sessions": [payload["sessions"][0]],  # same session_id "sess-1"
        "projects": [],
    }
    assert client.post("/ingest", json=other, headers=auth_headers).status_code == 200
    ov = logged_in.get("/api/overview").json()
    assert ov["session_count"] == 3  # 2 + 1 distinct (sess-1 from a 2nd machine)


def test_ingest_unknown_user_bucket(client, payload, auth_headers):
    payload["source"]["user_id"] = "ghost@example.com"
    resp = client.post("/ingest", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["unknown_users"] == ["ghost@example.com"]


def test_ingest_unsupported_schema_version(client, payload, auth_headers):
    payload["schema_version"] = 2
    resp = client.post("/ingest", json=payload, headers=auth_headers)
    assert resp.status_code == 422


def test_ingest_malformed_body(client, auth_headers):
    resp = client.post("/ingest", json={"nonsense": True}, headers=auth_headers)
    assert resp.status_code == 422


def test_ingest_tech_tooling_maps_round_trip(client, payload, auth_headers, settings_env):
    """8 aggregate maps in the payload are persisted and readable from the DB."""
    # sess-1 in the fixture already carries all 8 maps
    resp = client.post("/ingest", json=payload, headers=auth_headers)
    assert resp.status_code == 200

    import sqlite3

    conn = sqlite3.connect(str(settings_env["db_path"]))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM session WHERE session_id = ?", ("sess-1",)
    ).fetchone()
    conn.close()

    assert json.loads(row["language_counts"]) == {"python": 8, "typescript": 3}
    assert json.loads(row["framework_counts"]) == {"fastapi": 4, "react": 2}
    assert json.loads(row["builtin_tool_counts"]) == {"Read": 10, "Edit": 5, "Bash": 3}
    assert json.loads(row["user_tool_counts"]) == {"my-custom-tool": 1}
    assert json.loads(row["skill_counts"]) == {"deploy-nas": 2, "frontend-design": 1}
    assert json.loads(row["mcp_server_counts"]) == {"filesystem": 5, "github": 2}
    assert json.loads(row["subagent_counts"]) == {"general-purpose": 3, "Explore": 1}
    assert json.loads(row["slash_command_counts"]) == {"review": 2, "deploy": 1}


def test_ingest_tech_tooling_maps_backward_compat(client, auth_headers, settings_env):
    """Payload without the 8 new maps is accepted; columns default to {}."""
    minimal_payload = {
        "schema_version": 1,
        "source": {
            "machine_id": "laptop-old",
            "user_id": "alice@example.com",
            "instance_id": "default",
        },
        "sent_at": "2026-06-28T10:00:00+00:00",
        "sessions": [
            {
                "session_id": "sess-old",
                "project": "legacy-project",
                "message_count": 5,
                "usage": {
                    "input": 1000,
                    "output": 500,
                    "cache_write_5m": 0,
                    "cache_write_1h": 0,
                    "cache_read": 0,
                    "web_search": 0,
                    "web_fetch": 0,
                },
                "cost": 0.01,
                "cost_known": True,
                "tool_counts": {},
                # no language_counts, framework_counts, etc.
            }
        ],
        "projects": [],
    }
    resp = client.post("/ingest", json=minimal_payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["accepted_sessions"] == 1

    import sqlite3

    conn = sqlite3.connect(str(settings_env["db_path"]))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM session WHERE session_id = ?", ("sess-old",)
    ).fetchone()
    conn.close()

    for col in (
        "language_counts",
        "framework_counts",
        "builtin_tool_counts",
        "user_tool_counts",
        "skill_counts",
        "mcp_server_counts",
        "subagent_counts",
        "slash_command_counts",
    ):
        assert json.loads(row[col]) == {}, f"{col} should default to {{}}"
