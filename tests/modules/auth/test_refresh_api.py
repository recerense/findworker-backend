
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.modules.auth.router import router
from app.modules.auth.session_models import AuthSession, ClientType
from app.modules.auth.services.session_service import create_session
from app.modules.auth.services.token_service import create_refresh_token


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app)


@pytest.fixture
def refresh_credentials(db_session, customer_account):
    refresh_token, jti, token_hash, expires_at = create_refresh_token(
        customer_account.id,
        customer_account.account_type.value,
    )

    session = create_session(
        db=db_session,
        account_id=customer_account.id,
        refresh_token_jti=jti,
        refresh_token_hash=token_hash,
        expires_at=expires_at,
        client_type=ClientType.MOBILE,
    )

    return refresh_token, session


def test_refresh_token_success(
    client,
    db_session,
    refresh_credentials,
    customer_account,
):
    old_refresh_token, session = refresh_credentials

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["access_token"]
    assert data["refresh_token"]
    assert data["refresh_token"] != old_refresh_token
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0

    db_session.refresh(session)

    assert session.revoked_at is None
    assert session.last_used_at is not None

    # The session ID remains unchanged during rotation.
    assert session.account_id == customer_account.id


def test_refresh_rejects_reused_old_token(
    client,
    refresh_credentials,
):
    old_refresh_token, _ = refresh_credentials

    first_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert first_response.status_code == 200

    second_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert second_response.status_code == 401


def test_refresh_rejects_invalid_token(client):
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid.token.value"},
    )

    assert response.status_code == 401


def test_refresh_rejects_expired_token(
    client,
    db_session,
    customer_account,
):
    refresh_token, jti, token_hash, _ = create_refresh_token(
        customer_account.id,
        customer_account.account_type.value,
    )

    # Create a validly signed but already expired refresh token.
    import jwt
    from app.core.config import settings

    now = datetime.now(timezone.utc)

    expired_token = jwt.encode(
        {
            "sub": str(customer_account.id),
            "account_type": customer_account.account_type.value,
            "type": "refresh",
            "jti": str(uuid.uuid4()),
            "iat": now - timedelta(days=2),
            "exp": now - timedelta(days=1),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": expired_token},
    )

    assert response.status_code == 401


def test_refresh_rejects_inactive_account(
    client,
    db_session,
    refresh_credentials,
    customer_account,
):
    refresh_token, session = refresh_credentials

    customer_account.is_active = False
    db_session.flush()

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 401

    db_session.refresh(session)

    assert session.revoked_at is not None
