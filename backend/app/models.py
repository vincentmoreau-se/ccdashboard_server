from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Ingest models — mirror the ccdashboard client exporter contract (schema v1).
# extra="ignore" so future client fields never trigger a 422 retry storm.
# ---------------------------------------------------------------------------


class Usage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    input: int = 0
    output: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    cache_read: int = 0
    web_search: int = 0
    web_fetch: int = 0


class SessionIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_id: str
    project: str
    cwd: str | None = None
    file_path: str | None = None
    ai_title: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: float | None = None
    is_active: bool = False
    models: list[str] = Field(default_factory=list)
    provider: str = "anthropic"
    git_branch: str | None = None
    cc_version: str | None = None
    message_count: int = 0
    usage: Usage = Field(default_factory=Usage)
    cost: float = 0.0
    cost_known: bool = True
    tool_counts: dict[str, int] = Field(default_factory=dict)
    skipped_lines: int = 0
    lines_generated: int = 0


class IngestSource(BaseModel):
    model_config = ConfigDict(extra="ignore")
    machine_id: str
    user_id: str
    instance_id: str


class IngestPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_version: int
    source: IngestSource
    sent_at: datetime | None = None
    sessions: list[SessionIn] = Field(default_factory=list)
    # projects[] is a client-side recompute of the same session data — accepted
    # for contract compatibility but intentionally unused (server derives its own).
    projects: list[dict] = Field(default_factory=list)


class IngestResponse(BaseModel):
    status: str = "ok"
    accepted_sessions: int = 0
    unknown_users: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Evaluation ingest — a skill submits a score /100 for a participant (user_id).
# UPSERT on user_id keeps the latest submission.
# ---------------------------------------------------------------------------


class EvalIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_version: int = 1
    user_id: str
    score: float
    max_score: float = 100
    feedback: str | None = None
    evaluated_at: datetime | None = None


class EvalResponse(BaseModel):
    status: str = "ok"
    user_id: str
    known_user: bool = False


# ---------------------------------------------------------------------------
# Dashboard API response models
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    password: str
