
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def mask_destination(destination: str) -> str:
    if "@" in destination:
        local, domain = destination.split("@", 1)
        return f"{local[:2]}***@{domain}"

    return f"{destination[:3]}******{destination[-2:]}"


def send_otp(destination: str, otp: str, purpose: str) -> None:
    """Development-only OTP delivery placeholder."""

    if settings.DEBUG:
        logger.warning(
            "DEVELOPMENT OTP | purpose=%s | destination=%s | otp=%s",
            purpose,
            mask_destination(destination),
            otp,
        )
        return

    raise RuntimeError(
        "No production OTP delivery provider is configured"
    )

