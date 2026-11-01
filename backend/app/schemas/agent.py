from datetime import datetime
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class AgentErrorDetail(BaseModel):
    code: str = Field(..., description="Código de erro semântico da API")
    message: str = Field(..., description="Descrição detalhada do erro")


class AgentResponse(BaseModel, Generic[T]):
    """Envelope padronizado de resposta para o WhatsApp AI Agent."""
    success: bool
    data: T | None = None
    error: AgentErrorDetail | None = None

    @classmethod
    def ok(cls, data: T) -> "AgentResponse[T]":
        return cls(success=True, data=data, error=None)

    @classmethod
    def fail(cls, code: str, message: str) -> "AgentResponse[None]":
        return cls(success=False, data=None, error=AgentErrorDetail(code=code, message=message))


# ---------- Serviços ----------
class AgentServiceItem(BaseModel):
    id: int
    name: str
    duration_minutes: int
    price_cents: int
    price_formatted: str


# ---------- Disponibilidade ----------
class AgentAvailabilityItem(BaseModel):
    date: str
    service_id: int
    duration_minutes: int
    available_slots: list[str] = Field(..., description="Horários em formato HH:MM")
    available_slots_iso: list[str] = Field(..., description="Horários completos em formato ISO 8601")


# ---------- Clientes ----------
class AgentClientItem(BaseModel):
    id: int
    name: str
    phone: str
    created: bool | None = None


class AgentClientCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=8, max_length=25)


# ---------- Agendamentos ----------
class AgentAppointmentCreate(BaseModel):
    client_phone: str = Field(..., description="Telefone com DDD do cliente do WhatsApp")
    client_name: str | None = Field(None, min_length=2, max_length=100, description="Nome do cliente (obrigatório se novo)")
    service_id: int = Field(..., description="ID do serviço a ser agendado")
    starts_at: datetime = Field(..., description="Data e hora de início no formato ISO (ex: 2026-11-02T14:30:00-03:00)")
    notes: str | None = Field(None, max_length=300, description="Observações da reserva")


class AgentAppointmentItem(BaseModel):
    appointment_id: int
    client_id: int
    client_name: str
    client_phone: str
    service_id: int
    service_name: str
    status: str
    starts_at: datetime
    ends_at: datetime
    price_cents: int
    price_formatted: str
    notes: str | None = None
    cancelled_by: str | None = None


class AgentAppointmentReschedule(BaseModel):
    phone: str = Field(..., description="Telefone do cliente para conferência de titularidade")
    starts_at: datetime = Field(..., description="Nova data e hora de início no formato ISO")
    service_id: int | None = Field(None, description="Novo serviço caso queira trocar")


class AgentAppointmentCancel(BaseModel):
    phone: str = Field(..., description="Telefone do cliente para conferência de titularidade")
    reason: str | None = Field(None, max_length=200, description="Motivo do cancelamento")

