
import uuid

import jwt
import pytest

from app.modules.auth.services.token_service import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
)


def test_access_token_contains_session_id():
    account_id = uuid.uuid4()
    session_id = uuid.uuid4()

    token = create_access_token(
        account_id,
        "CUSTOMER",
        session_id,
    )

    payload = decode_access_token(token)

    assert payload["sub"] == str(account_id)
    assert payload["sid"] == str(session_id)
    assert payload["type"] == "access"


def test_access_token_rejects_refresh_token():
    account_id = uuid.uuid4()

    refresh_token, _, _, _ = create_refresh_token(
        account_id,
        "CUSTOMER",
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(refresh_token)


def test_access_token_rejects_token_without_session_id():
    account_id = uuid.uuid4()

    # Create a token without a session ID.
    from app.modules.auth.services.token_service import _create_token
    from datetime import timedelta

    token, _, _ = _create_token(
        account_id=account_id,
        account_type="CUSTOMER",
        token_type="access",
        expires_delta=timedelta(minutes=15),
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)
