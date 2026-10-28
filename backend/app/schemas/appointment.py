from datetime import date, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


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
    created_at: datetime


class AppointmentResult(AppointmentOut):
    """Resposta de criação/alteração: inclui avisos (ex.: horário fora do expediente)."""
    warnings: list[str] = []


class AppointmentCreate(BaseModel):
    """Informe `client_id` OU `client_phone` (+ `client_name` se o cliente ainda não existir)."""
    client_id: int | None = None
    client_phone: str | None = Field(default=None, max_length=25)
    client_name: str | None = Field(default=None, min_length=1, max_length=120)
    service_id: int
    starts_at: AwareDatetime
    notes: str | None = Field(default=None, max_length=1000)
    status: str = Field(default="confirmed", pattern="^(pending|confirmed)$")

    @model_validator(mode="after")
    def _client_given(self):
        if (self.client_id is None) == (self.client_phone is None):
            raise ValueError("Informe client_id ou client_phone (apenas um dos dois)")
        return self


class AppointmentUpdate(BaseModel):
    starts_at: AwareDatetime | None = None
    service_id: int | None = None
    notes: str | None = Field(default=None, max_length=1000)


class AppointmentFilters(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    status: str | None = None
    client_id: int | None = None
