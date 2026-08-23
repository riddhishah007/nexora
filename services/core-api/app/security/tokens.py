import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings
from app.models.user import ROLE_USER

ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


class TokenError(Exception):
    pass


def _create_token(
    claims: dict,
    secret: str,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        **claims,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_access_token(user_id: uuid.UUID, role: str = ROLE_USER) -> tuple[str, int]:
    expires_in = settings.access_token_expire_minutes * 60
    token = _create_token(
        {"sub": str(user_id), "type": TOKEN_TYPE_ACCESS, "role": role},
        settings.jwt_secret,
        timedelta(seconds=expires_in),
    )
    return token, expires_in


def create_refresh_token(
    user_id: uuid.UUID, session_id: uuid.UUID
) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    token = _create_token(
        {
            "sub": str(user_id),
            "sid": str(session_id),
            "type": TOKEN_TYPE_REFRESH,
        },
        settings.refresh_token_secret,
        timedelta(days=settings.refresh_token_expire_days),
    )
    return token, expires_at


def decode_token(token: str, expected_type: str) -> dict:
    secret = (
        settings.refresh_token_secret
        if expected_type == TOKEN_TYPE_REFRESH
        else settings.jwt_secret
    )
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid token") from exc

    if payload.get("type") != expected_type:
        raise TokenError("Unexpected token type")
    return payload


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
