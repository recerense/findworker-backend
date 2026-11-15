
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings


def _create_token(account_id: uuid.UUID, account_type: str, token_type: str, expires_delta: timedelta, session_id: uuid.UUID | None = None) -> tuple[str, str, datetime]:
    """Create a signed JWT and return the token, JTI, and expiry."""

    now = datetime.now(timezone.utc)
    expires_at = now + expires_delta
    token_id = str(uuid.uuid4())

    payload: dict[str, Any] = {
        "sub": str(account_id),
        "account_type": account_type,
        "type": token_type,
        "jti": token_id,
        "iat": now,
        "exp": expires_at,
    }

    if session_id is not None:
        payload["sid"] = str(session_id)

    encoded_token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    return encoded_token, token_id, expires_at


def create_access_token(account_id: uuid.UUID, account_type: str, session_id: uuid.UUID) -> str:
    """Create a short-lived access token linked to an auth session."""

    token, _, _ = _create_token(
        account_id=account_id,
        account_type=account_type,
        token_type="access",
        expires_delta=timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        ),
        session_id=session_id,
    )

    return token


def create_refresh_token(account_id: uuid.UUID, account_type: str) -> tuple[str, str, str, datetime]:
    """Create a refresh token and its database storage values."""

    token, token_id, expires_at = _create_token(
        account_id=account_id,
        account_type=account_type,
        token_type="refresh",
        expires_delta=timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        ),
    )

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    return token, token_id, token_hash, expires_at


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT."""

    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={
            "require": ["sub", "type", "jti", "iat", "exp"],
        },
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode an access token and validate its session identifier."""

    payload = decode_token(token)

    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid access token type")

    session_id = payload.get("sid")

    if not isinstance(session_id, str):
        raise jwt.InvalidTokenError("Missing access token session ID")

    try:
        uuid.UUID(session_id)
    except ValueError as exc:
        raise jwt.InvalidTokenError(
            "Invalid access token session ID"
        ) from exc

    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode a refresh token and validate its required claims."""

    payload = decode_token(token)

    if payload.get("type") != "refresh":
        raise jwt.InvalidTokenError("Invalid refresh token type")

    jti = payload.get("jti")

    if not isinstance(jti, str):
        raise jwt.InvalidTokenError("Missing refresh token JTI")

    try:
        uuid.UUID(jti)
    except ValueError as exc:
        raise jwt.InvalidTokenError(
            "Invalid refresh token JTI"
        ) from exc

    try:
        uuid.UUID(payload["sub"])
    except (ValueError, TypeError) as exc:
        raise jwt.InvalidTokenError(
            "Invalid refresh token subject"
        ) from exc

    return payload
