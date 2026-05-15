from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jwt import InvalidTokenError

from config import settings


ALGORITHM = "HS256"
bearer_scheme = HTTPBearer(auto_error=False)


def _jwt_secret() -> str:
    return settings.jwt_secret_key


def _expire_minutes() -> int:
    return settings.jwt_expire_minutes


def create_access_token(claims: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        **claims,
        "iat": now,
        "exp": now + timedelta(minutes=_expire_minutes()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


def verify_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        ) from exc
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )
    return verify_access_token(credentials.credentials)


def verify_google_id_token(credential: str) -> dict[str, Any]:
    client_id = settings.google_client_id
    if not client_id:
        raise RuntimeError("GOOGLE_CLIENT_ID must be configured.")

    return id_token.verify_oauth2_token(
        credential,
        google_requests.Request(),
        client_id,
    )
