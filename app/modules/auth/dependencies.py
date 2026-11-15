
import uuid
from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.models import Account
from app.modules.auth.session_models import AuthSession
from app.modules.auth.services.token_service import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme), db: Session = Depends(get_db)) -> tuple[Account, AuthSession]:
    """Authenticate a request and validate its active database session."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)

        account_id = uuid.UUID(payload["sub"])
        session_id = uuid.UUID(payload["sid"])

    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise unauthorized from None

    statement = (
        select(Account, AuthSession)
        .join(
            AuthSession,
            AuthSession.account_id == Account.id,
        )
        .where(
            Account.id == account_id,
            AuthSession.id == session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(timezone.utc),
        )
    )

    result = db.execute(statement).one_or_none()

    if result is None:
        raise unauthorized

    account, auth_session = result

    if not account.is_active:
        raise unauthorized

    if payload.get("account_type") != account.account_type.value:
        raise unauthorized

    return account, auth_session
