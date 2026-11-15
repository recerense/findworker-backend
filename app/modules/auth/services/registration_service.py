
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.credential_models import AccountCredential
from app.modules.auth.models import Account, AccountType
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.services.password_service import hash_password


class RegistrationConflictError(Exception):
    """Raised when an email or phone number is already registered."""


def register_account(db: Session, registration: RegisterRequest) -> Account:
    """Register a customer or worker account.

    The caller is responsible for committing or rolling back
    the database transaction.
    """

    email = (
        str(registration.email).strip().lower()
        if registration.email
        else None
    )

    phone = (
        registration.phone.strip()
        if registration.phone
        else None
    )

    if email is None and phone is None:
        raise ValueError("Email or phone number is required")

    # Check global email uniqueness across Customer and Worker accounts.
    if email:
        existing_email = db.execute(
            select(Account.id).where(
                Account.email == email
            )
        ).scalar_one_or_none()

        if existing_email is not None:
            raise RegistrationConflictError(
                "Email address is already registered"
            )

    # Check global phone uniqueness across Customer and Worker accounts.
    if phone:
        existing_phone = db.execute(
            select(Account.id).where(
                Account.phone == phone
            )
        ).scalar_one_or_none()

        if existing_phone is not None:
            raise RegistrationConflictError(
                "Phone number is already registered"
            )

    account_type = AccountType(registration.account_type.value)

    account = Account(
        account_type=account_type,
        email=email,
        phone=phone,
        is_active=True,
        is_email_verified=False,
        is_phone_verified=False,
    )

    db.add(account)
    db.flush()

    # Create credentials only when a password is supplied.
    if registration.password:
        credential = AccountCredential(
            account_id=account.id,
            password_hash=hash_password(registration.password),
        )

        db.add(credential)
        db.flush()

    return account
