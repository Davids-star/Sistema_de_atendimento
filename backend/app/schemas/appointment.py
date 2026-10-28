from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    client_id: int
    service_id: int
    starts_at: datetime
    ends_at: datetime
    status: str
    price_cents: int
    source: str
    notes: str | None
