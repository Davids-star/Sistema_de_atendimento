"""Importar todos os modelos aqui para o Alembic enxergá-los."""
from app.models.admin_user import AdminUser
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.schedule import BlockedTime, BusinessHours
from app.models.service import Service
from app.models.shop_settings import ShopSettings
from app.models.whatsapp import Conversation, WhatsAppMessage

__all__ = [
    "AdminUser", "Appointment", "AuditLog", "Client", "BlockedTime",
    "BusinessHours", "Service", "ShopSettings", "Conversation", "WhatsAppMessage",
]
