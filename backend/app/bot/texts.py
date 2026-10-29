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
BTN_MINE = "🗓 Meus agendamentos"
BTN_HOURS = "🕒 Horários de atend."
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


FULL_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def _span(first: int, last: int) -> str:
    if first == last:
        return FULL_NAMES[first]
    if last - first == 1:
        return f"{FULL_NAMES[first]} e {FULL_NAMES[last].lower()}"
    short = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    return f"{short[first]} a {short[last].lower()}"


def hours_summary(rows: list[tuple[int, str, str]]) -> str:
    """rows = (dia da semana 0-6, início "09:00", fim "12:00"). Junta dias seguidos com o mesmo expediente.

    Ex.: Seg a sex: 09:00–12:00 e 14:00–19:00 | Sábado: 09:00–16:00 | Domingo: fechado
    """
    by_day: dict[int, list[str]] = {d: [] for d in range(7)}
    for day, start, end in sorted(rows):
        by_day[day].append(f"{start}–{end}")
    lines, day = [], 0
    while day < 7:
        end = day
        while end + 1 < 7 and by_day[end + 1] == by_day[day]:
            end += 1
        label = _span(day, end)
        lines.append(f"{label}: " + (" e ".join(by_day[day]) if by_day[day] else "fechado"))
        day = end + 1
    return "\n".join(lines)


def hours_screen(summary: str | None, free_days: list[str]) -> str:
    if not summary:
        return "Os horários de atendimento ainda não foram cadastrados. Fale diretamente com a gente, por favor."
    free = ("Próximos dias com horário livre: " + ", ".join(free_days) + ".") if free_days else \
           "No momento não há horários livres nos próximos dias."
    return f"🕒 Horários de atendimento\n\n{summary}\n\n{free}\nToque em \"Agendar horário\" para escolher o seu."


def greeting(name: str | None) -> str:
    hello = f"Olá, {name}! 👋" if name else "Olá! 👋"
    return f"{hello}\nSou o assistente de agendamentos de {settings.business_name}. Como posso ajudar?"


CHOOSE_SERVICE = "Qual serviço você quer agendar?"
NO_SERVICES = "Ainda não há serviços disponíveis para agendar por aqui. Fale diretamente com a gente, por favor."
CHOOSE_DAY = "Para qual dia?"
NO_DAYS = "Não encontrei horários livres nos próximos dias. Tente novamente mais tarde ou fale diretamente com a gente."
CHOOSE_TIME = "Qual horário?"
ASK_PHONE = ("Para confirmar o agendamento preciso do seu número de celular. "
             "Toque no botão \"📱 Compartilhar meu número\" abaixo.\n\n"
             "Não apareceu? No Telegram do computador ele fica atrás do ícone de teclado, ao lado do campo de mensagem. "
             "No celular aparece direto.")
PHONE_BUTTON_ONLY = ("Por segurança, só aceito o número pelo botão \"📱 Compartilhar meu número\" (digitar não confirma que "
                     "o número é seu). Se o botão não aparece, abra o Telegram no celular ou fale diretamente com a gente.")
ASK_TYPED_PHONE = ("Pode digitar o seu celular com DDD (ex.: 11 99999-8888). "
                   "Obs.: sem a confirmação pelo botão, não consigo mostrar nem cancelar agendamentos por aqui.")
BAD_PHONE = "Não entendi esse número. Digite com DDD, por exemplo: 11 99999-8888."
PHONE_ALREADY_REGISTERED = ("Esse número já tem cadastro. Para continuar sem digitar, toque em \"📱 Compartilhar meu número\" "
                            "(confirma que é você) ou fale diretamente com a gente.")
VERIFY_TO_MANAGE = ("Para ver ou cancelar seus agendamentos preciso confirmar que o número é seu. "
                    "Toque em \"📱 Compartilhar meu número\".")
BAD_CONTACT = "Esse contato não é o seu. Preciso do SEU número: toque no botão para compartilhar o seu."
ASK_NAME = "Como você se chama? (nome e sobrenome, se preferir)"
BAD_NAME = "Não entendi o nome. Pode escrever de novo? (de 2 a 80 letras)"
USE_BUTTONS = "Use os botões abaixo, por favor 👇"
EXPIRED = "Essa opção já expirou. Vamos recomeçar 🙂"
SLOT_TAKEN = "Poxa, esse horário acabou de ser ocupado por outra pessoa. Vamos escolher outro:"
SLOT_GONE = "Esse horário não está mais disponível. Vamos escolher outro:"
NOTHING_BOOKED = "Você não tem agendamentos futuros."
NOTHING_BOOKED_UNVERIFIED = ("Você não tem agendamentos futuros feitos por esta conversa. "
                             "Para ver os de outros cadastros seus, toque em \"📱 Compartilhar meu número\" (confirma que o número é seu).")
CANCELLED = "Pronto, o agendamento foi cancelado. O horário foi liberado."
CANNOT_CANCEL = "Não consegui cancelar esse agendamento. Ele pode já ter sido cancelado ou ter passado."


def summary(service: str, price: int, minutes: int, start: datetime, name: str | None) -> str:
    who = f"\n👤 {name}" if name else ""
    return (f"Confira o seu agendamento:\n\n💅 {service} ({duration(minutes)})\n🗓 {when(start)}\n💰 {money(price)}{who}\n\n"
            "Posso confirmar?")


def booked(service: str, start: datetime) -> str:
    return f"✅ Agendado! {service}, {when(start)}.\nAté lá! Se precisar mudar, é só me chamar por aqui."


def rescheduled(service: str, old: datetime, new: datetime) -> str:
    return (f"📅 O horário do seu agendamento foi alterado.\n\n💅 {service}\nDe: {when(old)}\nPara: {when(new)}\n\n"
            "Se esse novo horário não funcionar para você, é só me chamar por aqui.")


def cancelled_by_studio(service: str, start: datetime) -> str:
    return (f"❌ Precisamos cancelar o seu agendamento de {service} ({when(start)}). Sentimos muito pelo transtorno.\n\n"
            "Quer marcar outro horário? Toque no botão abaixo.")


def reminder(service: str, start: datetime) -> str:
    from datetime import timedelta
    early = settings.arrive_early_minutes
    arrive = (start - timedelta(minutes=early)).astimezone(TZ)
    return (f"⏰ Lembrete: você tem {service} {when(start)}.\n\n"
            f"Por favor, chegue {early} minutos antes, por volta das {arrive:%H:%M}.\n"
            "Se não puder comparecer, avise por aqui com antecedência para liberarmos o horário.")


def my_appointment(index: int, service: str, start: datetime, status: str) -> str:
    mark = "✅ confirmado" if status == "confirmed" else "⏳ pendente"
    return f"{index}. {service}, {when(start)} ({mark})"
