from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _insert_snapshot(conn, ts, scope, tokens, cost, active=0):
    conn.execute(
        "INSERT OR REPLACE INTO agg_snapshot "
        "(ts, scope, total_tokens, total_cost, active_sessions) VALUES (?,?,?,?,?)",
        (ts, scope, tokens, cost, active),
    )
    conn.commit()


def _reset_snapshots(conn):
    # the startup snapshot_loop writes one snapshot at boot; clear it so the
    # rate math is computed only from the rows the test controls.
    conn.execute("DELETE FROM agg_snapshot")
    conn.commit()


def test_rate_from_snapshots(logged_in):
    from app.db import get_conn
    from app.live import _rate_from_snapshots

    conn = get_conn()
    _reset_snapshots(conn)
    t0 = datetime(2026, 6, 28, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=2)
    _insert_snapshot(conn, t0.isoformat(), "global", 1000, 1.0)
    _insert_snapshot(conn, t1.isoformat(), "global", 5000, 3.0)
    rate = _rate_from_snapshots("global", window=3)
    # 4000 tokens over 2 min -> 2000/min ; 2.0 cost over 2 min -> 60.0/hour
    assert rate["tokens_per_min"] == 2000.0
    assert abs(rate["cost_per_hour"] - 60.0) < 1e-6


def test_rate_clamps_negative(logged_in):
    from app.db import get_conn
    from app.live import _rate_from_snapshots

    conn = get_conn()
    _reset_snapshots(conn)
    t0 = datetime(2026, 6, 28, 11, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    # totals decrease (client truncation/restart) -> clamp to 0, never negative
    _insert_snapshot(conn, t0.isoformat(), "global", 9000, 5.0)
    _insert_snapshot(conn, t1.isoformat(), "global", 1000, 1.0)
    rate = _rate_from_snapshots("global", window=2)
    assert rate["tokens_per_min"] == 0.0
    assert rate["cost_per_hour"] == 0.0


def test_rate_warming_up(logged_in):
    from app.live import _rate_from_snapshots

    rate = _rate_from_snapshots("nonexistent-scope")
    assert rate["tokens_per_min"] is None
    assert rate["cost_per_hour"] is None


def test_live_window_excludes_stale(client, payload, auth_headers, logged_in):
    from app.db import get_conn, now_utc

    # sess-1 is active with a fresh server timestamp (just ingested).
    client.post("/ingest", json=payload, headers=auth_headers)

    conn = get_conn()
    # Inject an active session whose server_updated_at is well outside the window.
    stale = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    conn.execute(
        "INSERT INTO session (session_uid, source_key, user_id, session_id, project, "
        "is_active, server_updated_at) VALUES (?,?,?,?,?,1,?)",
        ("zombie::s", "zombie", "bob@example.com", "s", "ghosttown", stale),
    )
    conn.commit()

    snap = logged_in.get("/api/live/snapshot").json()
    # Only the fresh active session (sess-1) counts; the zombie is excluded.
    assert snap["active_sessions"] == 1
    assert snap["active_participants"] == 1


def test_live_snapshot_shape(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    snap = logged_in.get("/api/live/snapshot").json()
    for key in ("active_sessions", "active_participants", "active_teams",
                "tokens_per_min", "cost_per_hour", "top_teams", "models_in_use"):
        assert key in snap
