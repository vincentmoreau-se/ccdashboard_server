from __future__ import annotations

from tests.conftest import DASHBOARD_PASSWORD


def test_ingest_requires_bearer(client, payload):
    assert client.post("/ingest", json=payload).status_code == 401


def test_ingest_wrong_bearer(client, payload):
    resp = client.post(
        "/ingest", json=payload, headers={"Authorization": "Bearer nope"}
    )
    assert resp.status_code == 401


def test_login_wrong_password(client):
    assert client.post("/api/login", json={"password": "bad"}).status_code == 401


def test_login_sets_cookie_and_me(client):
    assert client.get("/api/me").json()["authenticated"] is False
    resp = client.post("/api/login", json={"password": DASHBOARD_PASSWORD})
    assert resp.status_code == 200
    assert client.get("/api/me").json()["authenticated"] is True


def test_protected_endpoint_requires_cookie(client):
    assert client.get("/api/overview").status_code == 401


def test_protected_endpoint_with_cookie(logged_in):
    assert logged_in.get("/api/overview").status_code == 200


def test_logout_clears_session(logged_in):
    assert logged_in.get("/api/me").json()["authenticated"] is True
    logged_in.post("/api/logout")
    assert logged_in.get("/api/me").json()["authenticated"] is False


def test_health_no_auth(client):
    assert client.get("/api/health").json()["status"] == "ok"
