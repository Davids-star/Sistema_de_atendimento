"""Importar todos os modelos aqui para o Alembic enxergá-los."""
from app.models.admin_user import AdminUser
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.device import DeviceToken
from app.models.email_verification import EmailVerificationToken
from app.models.schedule import BlockedTime, BusinessHours
from app.models.notification import Notification
from app.models.password_reset import PasswordResetToken
from app.models.service import Service
from app.models.shop_settings import ShopSettings
from app.models.whatsapp import Conversation, WhatsAppMessage

__all__ = [
    "AdminUser", "Appointment", "AuditLog", "Client", "DeviceToken", "EmailVerificationToken", "BlockedTime",
    "BusinessHours", "Notification", "PasswordResetToken", "Service", "ShopSettings", "Conversation", "WhatsAppMessage",
]
