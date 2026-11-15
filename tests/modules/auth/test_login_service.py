
import pytest

from app.modules.auth.credential_models import AccountCredential
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.session_models import ClientType
from app.modules.auth.services.login_service import (
    ContactNotVerifiedError,
    InvalidCredentialsError,
    login_with_email,
)
from app.modules.auth.services.password_service import hash_password
from ipaddress import ip_address

def create_verified_customer(db_session, customer_account):
    """Prepare a verified account with a password credential."""

    customer_account.is_email_verified = True

    credential = AccountCredential(
        account_id=customer_account.id,
        password_hash=hash_password("Password123"),
    )

    db_session.add(credential)
    db_session.flush()

    return customer_account


def test_login_with_email_success(
    db_session,
    customer_account,
):
    create_verified_customer(db_session, customer_account)

    login = LoginRequest(
        email=customer_account.email,
        password="Password123",
        client_type=ClientType.MOBILE.value,
    )

    account, access_token, refresh_token = login_with_email(
        db_session,
        login,
        ip_address="127.0.0.1",
        user_agent="FindWorker Test Client",
    )

    assert account.id == customer_account.id
    assert access_token
    assert refresh_token

    from app.modules.auth.session_models import AuthSession

    session = db_session.query(AuthSession).filter_by(
        account_id=customer_account.id
    ).one()

    assert session.client_type == ClientType.MOBILE
    assert session.ip_address == ip_address("127.0.0.1")

def test_login_rejects_incorrect_password(
    db_session,
    customer_account,
):
    create_verified_customer(db_session, customer_account)

    login = LoginRequest(
        email=customer_account.email,
        password="WrongPassword123",
    )

    with pytest.raises(InvalidCredentialsError):
        login_with_email(db_session, login)


def test_login_rejects_unknown_email(db_session):
    login = LoginRequest(
        email="unknown@example.com",
        password="Password123",
    )

    with pytest.raises(InvalidCredentialsError):
        login_with_email(db_session, login)


def test_login_rejects_unverified_account(
    db_session,
    customer_account,
):
    credential = AccountCredential(
        account_id=customer_account.id,
        password_hash=hash_password("Password123"),
    )

    db_session.add(credential)
    db_session.flush()

    login = LoginRequest(
        email=customer_account.email,
        password="Password123",
    )

    with pytest.raises(ContactNotVerifiedError):
        login_with_email(db_session, login)


def test_login_rejects_inactive_account(
    db_session,
    customer_account,
):
    create_verified_customer(db_session, customer_account)
    customer_account.is_active = False

    login = LoginRequest(
        email=customer_account.email,
        password="Password123",
    )

    with pytest.raises(InvalidCredentialsError):
        login_with_email(db_session, login)
