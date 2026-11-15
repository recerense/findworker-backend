
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.auth.session_models import ClientType
from app.modules.auth.services.session_service import (
    create_session,
    get_active_session,
    revoke_all_sessions,
    revoke_session,
    rotate_refresh_token,
)
from app.modules.auth.services.token_service import create_refresh_token, decode_token


@pytest.mark.parametrize(
    "client_type",
    [
        ClientType.MOBILE,
        ClientType.WEB,
        ClientType.CAPACITOR,
        ClientType.API,
    ],
)
def test_create_session_with_client_type(
    db_session,
    customer_account,
    client_type,
):
    """A session should persist its specified client type."""

    refresh_token = str(uuid.uuid4())

    session = create_session(
        db=db_session,
        account_id=customer_account.id,
        refresh_token_jti=str(uuid.uuid4()),
        refresh_token_hash=hashlib.sha256(
            refresh_token.encode("utf-8")
        ).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        client_type=client_type,
    )

    db_session.refresh(session)

    assert session.account_id == customer_account.id
    assert session.client_type == client_type


def test_create_session_defaults_to_mobile(
    db_session,
    customer_account,
):
    """A session should default to MOBILE when no client type is supplied."""

    refresh_token = str(uuid.uuid4())

    session = create_session(
        db=db_session,
        account_id=customer_account.id,
        refresh_token_jti=str(uuid.uuid4()),
        refresh_token_hash=hashlib.sha256(
            refresh_token.encode("utf-8")
        ).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    db_session.refresh(session)

    assert session.client_type == ClientType.MOBILE


@pytest.mark.parametrize(
    "client_type",
    [
        ClientType.MOBILE,
        ClientType.WEB,
        ClientType.CAPACITOR,
        ClientType.API,
    ],
)
def test_rotate_refresh_token_preserves_client_type(
    db_session,
    customer_account,
    client_type,
):
    """Refresh-token rotation should preserve the original client type."""

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

    result = rotate_refresh_token(
        db_session,
        refresh_token,
        refresh_token_jti,
    )

    assert result is not None

    rotated_session, new_refresh_token = result

    assert rotated_session.id == session.id
    assert rotated_session.client_type == client_type
    assert rotated_session.refresh_token_jti != refresh_token_jti
    assert new_refresh_token != refresh_token

    new_token_payload = decode_token(new_refresh_token)

    assert new_token_payload["type"] == "refresh"
    assert new_token_payload["sub"] == str(customer_account.id)


def test_old_refresh_token_cannot_be_reused(
    db_session,
    customer_account,
):
    """A refresh token must not work again after successful rotation."""

    (
        refresh_token,
        refresh_token_jti,
        refresh_token_hash,
        expires_at,
    ) = create_refresh_token(
        customer_account.id,
        customer_account.account_type.value,
    )

    create_session(
        db=db_session,
        account_id=customer_account.id,
        refresh_token_jti=refresh_token_jti,
        refresh_token_hash=refresh_token_hash,
        expires_at=expires_at,
        client_type=ClientType.MOBILE,
    )

    first_rotation = rotate_refresh_token(
        db_session,
        refresh_token,
        refresh_token_jti,
    )

    assert first_rotation is not None

    _, new_refresh_token = first_rotation

    second_rotation = rotate_refresh_token(
        db_session,
        refresh_token,
        refresh_token_jti,
    )

    assert second_rotation is None

    new_token_payload = decode_token(new_refresh_token)
    assert new_token_payload["type"] == "refresh"


def test_revoke_session_does_not_affect_other_sessions(
    db_session,
    customer_account,
):
    """Revoking one device session should leave other sessions active."""

    sessions = []

    for client_type in (ClientType.MOBILE, ClientType.WEB):
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
        sessions.append((session, refresh_token))

    mobile_session = sessions[0][0]
    web_session = sessions[1][0]

    assert revoke_session(
        db_session,
        mobile_session.refresh_token_jti,
    ) is True

    assert get_active_session(
        db_session,
        mobile_session.refresh_token_jti,
    ) is None

    assert get_active_session(
        db_session,
        web_session.refresh_token_jti,
    ) is not None


def test_revoke_all_sessions(
    db_session,
    customer_account,
):
    """Revoking all sessions should invalidate every active session."""

    refresh_token_jtis = []

    for client_type in (
        ClientType.MOBILE,
        ClientType.WEB,
        ClientType.API,
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

        create_session(
            db=db_session,
            account_id=customer_account.id,
            refresh_token_jti=refresh_token_jti,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            client_type=client_type,
        )

        refresh_token_jtis.append(refresh_token_jti)

    revoked_count = revoke_all_sessions(
        db_session,
        customer_account.id,
    )

    assert revoked_count == 3

    for refresh_token_jti in refresh_token_jtis:
        assert get_active_session(
            db_session,
            refresh_token_jti,
        ) is None
