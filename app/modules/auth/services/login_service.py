
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.credential_models import AccountCredential
from app.modules.auth.models import Account
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.session_models import ClientType
from app.modules.auth.services.password_service import verify_password
from app.modules.auth.services.session_service import create_session
from app.modules.auth.services.token_service import (
    create_access_token,
    create_refresh_token,
)


class InvalidCredentialsError(Exception):
    """Raised when login credentials are invalid."""


class ContactNotVerifiedError(Exception):
    """Raised when an account has no verified contact method."""


def login_with_email(db: Session, login: LoginRequest, ip_address: str | None = None, user_agent: str | None = None) -> tuple[Account, str, str]:
    """Authenticate using email and password and create a session.

    The caller is responsible for committing or rolling back.
    Returns account, access token, and refresh token.
    """

    email = str(login.email).strip().lower()

    statement = (
        select(Account, AccountCredential)
        .join(
            AccountCredential,
            AccountCredential.account_id == Account.id,
        )
        .where(Account.email == email)
    )

    result = db.execute(statement).one_or_none()

    if result is None:
        raise InvalidCredentialsError("Invalid email or password")

    account, credential = result

    if (
        credential.password_hash is None
        or not verify_password(login.password, credential.password_hash)
    ):
        raise InvalidCredentialsError("Invalid email or password")

    if not account.is_active:
        raise InvalidCredentialsError("Invalid email or password")

    if not (account.is_email_verified or account.is_phone_verified):
        raise ContactNotVerifiedError(
            "Please verify your email address or phone number before logging in"
        )

    (
        refresh_token,
        refresh_token_jti,
        refresh_token_hash,
        refresh_token_expiry,
    ) = create_refresh_token(
        account.id,
        account.account_type.value,
    )

    auth_session = create_session(
        db=db,
        account_id=account.id,
        refresh_token_jti=refresh_token_jti,
        refresh_token_hash=refresh_token_hash,
        expires_at=refresh_token_expiry,
        client_type=ClientType(login.client_type.value),
        ip_address=ip_address,
        user_agent=user_agent,
    )

    access_token = create_access_token(
        account.id,
        account.account_type.value,
        auth_session.id,
    )

    return account, access_token, refresh_token
