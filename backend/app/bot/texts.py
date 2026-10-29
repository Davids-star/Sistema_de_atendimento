"""Todos os textos do bot em um só lugar (fácil de ajustar o tom). Texto puro: sem formatação do canal."""
from datetime import date, datetime

from app.core.config import settings
from app.services.availability import TZ

WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def money(cents: int) -> str:
    return f"R$ {cents / 100:.2f}".replace(".", ",")


def duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if h and m else (f"{h} h" if h else f"{m} min")


def when(dt: datetime) -> str:
    local = dt.astimezone(TZ)
    return f"{WEEKDAYS[local.weekday()]}, {local:%d/%m} às {local:%H:%M}"


def day_label(day: date, today: date) -> str:
    delta = (day - today).days
    prefix = "Hoje" if delta == 0 else "Amanhã" if delta == 1 else WEEKDAYS[day.weekday()]
    return f"{prefix} {day:%d/%m}"


# Rótulos de botões: até 20 caracteres (limite do WhatsApp), então já valem nos dois canais.
BTN_BOOK = "💅 Agendar horário"
BTN_MINE = "🗓 Meus horários"
BTN_MENU = "⬅️ Menu"
BTN_CONFIRM = "✅ Confirmar"
BTN_OTHER_TIME = "📅 Outro horário"
BTN_OTHER_DAY = "📅 Outro dia"
BTN_MORE_TIMES = "➡️ Mais horários"
BTN_YES_CANCEL = "Sim, cancelar"
BTN_NO = "Não"


def short(text: str, limit: int = 20) -> str:
    """Corta com reticências para caber no título de um botão."""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def greeting(name: str | None) -> str:
    hello = f"Olá, {name}! 👋" if name else "Olá! 👋"
    return f"{hello}\nSou o assistente de agendamentos de {settings.business_name}. Como posso ajudar?"


CHOOSE_SERVICE = "Qual serviço você quer agendar?"
NO_SERVICES = "Ainda não há serviços disponíveis para agendar por aqui. Fale diretamente com a gente, por favor."
CHOOSE_DAY = "Para qual dia?"
NO_DAYS = "Não encontrei horários livres nos próximos dias. Tente novamente mais tarde ou fale diretamente com a gente."
CHOOSE_TIME = "Qual horário?"
ASK_PHONE = ("Para confirmar o agendamento preciso do seu número de celular. "
             "Toque no botão abaixo para compartilhar (é o jeito mais seguro).")
BAD_CONTACT = "Esse contato não é o seu. Preciso do SEU número: toque no botão para compartilhar o seu."
ASK_NAME = "Como você se chama? (nome e sobrenome, se preferir)"
BAD_NAME = "Não entendi o nome. Pode escrever de novo? (de 2 a 80 letras)"
USE_BUTTONS = "Use os botões abaixo, por favor 👇"
EXPIRED = "Essa opção já expirou. Vamos recomeçar 🙂"
SLOT_TAKEN = "Poxa, esse horário acabou de ser ocupado por outra pessoa. Vamos escolher outro:"
SLOT_GONE = "Esse horário não está mais disponível. Vamos escolher outro:"
NOTHING_BOOKED = "Você não tem agendamentos futuros."
CANCELLED = "Pronto, o agendamento foi cancelado. O horário foi liberado."
CANNOT_CANCEL = "Não consegui cancelar esse agendamento. Ele pode já ter sido cancelado ou ter passado."


def summary(service: str, price: int, minutes: int, start: datetime, name: str | None) -> str:
    who = f"\n👤 {name}" if name else ""
    return (f"Confira o seu agendamento:\n\n💅 {service} ({duration(minutes)})\n🗓 {when(start)}\n💰 {money(price)}{who}\n\n"
            "Posso confirmar?")


def booked(service: str, start: datetime) -> str:
    return f"✅ Agendado! {service}, {when(start)}.\nAté lá! Se precisar mudar, é só me chamar por aqui."


def my_appointment(index: int, service: str, start: datetime, status: str) -> str:
    mark = "✅ confirmado" if status == "confirmed" else "⏳ pendente"
    return f"{index}. {service}, {when(start)} ({mark})"
