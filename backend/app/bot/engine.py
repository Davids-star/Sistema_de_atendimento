"""O cérebro da conversa de agendamento. Não conhece Telegram nem WhatsApp: recebe `Incoming`, devolve `Reply`s.

Estados (guardados em `conversations.state`; os dados do que a pessoa escolheu ficam em `conversations.context`):
  idle -> choose_service -> choose_day -> choose_time -> [ask_phone] -> [ask_name] -> confirm -> idle
Os botões carregam só o essencial ("svc:3"); tudo é revalidado contra o banco antes de agir, então botão antigo ou
forjado nunca causa estrago.
"""
import logging
import re
import threading
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.bot import texts
from app.bot.types import Button, Incoming, Reply
from app.core import rate_limit
from app.core.config import settings
from app.models import Appointment, Client, Conversation, Service, WhatsAppMessage
from app.models.appointment import ACTIVE_STATUSES
from app.services import appointments as appt_service
from app.services import owner_notify
from app.services.availability import TZ, slots_for_day
from app.services.clients import get_or_create_by_phone, normalize_phone

logger = logging.getLogger("app.bot")

MENU_WORDS = {"/start", "/menu", "menu", "oi", "olá", "ola", "início", "inicio", "voltar", "recomeçar"}
MAX_TEXT = 200
RATE_PER_MINUTE = 15
TIMES_PER_PAGE = 7     # 7 horários + "Mais horários" + "Outro dia" + "Menu" = 10 opções (limite do WhatsApp)
MAX_SERVICES = 9
MAX_DAYS = 9


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return datetime.now(TZ).date()


def _menu_buttons() -> list[list[Button]]:
    return [[Button(texts.BTN_BOOK, "book")], [Button(texts.BTN_MINE, "mine")]]


def run_in_background(fn, *args) -> threading.Thread:
    """Executa algo sem fazer a cliente esperar (ex.: avisar o dono). Falhas aqui nunca chegam à cliente."""
    def runner():
        try:
            fn(*args)
        except Exception:
            logger.exception("falha em tarefa de segundo plano")
    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------- entrada
def handle(db: Session, inc: Incoming) -> list[Reply]:
    """Processa uma mensagem. Nunca levanta erro para o canal: em caso de falha, pede para tentar de novo."""
    key = f"{inc.channel}:{inc.external_id}"
    window = 60
    if rate_limit.bot_messages.count(key, window) >= RATE_PER_MINUTE:
        return []   # excesso de mensagens: ignora em silêncio
    rate_limit.bot_messages.hit(key, window)

    conv = _get_conversation(db, inc)
    if not _register_message(db, conv, inc):
        return []   # mensagem repetida (o canal reenviou): já foi tratada
    try:
        replies = _route(db, conv, inc)
        conv.last_message_at = _now()
        db.commit()
        return replies
    except Exception:
        logger.exception("erro na conversa (%s)", inc.channel)
        db.rollback()
        return [Reply("Tive um probleminha aqui. Pode tentar de novo? Envie /menu para recomeçar.")]


def _get_conversation(db: Session, inc: Incoming) -> Conversation:
    conv = db.scalar(select(Conversation).where(Conversation.channel == inc.channel,
                                                Conversation.external_id == inc.external_id))
    if conv is None:
        try:
            with db.begin_nested():
                conv = Conversation(channel=inc.channel, external_id=inc.external_id, state="idle", context={})
                db.add(conv)
                db.flush()
        except IntegrityError:   # duas mensagens simultâneas criaram juntas
            conv = db.scalar(select(Conversation).where(Conversation.channel == inc.channel,
                                                        Conversation.external_id == inc.external_id))
    return conv


def _register_message(db: Session, conv: Conversation, inc: Incoming) -> bool:
    """Guarda a mensagem recebida. False se este id já foi processado (deduplicação)."""
    body = (inc.data or inc.text or ("[contato]" if inc.phone else ""))[:MAX_TEXT]
    try:
        with db.begin_nested():
            db.add(WhatsAppMessage(wa_message_id=inc.message_id, conversation_id=conv.id, direction="in", body=body,
                                   processing_status="processed"))
            db.flush()
        return True
    except IntegrityError:
        return False


# ---------------------------------------------------------------- roteamento
def _reset(conv: Conversation) -> None:
    conv.state, conv.context = "idle", {}


def _set(conv: Conversation, state: str, **context) -> None:
    conv.state = state
    conv.context = {**(conv.context or {}), **context}   # atribuir um dict novo é o que o SQLAlchemy detecta


def _route(db: Session, conv: Conversation, inc: Incoming) -> list[Reply]:
    # Conversa parada há muito tempo volta ao menu (evita agir sobre uma escolha antiga).
    if conv.last_message_at and _now() - conv.last_message_at > timedelta(minutes=settings.bot_session_minutes):
        _reset(conv)
    if inc.phone:
        _bind_phone(db, conv, inc.phone)
    if inc.contact_rejected:
        return [Reply(texts.BAD_CONTACT, ask_contact=True)]

    text = (inc.text or "").strip()[:MAX_TEXT]
    if text.lower() in MENU_WORDS or inc.data == "menu":
        _reset(conv)
        return [_menu(db, conv)]

    if inc.data:
        action, _, arg = inc.data.partition(":")
        handler = {"book": _book, "svc": _choose_service, "day": _choose_day, "time": _choose_time, "more": _more_times,
                   "yes": _confirm, "back_days": _back_days, "mine": _mine, "cancel": _ask_cancel,
                   "cancel_yes": _do_cancel}.get(action)
        return handler(db, conv, arg) if handler else [Reply(texts.EXPIRED, _menu_buttons())]

    if conv.state == "ask_phone" and inc.phone:
        return _after_identity(db, conv)
    if conv.state == "ask_name" and text:
        return _receive_name(db, conv, text)
    if conv.state == "ask_phone":
        return [Reply(texts.ASK_PHONE, ask_contact=True)]
    if conv.state == "ask_name":
        return [Reply(texts.ASK_NAME)]
    if conv.state == "idle":
        return [_menu(db, conv)]
    return [Reply(texts.USE_BUTTONS)] + _current_step(db, conv)


def _client(db: Session, conv: Conversation) -> Client | None:
    return db.get(Client, conv.client_id) if conv.client_id else None


def _menu(db: Session, conv: Conversation) -> Reply:
    client = _client(db, conv)
    return Reply(texts.greeting(client.name.split()[0] if client else None), _menu_buttons())


def _bind_phone(db: Session, conv: Conversation, phone: str) -> None:
    """Guarda o número confirmado pelo canal e liga a conversa ao cliente que já tiver esse número."""
    try:
        phone = normalize_phone(phone)
    except ValueError:
        return
    conv.phone = phone
    if conv.client_id is None:
        client = db.scalar(select(Client).where(Client.phone == phone))
        if client:
            conv.client_id = client.id


def _current_step(db: Session, conv: Conversation) -> list[Reply]:
    """Reapresenta o passo em que a pessoa está (quando ela escreve em vez de tocar num botão)."""
    ctx = conv.context or {}
    if conv.state == "choose_service":
        return _book(db, conv, "")
    if conv.state == "choose_day" and ctx.get("service_id"):
        return _show_days(db, conv, ctx["service_id"])
    if conv.state == "choose_time" and ctx.get("service_id") and ctx.get("day"):
        return _show_times(db, conv, ctx["service_id"], date.fromisoformat(ctx["day"]))
    if conv.state == "confirm":
        return _show_confirm(db, conv)
    return [_menu(db, conv)]


# ---------------------------------------------------------------- agendar
def _active_services(db: Session) -> list[Service]:
    return list(db.scalars(select(Service).where(Service.is_active).order_by(Service.name)))


def _book(db: Session, conv: Conversation, _arg: str) -> list[Reply]:
    services = _active_services(db)
    if not services:
        _reset(conv)
        return [Reply(texts.NO_SERVICES, [[Button(texts.BTN_MENU, "menu")]])]
    _set(conv, "choose_service")
    rows = [[Button(texts.short(s.name), f"svc:{s.id}", f"{s.name} · {texts.duration(s.duration_minutes)} · {texts.money(s.price_cents)}"[:72]
                    if len(s.name) > 20 else f"{texts.duration(s.duration_minutes)} · {texts.money(s.price_cents)}")]
            for s in services[:MAX_SERVICES]]
    return [Reply(texts.CHOOSE_SERVICE, rows + [[Button(texts.BTN_MENU, "menu")]])]


def _service(db: Session, service_id: int) -> Service | None:
    service = db.get(Service, service_id)
    return service if service and service.is_active else None


def _choose_service(db: Session, conv: Conversation, arg: str) -> list[Reply]:
    if conv.state != "choose_service" or not arg.isdigit() or _service(db, int(arg)) is None:
        return [Reply(texts.EXPIRED, _menu_buttons())]
    _set(conv, "choose_day", service_id=int(arg))
    return _show_days(db, conv, int(arg))


def _show_days(db: Session, conv: Conversation, service_id: int) -> list[Reply]:
    service = _service(db, service_id)
    today = _today()
    days = [d for d in (today + timedelta(days=i) for i in range(settings.bot_booking_days))
            if slots_for_day(db, d, service)]
    if not days:
        _reset(conv)
        return [Reply(texts.NO_DAYS, [[Button(texts.BTN_MENU, "menu")]])]
    buttons = [Button(texts.day_label(d, today), f"day:{d.isoformat()}") for d in days[:MAX_DAYS]]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return [Reply(texts.CHOOSE_DAY, rows + [[Button(texts.BTN_MENU, "menu")]])]


def _choose_day(db: Session, conv: Conversation, arg: str) -> list[Reply]:
    ctx = conv.context or {}
    try:
        day = date.fromisoformat(arg)
    except ValueError:
        return [Reply(texts.EXPIRED, _menu_buttons())]
    if conv.state not in ("choose_day", "choose_time") or not ctx.get("service_id") or _service(db, ctx["service_id"]) is None:
        return [Reply(texts.EXPIRED, _menu_buttons())]
    _set(conv, "choose_time", day=day.isoformat())
    return _show_times(db, conv, ctx["service_id"], day)


def _show_times(db: Session, conv: Conversation, service_id: int, day: date, intro: str | None = None, page: int = 0) -> list[Reply]:
    slots = slots_for_day(db, day, _service(db, service_id))
    if not slots:
        _set(conv, "choose_day")
        return [Reply(texts.SLOT_GONE)] + _show_days(db, conv, service_id)
    pages = max(1, -(-len(slots) // TIMES_PER_PAGE))
    page = min(max(page, 0), pages - 1)
    _set(conv, "choose_time", day=day.isoformat(), page=page)
    shown = slots[page * TIMES_PER_PAGE:(page + 1) * TIMES_PER_PAGE]
    buttons = [Button(s.astimezone(TZ).strftime("%H:%M"), f"time:{s.astimezone(timezone.utc).strftime('%Y%m%dT%H%M')}") for s in shown]
    rows = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]
    nav = [Button(texts.BTN_MORE_TIMES, f"more:{(page + 1) % pages}")] if pages > 1 else []
    return [Reply(intro or texts.CHOOSE_TIME, rows + ([nav] if nav else []) + [[Button(texts.BTN_OTHER_DAY, "back_days"), Button(texts.BTN_MENU, "menu")]])]


def _more_times(db: Session, conv: Conversation, arg: str) -> list[Reply]:
    ctx = conv.context or {}
    if conv.state != "choose_time" or not arg.isdigit() or not ctx.get("service_id") or not ctx.get("day"):
        return [Reply(texts.EXPIRED, _menu_buttons())]
    return _show_times(db, conv, ctx["service_id"], date.fromisoformat(ctx["day"]), page=int(arg))


def _back_days(db: Session, conv: Conversation, _arg: str) -> list[Reply]:
    ctx = conv.context or {}
    if not ctx.get("service_id") or _service(db, ctx["service_id"]) is None:
        return [Reply(texts.EXPIRED, _menu_buttons())]
    _set(conv, "choose_day")
    return _show_days(db, conv, ctx["service_id"])


def _choose_time(db: Session, conv: Conversation, arg: str) -> list[Reply]:
    ctx = conv.context or {}
    service = _service(db, ctx.get("service_id") or 0)
    if conv.state != "choose_time" or service is None:
        return [Reply(texts.EXPIRED, _menu_buttons())]
    try:
        start = datetime.strptime(arg, "%Y%m%dT%H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return [Reply(texts.EXPIRED, _menu_buttons())]
    # Revalida: só vale um horário que AINDA esteja entre os livres (nunca confiar no botão).
    if start not in slots_for_day(db, start.astimezone(TZ).date(), service):
        return _show_times(db, conv, service.id, date.fromisoformat(ctx["day"]), texts.SLOT_GONE)
    _set(conv, "confirm", start=start.isoformat())
    if _client(db, conv):
        return _show_confirm(db, conv)
    if conv.phone:   # canal que já garante o número (WhatsApp): falta só o nome
        _set(conv, "ask_name")
        return [Reply(texts.ASK_NAME)]
    _set(conv, "ask_phone")
    return [Reply(texts.ASK_PHONE, ask_contact=True)]


def _after_identity(db: Session, conv: Conversation) -> list[Reply]:
    """Chamado quando o canal acabou de confirmar o telefone. Cliente conhecido segue; novo informa o nome."""
    if _client(db, conv):
        _set(conv, "confirm")
        return _show_confirm(db, conv)
    _set(conv, "ask_name")
    return [Reply(texts.ASK_NAME)]


def _receive_name(db: Session, conv: Conversation, text: str) -> list[Reply]:
    name = re.sub(r"\s+", " ", "".join(c for c in text if c.isprintable())).strip()
    if not (2 <= len(name) <= 80) or not re.search(r"[^\W\d_]{2}", name):
        return [Reply(texts.BAD_NAME)]
    if not conv.phone:   # defesa: sem telefone confirmado não se cria cliente
        _set(conv, "ask_phone")
        return [Reply(texts.ASK_PHONE, ask_contact=True)]
    client, _ = get_or_create_by_phone(db, conv.phone, name)
    conv.client_id = client.id
    _set(conv, "confirm")
    return _show_confirm(db, conv)


def _show_confirm(db: Session, conv: Conversation) -> list[Reply]:
    ctx = conv.context or {}
    service = _service(db, ctx.get("service_id") or 0)
    if service is None or not ctx.get("start"):
        _reset(conv)
        return [Reply(texts.EXPIRED, _menu_buttons())]
    client = _client(db, conv)
    start = datetime.fromisoformat(ctx["start"])
    return [Reply(texts.summary(service.name, service.price_cents, service.duration_minutes, start,
                                client.name if client else None),
                  [[Button(texts.BTN_CONFIRM, "yes")], [Button(texts.BTN_OTHER_TIME, "back_days"), Button(texts.BTN_MENU, "menu")]])]


def _confirm(db: Session, conv: Conversation, _arg: str) -> list[Reply]:
    ctx = conv.context or {}
    client, service = _client(db, conv), _service(db, ctx.get("service_id") or 0)
    if conv.state != "confirm" or client is None or service is None or not ctx.get("start"):
        return [Reply(texts.EXPIRED, _menu_buttons())]
    start = datetime.fromisoformat(ctx["start"])
    try:
        # strict=True: só aceita horário realmente livre, dentro do expediente e na grade (nunca no passado).
        appt, _ = appt_service.create_appointment(
            db, admin=None, client_id=client.id, client_phone=None, client_name=None, service_id=service.id,
            starts_at=start, notes=None, status="confirmed", source=conv.channel, strict=True)
    except appt_service.AppointmentError:
        _set(conv, "choose_time")
        return _show_times(db, conv, service.id, start.astimezone(TZ).date(), texts.SLOT_TAKEN)
    _reset(conv)
    db.commit()
    run_in_background(owner_notify.notify_owner_booking, appt.id, conv.channel)   # a cliente não espera por isso
    return [Reply(texts.booked(service.name, start), _menu_buttons())]


# ---------------------------------------------------------------- meus agendamentos / cancelar
def _my_upcoming(db: Session, conv: Conversation) -> list[Appointment]:
    if not conv.client_id:
        return []
    return list(db.scalars(select(Appointment).where(
        Appointment.client_id == conv.client_id, Appointment.status.in_(ACTIVE_STATUSES), Appointment.starts_at > _now())
        .order_by(Appointment.starts_at).limit(5)))


def _mine(db: Session, conv: Conversation, _arg: str) -> list[Reply]:
    items = _my_upcoming(db, conv)
    if not items:
        return [Reply(texts.NOTHING_BOOKED, _menu_buttons())]
    lines = [texts.my_appointment(i, a.service.name, a.starts_at, a.status) for i, a in enumerate(items, 1)]
    rows = [[Button(f"❌ Cancelar {i}", f"cancel:{a.id}")] for i, a in enumerate(items, 1)]
    return [Reply("Seus próximos agendamentos:\n\n" + "\n".join(lines), rows + [[Button(texts.BTN_MENU, "menu")]])]


def _own(db: Session, conv: Conversation, raw_id: str) -> Appointment | None:
    """O agendamento só vale se for DESTA pessoa: um id forjado no botão não cancela o de outra cliente."""
    if not raw_id.isdigit() or not conv.client_id:
        return None
    return next((a for a in _my_upcoming(db, conv) if a.id == int(raw_id)), None)


def _ask_cancel(db: Session, conv: Conversation, arg: str) -> list[Reply]:
    appt = _own(db, conv, arg)
    if appt is None:
        return [Reply(texts.CANNOT_CANCEL, _menu_buttons())]
    return [Reply(f"Cancelar {appt.service.name}, {texts.when(appt.starts_at)}?",
                  [[Button(texts.BTN_YES_CANCEL, f"cancel_yes:{appt.id}"), Button(texts.BTN_NO, "mine")]])]


def _do_cancel(db: Session, conv: Conversation, arg: str) -> list[Reply]:
    appt = _own(db, conv, arg)
    if appt is None:
        return [Reply(texts.CANNOT_CANCEL, _menu_buttons())]
    try:
        appt_service.change_status(db, None, appt.id, "cancel")
    except appt_service.AppointmentError:
        return [Reply(texts.CANNOT_CANCEL, _menu_buttons())]
    return [Reply(texts.CANCELLED, _menu_buttons())]
