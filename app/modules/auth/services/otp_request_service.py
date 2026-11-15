
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import Account
from app.modules.auth.otp_models import OTPPurpose
from app.modules.auth.schemas import OTPRequest
from app.modules.auth.services.otp_challenge_service import (
    create_otp_challenge,
)
from app.modules.auth.services.otp_delivery_service import send_otp


class OTPRequestError(Exception):
    """Raised when an OTP request cannot be processed."""


def request_otp(db: Session, request: OTPRequest) -> None:
    destination = request.destination
    purpose = request.purpose

    account = None

    if purpose != OTPPurpose.REGISTRATION:
        account = db.execute(
            select(Account).where(
                (
                    Account.phone == destination
                    if purpose in {
                        OTPPurpose.LOGIN,
                        OTPPurpose.VERIFY_PHONE,
                    }
                    else Account.email == destination
                )
            )
        ).scalar_one_or_none()

        if account is None:
            raise OTPRequestError("Unable to process OTP request")

        if not account.is_active:
            raise OTPRequestError("Unable to process OTP request")

        if purpose == OTPPurpose.VERIFY_PHONE and account.phone != destination:
            raise OTPRequestError("Unable to process OTP request")

        if purpose == OTPPurpose.VERIFY_EMAIL and account.email != destination:
            raise OTPRequestError("Unable to process OTP request")

    _, otp = create_otp_challenge(
        db=db,
        destination=destination,
        purpose=purpose,
        account_id=account.id if account else None,
    )

    try:
        send_otp(
            destination=destination,
            otp=otp,
            purpose=purpose.value,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise OTPRequestError("Unable to deliver OTP") from None
