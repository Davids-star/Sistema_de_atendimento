from datetime import datetime

from pydantic import BaseModel


class ConversationOut(BaseModel):
    id: int
    channel: str
    client_name: str | None
    client_phone: str | None
    phone_verified: bool
    needs_human: bool
    handoff_at: datetime | None
    handoff_note: str | None
    last_message_at: datetime | None
