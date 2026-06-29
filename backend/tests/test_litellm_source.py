from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

# The LiteLLM key hash == the digest part of the ccdashboard user_id.
TOKEN = hashlib.sha256(b"sk-user-key").hexdigest()
USER = f"key:{TOKEN}"


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _FakeClient:
    """Stands in for httpx.Client, routing by endpoint."""

    def __init__(self, daily, keys):
        self._daily = daily
        self._keys = keys

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, params=None):
        if url.endswith("/user/daily/activity"):
            return _FakeResp({"results": self._daily, "metadata": {"total_pages": 1}})
        if url.endswith("/key/list"):
            return _FakeResp({"keys": self._keys})
        raise AssertionError(f"unexpected url {url}")


def _daily(date: str) -> dict:
    return {
        "date": date,
        "metrics": {},
        "breakdown": {
            "models": {
                "claude-sonnet-4-6": {
                    "api_key_breakdown": {
                        TOKEN: {
                            "metrics": {
                                "spend": 4.5,
                                # LiteLLM prompt_tokens follows the OpenAI convention:
                                # it INCLUDES cache (1000 real input + 5000 read + 300
                                # creation). The poller strips cache back out so
                                # in_tokens == non-cached input (1000).
                                "prompt_tokens": 6300,
                                "completion_tokens": 200,
                                "cache_read_input_tokens": 5000,
                                "cache_creation_input_tokens": 300,
                                "api_requests": 12,
                            },
                            "metadata": {"key_alias": "x@example.com"},
                        }
                    }
                }
            }
        },
    }


@pytest.fixture
def litellm_env(settings_env, monkeypatch):
    """settings_env + LiteLLM config, with the DB opened (no HTTP server)."""
    monkeypatch.setenv("CCSRV_LITELLM_ENABLED", "true")
    monkeypatch.setenv("CCSRV_LITELLM_MASTER_KEY", "sk-master")
    monkeypatch.setenv("CCSRV_LITELLM_BASE_URL", "http://litellm:4000")

    from app.config import get_settings

    get_settings.cache_clear()
    from app.db import init_db

    init_db(str(settings_env["db_path"]))
    yield settings_env
    get_settings.cache_clear()


def _patch_http(monkeypatch, daily, keys):
    import app.litellm_source as mod

    monkeypatch.setattr(mod.httpx, "Client", lambda *a, **k: _FakeClient(daily, keys))
    return mod


def test_poll_writes_litellm_session(litellm_env, monkeypatch):
    today = datetime.now(timezone.utc).date().isoformat()
    mod = _patch_http(
        monkeypatch,
        [_daily(today)],
        [{"token": TOKEN, "last_active": datetime.now(timezone.utc).isoformat()}],
    )

    assert mod.poll_once() == 1

    row = mod.get_conn().execute(
        "SELECT * FROM session WHERE user_id=?", (USER,)
    ).fetchone()
    assert row["data_source"] == "litellm"
    assert row["session_id"] == f"litellm:{today}"
    assert row["in_tokens"] == 1000  # prompt_tokens (6300) minus cache (5000+300)
    assert row["out_tokens"] == 200
    # Invariant: the displayed token total (in+out) excludes cache, same as the
    # ccdashboard source — cache stays in its own columns.
    assert row["in_tokens"] + row["out_tokens"] == 1200
    assert row["cache_read"] == 5000
    assert row["cache_write_5m"] == 300
    assert row["message_count"] == 12
    assert abs(row["cost"] - 4.5) < 1e-6
    assert row["is_active"] == 1  # last_active is recent and date == today


def test_poll_skips_and_purges_ccdashboard_covered_day(litellm_env, monkeypatch):
    from app.ingest import persist_sessions
    from app.models import SessionIn

    today = datetime.now(timezone.utc).date().isoformat()

    # First poll: no ccdashboard coverage -> LiteLLM row written.
    mod = _patch_http(monkeypatch, [_daily(today)], [])
    assert mod.poll_once() == 1
    assert _litellm_count(mod) == 1

    # ccdashboard now reports activity for the same user/day...
    persist_sessions(
        f"laptop|{USER}|default",
        "laptop",
        USER,
        "default",
        [SessionIn(session_id="cc-1", project="proj", started_at=f"{today}T08:00:00+00:00")],
        data_source="ccdashboard",
    )

    # ...so the next poll skips that day and purges the stale LiteLLM row.
    assert mod.poll_once() == 0
    assert _litellm_count(mod) == 0


def test_poll_noop_without_master_key(settings_env, monkeypatch):
    monkeypatch.setenv("CCSRV_LITELLM_MASTER_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.db import init_db

    init_db(str(settings_env["db_path"]))
    import app.litellm_source as mod

    assert mod.poll_once() == 0
    get_settings.cache_clear()


def _litellm_count(mod) -> int:
    return mod.get_conn().execute(
        "SELECT COUNT(*) AS c FROM session WHERE data_source='litellm'"
    ).fetchone()["c"]
