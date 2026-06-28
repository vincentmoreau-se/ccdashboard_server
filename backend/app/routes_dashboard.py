from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, status

from app import enrichment, metrics
from app.auth import (
    clear_session_cookie,
    is_authenticated,
    require_dashboard,
    set_session_cookie,
    verify_password,
)
from app.config import Settings, get_settings
from app.models import LoginRequest

router = APIRouter()


# --- Auth ---------------------------------------------------------------


@router.post("/api/login")
def login(
    body: LoginRequest,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict:
    if not verify_password(body.password, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password"
        )
    set_session_cookie(response, settings)
    return {"status": "ok"}


@router.post("/api/logout")
def logout(response: Response) -> dict:
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/api/me")
def me(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    return {"authenticated": is_authenticated(request, settings)}


@router.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/api/config")
def config(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "currency": settings.currency,
        "event_name": settings.event_name,
        "live_window_seconds": settings.live_window_seconds,
        "snapshot_interval_seconds": settings.snapshot_interval_seconds,
    }


# --- Historical / read (all require dashboard auth) ---------------------


@router.get("/api/overview", dependencies=[Depends(require_dashboard)])
def overview() -> dict:
    return metrics.overview()


@router.get("/api/timeseries", dependencies=[Depends(require_dashboard)])
def timeseries(bucket: str = "hour", metric: str = "cost") -> list[dict]:
    if bucket not in ("hour", "day"):
        bucket = "hour"
    return metrics.timeseries(bucket=bucket, metric=metric)


def _norm_sort(sort: str) -> str:
    return sort if sort in ("cost", "eval", "volume") else "cost"


@router.get("/api/leaderboard/teams", dependencies=[Depends(require_dashboard)])
def leaderboard_teams(sort: str = "cost") -> list[dict]:
    return metrics.leaderboard_teams(_norm_sort(sort))


@router.get("/api/leaderboard/participants", dependencies=[Depends(require_dashboard)])
def leaderboard_participants(sort: str = "cost") -> list[dict]:
    return metrics.leaderboard_participants(_norm_sort(sort))


@router.get("/api/leaderboard/locations", dependencies=[Depends(require_dashboard)])
def leaderboard_locations(sort: str = "cost") -> list[dict]:
    return metrics.leaderboard_locations(_norm_sort(sort))


@router.get("/api/teams/{team_id}", dependencies=[Depends(require_dashboard)])
def team_detail(team_id: str) -> dict:
    return metrics.team_detail(team_id)


@router.get("/api/models", dependencies=[Depends(require_dashboard)])
def models() -> list[dict]:
    return metrics.model_distribution()


@router.get("/api/providers", dependencies=[Depends(require_dashboard)])
def providers() -> list[dict]:
    return metrics.provider_split()


@router.get("/api/tools", dependencies=[Depends(require_dashboard)])
def tools() -> list[dict]:
    return metrics.tools_breakdown()


@router.get("/api/technologies", dependencies=[Depends(require_dashboard)])
def technologies() -> dict:
    return metrics.technologies_breakdown()


@router.get("/api/tooling", dependencies=[Depends(require_dashboard)])
def tooling() -> dict:
    return metrics.tooling_breakdown()


@router.get("/api/sessions", dependencies=[Depends(require_dashboard)])
def sessions(
    active: bool = False,
    limit: int = 100,
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    return metrics.sessions_list(
        active=active, limit=limit, live_window=settings.live_window_seconds
    )


# --- Admin: CSV reference data ------------------------------------------


@router.get("/api/admin/participants/unknown", dependencies=[Depends(require_dashboard)])
def unknown_participants() -> dict:
    return {"unknown_users": enrichment.unknown_users_in_sessions()}


@router.post("/api/admin/participants", dependencies=[Depends(require_dashboard)])
async def upload_participants(file: UploadFile) -> dict:
    raw = await file.read()
    loaded = enrichment.load_from_text(raw.decode("utf-8-sig"))
    return {
        "loaded": loaded,
        "still_unknown": enrichment.unknown_users_in_sessions(),
    }
