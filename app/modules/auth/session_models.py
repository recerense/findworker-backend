
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.auth.models import Account  # noqa: F401


class ClientType(str, enum.Enum):
    MOBILE = "MOBILE"
    WEB = "WEB"
    CAPACITOR = "CAPACITOR"
    API = "API"


class AuthSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stores refresh-token sessions for authenticated accounts."""

    __tablename__ = "auth_sessions"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    client_type: Mapped[ClientType] = mapped_column(
        Enum(ClientType, name="client_type", native_enum=True),
        nullable=False,
        default=ClientType.MOBILE,
        server_default="MOBILE",
    )

    refresh_token_jti: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
    )

    refresh_token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )


