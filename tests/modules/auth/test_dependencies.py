
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.modules.auth.dependencies import get_current_auth
from app.modules.auth.session_models import ClientType
from app.modules.auth.services.session_service import create_session
from app.modules.auth.services.token_service import (
    create_access_token,
    create_refresh_token,
)


def create_test_credentials(
    db_session,
    customer_account,
    client_type=ClientType.MOBILE,
):
    (
        refresh_token,
        refresh_token_jti,
        refresh_token_hash,
        expires_at,
    ) = create_refresh_token(
        customer_account.id,
        customer_account.account_type.value,
    )

    session = create_session(
        db=db_session,
        account_id=customer_account.id,
        refresh_token_jti=refresh_token_jti,
        refresh_token_hash=refresh_token_hash,
        expires_at=expires_at,
        client_type=client_type,
    )

    access_token = create_access_token(
        customer_account.id,
        customer_account.account_type.value,
        session.id,
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=access_token,
    )

    return session, credentials


def test_get_current_auth_success(
    db_session,
    customer_account,
):
    session, credentials = create_test_credentials(
        db_session,
        customer_account,
    )

    account, authenticated_session = get_current_auth(
        credentials=credentials,
        db=db_session,
    )

    assert account.id == customer_account.id
    assert authenticated_session.id == session.id


def test_get_current_auth_rejects_missing_credentials(db_session):
    with pytest.raises(HTTPException) as exc_info:
        get_current_auth(
            credentials=None,
            db=db_session,
        )

    assert exc_info.value.status_code == 401


def test_get_current_auth_rejects_invalid_token(db_session):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid.token.value",
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_auth(
            credentials=credentials,
            db=db_session,
        )

    assert exc_info.value.status_code == 401


def test_get_current_auth_rejects_revoked_session(
    db_session,
    customer_account,
):
    session, credentials = create_test_credentials(
        db_session,
        customer_account,
    )

    session.revoked_at = datetime.now(timezone.utc)
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        get_current_auth(
            credentials=credentials,
            db=db_session,
        )

    assert exc_info.value.status_code == 401


def test_get_current_auth_rejects_inactive_account(
    db_session,
    customer_account,
):
    _, credentials = create_test_credentials(
        db_session,
        customer_account,
    )

    customer_account.is_active = False
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        get_current_auth(
            credentials=credentials,
            db=db_session,
        )

    assert exc_info.value.status_code == 401


def test_get_current_auth_rejects_expired_session(
    db_session,
    customer_account,
):
    (
        refresh_token,
        refresh_token_jti,
        refresh_token_hash,
        _,
    ) = create_refresh_token(
        customer_account.id,
        customer_account.account_type.value,
    )

    session = create_session(
        db=db_session,
        account_id=customer_account.id,
        refresh_token_jti=refresh_token_jti,
        refresh_token_hash=refresh_token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    access_token = create_access_token(
        customer_account.id,
        customer_account.account_type.value,
        session.id,
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=access_token,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_auth(credentials=credentials, db=db_session)

    assert exc_info.value.status_code == 401


def test_get_current_auth_rejects_account_type_mismatch(
    db_session,
    customer_account,
):
    session, _ = create_test_credentials(
        db_session,
        customer_account,
    )

    # The JWT is validly signed, but its account type is incorrect.
    access_token = create_access_token(
        customer_account.id,
        "WORKER",
        session.id,
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=access_token,
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_auth(credentials=credentials, db=db_session)

    assert exc_info.value.status_code == 401
