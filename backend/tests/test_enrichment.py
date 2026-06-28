from __future__ import annotations

import io


def test_known_user_enriched_to_team(client, payload, auth_headers, logged_in):
    client.post("/ingest", json=payload, headers=auth_headers)
    teams = logged_in.get("/api/leaderboard/teams").json()
    team_ids = {t["team_id"] for t in teams}
    assert "team-rocket" in team_ids
    assert "UNKNOWN" not in team_ids  # alice is mapped


def test_unknown_user_goes_to_unknown_bucket(client, payload, auth_headers, logged_in):
    payload["source"]["user_id"] = "ghost@example.com"
    client.post("/ingest", json=payload, headers=auth_headers)
    teams = logged_in.get("/api/leaderboard/teams").json()
    assert "UNKNOWN" in {t["team_id"] for t in teams}
    unknown = logged_in.get("/api/admin/participants/unknown").json()
    assert "ghost@example.com" in unknown["unknown_users"]


def test_admin_reupload_rebuckets_history(client, payload, auth_headers, logged_in):
    payload["source"]["user_id"] = "ghost@example.com"
    client.post("/ingest", json=payload, headers=auth_headers)
    # ghost starts UNKNOWN
    teams = logged_in.get("/api/leaderboard/teams").json()
    assert "UNKNOWN" in {t["team_id"] for t in teams}

    csv = (
        "user_id,team_id,localisation,display_name\n"
        "ghost@example.com,team-spectre,Room Z,Ghost\n"
    )
    resp = logged_in.post(
        "/api/admin/participants",
        files={"file": ("p.csv", io.BytesIO(csv.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    # Historical sessions instantly re-bucketed via query-time join.
    teams = logged_in.get("/api/leaderboard/teams").json()
    assert "team-spectre" in {t["team_id"] for t in teams}
