"""conversas por canal (telegram/whatsapp) e origem telegram nos agendamentos

Revision ID: a1b2c3d4e5f6
Revises: fb86719c4eb8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "fb86719c4eb8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("channel", sa.String(length=20), server_default="whatsapp", nullable=False))
    op.add_column("conversations", sa.Column("external_id", sa.String(length=64), nullable=True))
    op.execute("UPDATE conversations SET external_id = phone WHERE external_id IS NULL")
    op.alter_column("conversations", "phone", existing_type=sa.String(length=20), nullable=True)
    op.drop_constraint("conversations_phone_key", "conversations", type_="unique")
    op.create_unique_constraint("uq_conversations_channel_external", "conversations", ["channel", "external_id"])
    op.drop_constraint("ck_appointments_source", "appointments", type_="check")
    op.create_check_constraint("ck_appointments_source", "appointments", "source IN ('admin','whatsapp','telegram')")


def downgrade() -> None:
    op.drop_constraint("ck_appointments_source", "appointments", type_="check")
    op.create_check_constraint("ck_appointments_source", "appointments", "source IN ('admin','whatsapp')")
    op.drop_constraint("uq_conversations_channel_external", "conversations", type_="unique")
    op.create_unique_constraint("conversations_phone_key", "conversations", ["phone"])
    op.alter_column("conversations", "phone", existing_type=sa.String(length=20), nullable=False)
    op.drop_column("conversations", "external_id")
    op.drop_column("conversations", "channel")
