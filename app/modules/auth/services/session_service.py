
import uuid
from datetime import datetime, timezone
import hashlib
import hmac

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.session_models import AuthSession, ClientType
from app.modules.auth.services.token_service import create_refresh_token



def create_session(db: Session, account_id: uuid.UUID, refresh_token_jti: str, refresh_token_hash: str, expires_at: datetime, client_type: ClientType = ClientType.MOBILE,
                    ip_address: str | None = None, user_agent: str | None = None) -> AuthSession:
    """Create a persistent refresh-token session."""

    session = AuthSession(
        account_id=account_id,
        refresh_token_jti=refresh_token_jti,
        refresh_token_hash=refresh_token_hash,
        expires_at=expires_at,
        client_type=client_type,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(session)
    db.flush()

    return session



def get_active_session(db: Session, refresh_token_jti: str) -> AuthSession | None:
    """Retrieve and lock a non-revoked, non-expired session."""

    statement = (
        select(AuthSession)
        .where(
            AuthSession.refresh_token_jti == refresh_token_jti,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(timezone.utc),
        )
        .with_for_update()
    )

    return db.execute(statement).scalar_one_or_none()


def rotate_refresh_token(db: Session, refresh_token: str, refresh_token_jti: str,) -> tuple[AuthSession, str] | None:
    """Validate and rotate an existing refresh token.

    The caller must commit the transaction after success.
    The caller must roll back on exceptions.
    """

    session = get_active_session(db, refresh_token_jti)

    if session is None:
        return None

    supplied_hash = hashlib.sha256(
        refresh_token.encode("utf-8")
    ).hexdigest()

    if not hmac.compare_digest(
        supplied_hash,
        session.refresh_token_hash,
    ):
        return None

    from app.modules.auth.models import Account

    account = db.get(Account, session.account_id)

    if account is None or not account.is_active:
        session.revoked_at = datetime.now(timezone.utc)
        db.flush()
        return None

    new_token, new_jti, new_hash, new_expiry = create_refresh_token(
        account.id,
        account.account_type.value,
    )

    now = datetime.now(timezone.utc)

    session.refresh_token_jti = new_jti
    session.refresh_token_hash = new_hash
    session.expires_at = new_expiry
    session.last_used_at = now

    db.flush()

    return session, new_token

def revoke_session(db: Session, refresh_token_jti: str) -> bool:
    """Revoke an active session."""

    session = get_active_session(db, refresh_token_jti)

    if session is None:
        return False

    session.revoked_at = datetime.now(timezone.utc)
    db.flush()

    return True


def revoke_all_sessions(db: Session, account_id: uuid.UUID,) -> int:
    """Revoke all active sessions belonging to an account."""

    from sqlalchemy import update

    now = datetime.now(timezone.utc)

    statement = (
        update(AuthSession)
        .where(
            AuthSession.account_id == account_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        .values(revoked_at=now)
    )

    result = db.execute(statement)

    return result.rowcount or 0