"""Trilha de auditoria. Nunca passe senhas, tokens ou dados sensíveis em `changes`."""
from sqlalchemy.orm import Session

from app.models import AdminUser, AuditLog


def record(db: Session, admin: AdminUser | None, action: str, entity_type: str,
           entity_id: int | None, changes: dict | None = None) -> None:
    db.add(AuditLog(admin_user_id=admin.id if admin else None, action=action,
                    entity_type=entity_type, entity_id=entity_id, changes=changes))
