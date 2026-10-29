"""agendamentos: quem cancelou e quando

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("cancelled_by", sa.String(length=120), nullable=True))
    op.add_column("appointments", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    # Cancelamentos antigos: recupera o autor e o momento a partir da trilha de auditoria.
    op.execute("""
        UPDATE appointments a SET
          cancelled_at = l.created_at,
          cancelled_by = CASE WHEN l.admin_user_id IS NULL THEN 'cliente (pelo bot)' ELSE COALESCE(u.name, 'painel') || ' (painel)' END
        FROM (SELECT DISTINCT ON (entity_id) entity_id, admin_user_id, created_at FROM audit_logs
              WHERE entity_type = 'appointment' AND action = 'cancel' ORDER BY entity_id, id DESC) l
        LEFT JOIN admin_users u ON u.id = l.admin_user_id
        WHERE a.id = l.entity_id AND a.status = 'cancelled'
    """)
    op.execute("UPDATE appointments SET cancelled_at = updated_at WHERE status = 'cancelled' AND cancelled_at IS NULL")


def downgrade() -> None:
    op.drop_column("appointments", "cancelled_at")
    op.drop_column("appointments", "cancelled_by")
