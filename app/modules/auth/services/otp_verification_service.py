
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import Account
from app.modules.auth.otp_models import OTPChallenge, OTPPurpose
from app.modules.auth.services.otp_challenge_service import verify_otp_challenge


SUPPORTED_PURPOSES = {
    OTPPurpose.LOGIN,
    OTPPurpose.VERIFY_PHONE,
    OTPPurpose.VERIFY_EMAIL,
}


def verify_otp(db: Session, challenge_id: UUID, otp: str) -> tuple[Account, OTPPurpose] | None:
    """Verify an OTP and apply the corresponding account verification."""

    statement = (
        select(OTPChallenge)
        .where(OTPChallenge.id == challenge_id)
        .with_for_update()
    )

    challenge = db.execute(statement).scalar_one_or_none()

    if challenge is None:
        return None

    if challenge.purpose not in SUPPORTED_PURPOSES:
        return None

    if challenge.account_id is None:
        return None

    account = db.get(Account, challenge.account_id)

    if account is None or not account.is_active:
        return None

    if challenge.purpose in {
        OTPPurpose.LOGIN,
        OTPPurpose.VERIFY_PHONE,
    }:
        if account.phone != challenge.destination:
            return None

    elif challenge.purpose == OTPPurpose.VERIFY_EMAIL:
        if account.email != challenge.destination:
            return None

    verified = verify_otp_challenge(
        db=db,
        challenge=challenge,
        otp=otp,
    )

    if not verified:
        return None

    if challenge.purpose in {
        OTPPurpose.LOGIN,
        OTPPurpose.VERIFY_PHONE,
    }:
        account.is_phone_verified = True

    elif challenge.purpose == OTPPurpose.VERIFY_EMAIL:
        account.is_email_verified = True

    db.flush()

    return account, challenge.purpose
