
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_auth
from app.modules.auth.router import router
from app.modules.auth.session_models import ClientType
from app.modules.auth.services.session_service import create_session
from app.modules.auth.services.token_service import (
    create_access_token,
    create_refresh_token,
)


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app)


def create_test_session(db_session, account, client_type=ClientType.MOBILE):
    refresh_token, jti, token_hash, expires_at = create_refresh_token(
        account.id,
        account.account_type.value,
    )

    session = create_session(
        db=db_session,
        account_id=account.id,
        refresh_token_jti=jti,
        refresh_token_hash=token_hash,
        expires_at=expires_at,
        client_type=client_type,
    )

    access_token = create_access_token(
        account.id,
        account.account_type.value,
        session.id,
    )

    return session, access_token


def test_logout_success(client, db_session, customer_account):
    session, access_token = create_test_session(
        db_session,
        customer_account,
    )

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"

    db_session.refresh(session)
    assert session.revoked_at is not None

    # The same access token must now be rejected.
    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert me_response.status_code == 401


def test_logout_does_not_revoke_other_sessions(
    client,
    db_session,
    customer_account,
):
    first_session, first_token = create_test_session(
        db_session,
        customer_account,
        ClientType.MOBILE,
    )

    second_session, second_token = create_test_session(
        db_session,
        customer_account,
        ClientType.WEB,
    )

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {first_token}"},
    )

    assert response.status_code == 200

    db_session.refresh(first_session)
    db_session.refresh(second_session)

    assert first_session.revoked_at is not None
    assert second_session.revoked_at is None

    second_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert second_response.status_code == 200


def test_logout_requires_authentication(client):
    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 401


def test_logout_all_success(client, db_session, customer_account):
    first_session, first_token = create_test_session(
        db_session,
        customer_account,
        ClientType.MOBILE,
    )

    second_session, second_token = create_test_session(
        db_session,
        customer_account,
        ClientType.WEB,
    )

    response = client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {first_token}"},
    )

    assert response.status_code == 200
    assert response.json()["revoked_sessions"] == 2

    db_session.refresh(first_session)
    db_session.refresh(second_session)

    assert first_session.revoked_at is not None
    assert second_session.revoked_at is not None

    for token in (first_token, second_token):
        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert me_response.status_code == 401


def test_logout_all_requires_authentication(client):
    response = client.post("/api/v1/auth/logout-all")

    assert response.status_code == 401
