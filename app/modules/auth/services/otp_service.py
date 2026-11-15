import hashlib
import hmac
import secrets
import uuid

from app.core.config import settings


OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 300
OTP_MAX_ATTEMPTS = 5


def generate_otp() -> str:
    """Generate a cryptographically secure six-digit OTP."""
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def hash_otp(otp: str, challenge_id: uuid.UUID) -> str:
    """Create a challenge-specific HMAC-SHA256 hash of an OTP."""
    message = f"{challenge_id}:{otp}".encode("utf-8")

    return hmac.new(
        settings.OTP_HMAC_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def verify_otp(
    otp: str,
    stored_hash: str,
    challenge_id: uuid.UUID,
) -> bool:
    """Verify an OTP against its challenge-specific HMAC."""
    if len(otp) != OTP_LENGTH or not otp.isdigit():
        return False

    expected_hash = hash_otp(otp, challenge_id)

    return hmac.compare_digest(expected_hash, stored_hash)