"""agendamentos: controle do lembrete ao cliente

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("appointments", sa.Column("reminder_attempts", sa.Integer(), server_default="0", nullable=False))
    # Quem já começou ou já passou não deve receber lembrete retroativo.
    op.execute("UPDATE appointments SET reminder_sent_at = now() WHERE starts_at <= now()")


def downgrade() -> None:
    op.drop_column("appointments", "reminder_attempts")
    op.drop_column("appointments", "reminder_sent_at")
