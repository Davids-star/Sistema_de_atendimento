from datetime import datetime, time

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class BusinessHoursItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    weekday: int = Field(ge=0, le=6, description="0=segunda ... 6=domingo")
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _order(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time deve ser anterior a end_time")
        return self


class BusinessHoursUpdate(BaseModel):
    """Substitui a semana inteira. Dia sem intervalos = fechado."""
    items: list[BusinessHoursItem]

    @model_validator(mode="after")
    def _no_overlap(self):
        by_day: dict[int, list[BusinessHoursItem]] = {}
        for it in self.items:
            by_day.setdefault(it.weekday, []).append(it)
        for day_items in by_day.values():
            day_items.sort(key=lambda i: i.start_time)
            for a, b in zip(day_items, day_items[1:]):
                if b.start_time < a.end_time:
                    raise ValueError("intervalos do mesmo dia não podem se sobrepor")
        return self


class BlockedTimeCreate(BaseModel):
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _order(self):
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at deve ser anterior a ends_at")
        return self


class BlockedTimeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    starts_at: datetime
    ends_at: datetime
    reason: str | None


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slot_interval_minutes: int
    contact_phone: str | None = None   # WhatsApp do dono para onde o bot encaminha quem precisa falar com uma pessoa


class SettingsUpdate(BaseModel):
    """Só o que for enviado é alterado. `contact_phone` vazio (ou null) apaga o número."""
    slot_interval_minutes: int | None = Field(default=None, ge=5, le=240)
    contact_phone: str | None = Field(default=None, max_length=25)

    @model_validator(mode="after")
    def _something(self):
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo")
        if "slot_interval_minutes" in self.model_fields_set and self.slot_interval_minutes is None:
            raise ValueError("slot_interval_minutes não pode ser nulo")
        return self


class AvailabilityOut(BaseModel):
    date: str
    service_id: int
    duration_minutes: int
    slots: list[datetime]
