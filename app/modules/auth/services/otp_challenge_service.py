
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

# Registers the Account model with SQLAlchemy metadata.
from app.modules.auth.models import Account  # noqa: F401
from app.modules.auth.otp_models import OTPChallenge, OTPPurpose
from app.modules.auth.services.otp_service import (
    OTP_EXPIRY_SECONDS,
    OTP_MAX_ATTEMPTS,
    generate_otp,
    hash_otp,
    verify_otp,
)


def create_otp_challenge(db: Session, destination: str, purpose: OTPPurpose, account_id: uuid.UUID | None = None) -> tuple[OTPChallenge, str]:
    """Create and persist an OTP challenge.

    The caller is responsible for committing the transaction.
    The plaintext OTP must only be passed to a trusted delivery service.
    """

    challenge_id = uuid.uuid4()
    otp = generate_otp()

    challenge = OTPChallenge(
        id=challenge_id,
        account_id=account_id,
        destination=destination,
        purpose=purpose,
        otp_hash=hash_otp(otp, challenge_id),
        expires_at=datetime.now(timezone.utc)
        + timedelta(seconds=OTP_EXPIRY_SECONDS),
        attempts=0,
        max_attempts=OTP_MAX_ATTEMPTS,
    )

    db.add(challenge)
    db.flush()

    return challenge, otp



def verify_otp_challenge(db: Session, challenge: OTPChallenge, otp: str) -> bool:
    """
    Verify an already-locked OTP challenge exactly once.

    The caller must commit the transaction after this function returns,
    including when verification fails, to persist failed attempts.
    """

    if challenge.verified_at is not None:
        return False

    if challenge.expires_at <= datetime.now(timezone.utc):
        return False

    if challenge.attempts >= challenge.max_attempts:
        return False

    if not verify_otp(otp, challenge.otp_hash, challenge.id):
        challenge.attempts += 1
        db.flush()
        return False

    challenge.verified_at = datetime.now(timezone.utc)
    db.flush()

    return True

