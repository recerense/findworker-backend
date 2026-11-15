
import uuid

import pytest
from sqlalchemy.orm import Session

from app.db.session import engine
from app.modules.auth.models import Account, AccountType


@pytest.fixture
def db_session():
    """Provide a database session isolated by an outer transaction."""

    connection = engine.connect()
    transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def customer_account(db_session: Session) -> Account:
    """Create a customer account for authentication tests."""

    account = Account(
        account_type=AccountType.CUSTOMER,
        email=f"{uuid.uuid4()}@example.com",
    )

    db_session.add(account)
    db_session.flush()

    return account
