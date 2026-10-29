from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Conversation(Base):
    """Uma conversa com um cliente em um canal (telegram, whatsapp...). A identidade é (canal, external_id)."""

    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("channel", "external_id", name="uq_conversations_channel_external"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp", server_default="whatsapp")
    external_id: Mapped[str | None] = mapped_column(String(64))   # id do chat no canal (no WhatsApp, o número)
    phone: Mapped[str | None] = mapped_column(String(20))         # só quando o CANAL confirmou o número
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
    state: Mapped[str] = mapped_column(String(40), default="idle", server_default="idle")
    context: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")  # dados do fluxo em andamento
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"
    __table_args__ = (
        CheckConstraint("direction IN ('in','out')", name="ck_wa_messages_direction"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    wa_message_id: Mapped[str | None] = mapped_column(String(128), unique=True)  # evita processar duas vezes
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    direction: Mapped[str] = mapped_column(String(3))
    body: Mapped[str | None] = mapped_column(Text)
    processing_status: Mapped[str] = mapped_column(String(20), default="received", server_default="received")
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
