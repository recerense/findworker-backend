
import pytest
import secrets

from app.modules.auth.credential_models import AccountCredential
from app.modules.auth.models import AccountType
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.services.password_service import verify_password
from app.modules.auth.services.registration_service import (
    RegistrationConflictError,
    register_account,
)


def generate_test_phone():
    """Generate a unique, valid-format Indian mobile number."""
    first_digit = secrets.choice("6789")
    remaining_digits = secrets.randbelow(10**9)
    return f"+91{first_digit}{remaining_digits:09d}"


def test_register_customer_with_email_and_password(db_session):
    registration = RegisterRequest(
        account_type="CUSTOMER",
        email="customer@example.com",
        password="Password123",
    )

    account = register_account(db_session, registration)

    assert account.account_type == AccountType.CUSTOMER
    assert account.email == "customer@example.com"
    assert account.phone is None
    assert account.is_email_verified is False


def test_register_worker_with_email_and_password(db_session):
    registration = RegisterRequest(
        account_type="WORKER",
        email="worker@example.com",
        password="Password123",
    )

    account = register_account(db_session, registration)

    assert account.account_type == AccountType.WORKER
    assert account.email == "worker@example.com"


def test_register_with_phone_only(db_session):
    phone = generate_test_phone()

    registration = RegisterRequest(
        account_type="CUSTOMER",
        phone=phone,
    )

    account = register_account(db_session, registration)

    assert account.phone == phone
    assert account.email is None

    credential = db_session.query(AccountCredential).filter_by(
        account_id=account.id
    ).one_or_none()

    assert credential is None
    assert account.is_phone_verified is False


def test_duplicate_email_rejected_across_account_types(db_session):
    first = register_account(
        db_session,
        RegisterRequest(
            account_type="CUSTOMER",
            email="duplicate@example.com",
            password="Password123",
        ),
    )

    with pytest.raises(RegistrationConflictError):
        register_account(
            db_session,
            RegisterRequest(
                account_type="WORKER",
                email="duplicate@example.com",
                password="Password123",
            ),
        )

    assert first.account_type == AccountType.CUSTOMER


def test_duplicate_phone_rejected_across_account_types(db_session):
    phone = generate_test_phone()

    register_account(
        db_session,
        RegisterRequest(
            account_type="CUSTOMER",
            phone=phone,
        ),
    )

    with pytest.raises(RegistrationConflictError):
        register_account(
            db_session,
            RegisterRequest(
                account_type="WORKER",
                phone=phone,
            ),
        )


def test_password_is_hashed(db_session):
    password = "Password123"

    account = register_account(
        db_session,
        RegisterRequest(
            account_type="CUSTOMER",
            email="hash@example.com",
            password=password,
        ),
    )

    credential = db_session.query(AccountCredential).filter_by(
        account_id=account.id
    ).one()

    assert credential.password_hash != password
    assert verify_password(password, credential.password_hash)


def test_new_account_contacts_are_unverified(db_session):
    account = register_account(
        db_session,
        RegisterRequest(
            account_type="CUSTOMER",
            email="unverified@example.com",
            phone=generate_test_phone(),
            password="Password123",
        ),
    )

    assert account.is_email_verified is False
    assert account.is_phone_verified is False
    assert account.is_active is True
