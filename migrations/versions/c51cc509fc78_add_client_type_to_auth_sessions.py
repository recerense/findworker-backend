
"""add client type to auth sessions

Revision ID: c51cc509fc78
Revises: 6c426b68a072
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c51cc509fc78"
down_revision: Union[str, Sequence[str], None] = "6c426b68a072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


client_type_enum = sa.Enum(
    "MOBILE",
    "WEB",
    "CAPACITOR",
    "API",
    name="client_type",
)


def upgrade() -> None:
    client_type_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "auth_sessions",
        sa.Column(
            "client_type",
            client_type_enum,
            server_default="MOBILE",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("auth_sessions", "client_type")

    client_type_enum.drop(op.get_bind(), checkfirst=True)
