from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    price_cents: int = Field(ge=0, le=10_000_000)
    duration_minutes: int = Field(gt=0, le=480)


class ServiceUpdate(BaseModel):
    """Todos os campos opcionais: PATCH altera só o que for enviado."""
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    price_cents: int | None = Field(default=None, ge=0, le=10_000_000)
    duration_minutes: int | None = Field(default=None, gt=0, le=480)
    is_active: bool | None = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    price_cents: int
    duration_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
