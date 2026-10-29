"""agendamentos: conversa do bot que os criou

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("conversation_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_appointments_conversation", "appointments", "conversations", ["conversation_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_appointments_conversation_id", "appointments", ["conversation_id"])
    # Agendamentos já feitos pelo bot: liga à conversa do mesmo canal quando há UMA só conversa para aquela cliente.
    op.execute("""
        UPDATE appointments a SET conversation_id = c.id
        FROM conversations c
        WHERE a.conversation_id IS NULL AND a.source IN ('telegram', 'whatsapp')
          AND c.client_id = a.client_id AND c.channel = a.source
          AND (SELECT count(*) FROM conversations c2 WHERE c2.client_id = a.client_id AND c2.channel = a.source) = 1
    """)


def downgrade() -> None:
    op.drop_index("ix_appointments_conversation_id", table_name="appointments")
    op.drop_constraint("fk_appointments_conversation", "appointments", type_="foreignkey")
    op.drop_column("appointments", "conversation_id")
