from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings, get_settings

SESSION_COOKIE = "ccsrv_session"


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="ccsrv-dashboard")


# --- Ingest auth: shared bearer token ------------------------------------


def require_ingest_token(
    request: Request, settings: Settings = Depends(get_settings)
) -> None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    if not hmac.compare_digest(token, settings.ingest_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ingest token",
        )


# --- Dashboard auth: shared password -> signed session cookie -------------


def verify_password(password: str, settings: Settings) -> bool:
    return hmac.compare_digest(password, settings.dashboard_password)


def set_session_cookie(response: Response, settings: Settings) -> None:
    token = _serializer(settings).dumps("dashboard")
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def is_authenticated(request: Request, settings: Settings) -> bool:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False
    try:
        _serializer(settings).loads(
            token, max_age=settings.session_max_age_seconds
        )
        return True
    except (BadSignature, SignatureExpired):
        return False


def require_dashboard(
    request: Request, settings: Settings = Depends(get_settings)
) -> None:
    if not is_authenticated(request, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
