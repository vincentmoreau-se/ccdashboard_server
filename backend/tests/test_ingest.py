from __future__ import annotations


def _count_sessions(client, logged_in_token=None):
    # use the DB directly via the metrics overview endpoint after login
    pass


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
