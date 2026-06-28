from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "payload.json"

INGEST_TOKEN = "test-ingest-token"
DASHBOARD_PASSWORD = "test-password"


@pytest.fixture
def settings_env(tmp_path, monkeypatch):
    """Point the app at a fresh temp DB + CSV and known secrets."""
    db_path = tmp_path / "test.db"
    csv_path = tmp_path / "participants.csv"
    csv_path.write_text(
        "user_id,team_id,localisation,display_name\n"
        "alice@example.com,team-rocket,Room A,Alice\n"
        "bob@example.com,team-rocket,Room A,Bob\n"
        "carol@example.com,team-data,Room B,Carol\n"
    )
    monkeypatch.setenv("CCSRV_DB_PATH", str(db_path))
    monkeypatch.setenv("CCSRV_PARTICIPANTS_CSV", str(csv_path))
    monkeypatch.setenv("CCSRV_INGEST_TOKEN", INGEST_TOKEN)
    monkeypatch.setenv("CCSRV_DASHBOARD_PASSWORD", DASHBOARD_PASSWORD)
    monkeypatch.setenv("CCSRV_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("CCSRV_LIVE_WINDOW_SECONDS", "120")

    from app.config import get_settings

    get_settings.cache_clear()
    yield {"db_path": db_path, "csv_path": csv_path}
    get_settings.cache_clear()


@pytest.fixture
def client(settings_env):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def payload():
    return copy.deepcopy(json.loads(FIXTURE.read_text()))


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {INGEST_TOKEN}"}


@pytest.fixture
def logged_in(client):
    """A client with a valid dashboard session cookie."""
    resp = client.post("/api/login", json={"password": DASHBOARD_PASSWORD})
    assert resp.status_code == 200
    return client
