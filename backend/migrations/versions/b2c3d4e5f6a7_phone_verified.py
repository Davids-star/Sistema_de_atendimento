"""conversas: telefone confirmado pelo canal

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("phone_verified", sa.Boolean(), server_default="false", nullable=False))
    # Até aqui só era aceito número confirmado pelo canal, então as conversas existentes com telefone já estão confirmadas.
    op.execute("UPDATE conversations SET phone_verified = true WHERE phone IS NOT NULL")


def downgrade() -> None:
    op.drop_column("conversations", "phone_verified")
