"""Adaptador do Telegram para o bot do cliente. Só traduz: o Telegram <-> o cérebro (app.bot.engine).

Segurança:
- só conversas privadas (grupos são ignorados);
- o telefone só é aceito pelo botão nativo "compartilhar contato" E se o contato for da própria pessoa
  (`contact.user_id == from.id`): digitar um número não prova nada;
- textos vão sem formatação (sem parse_mode): um nome malicioso não injeta nada;
- o token nunca aparece em logs (as exceções do `requests` trazem a URL, então não são registradas).
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.bot import engine
from app.bot.types import Incoming, Reply
from app.core.config import settings
from app.db.session import SessionLocal

logger = logging.getLogger("app.bot.telegram")
API = "https://api.telegram.org/bot{token}/{method}"

# Cada conexão nova ao Telegram custa de 0,7 a 6 s (handshake TLS) em redes lentas. Reaproveitar a conexão (keep-alive)
# paga isso uma vez só. As tentativas cobrem só falha ao CONECTAR (nada foi enviado ainda), então não duplicam mensagem.
_session = requests.Session()
_session.mount("https://", HTTPAdapter(pool_connections=4, pool_maxsize=8,
                                        max_retries=Retry(total=2, connect=2, read=0, backoff_factor=0.2,
                                                          allowed_methods=frozenset(["POST"]))))
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tg")   # chamadas independentes em paralelo


def call(method: str, payload: dict, timeout: int = 15) -> dict | None:
    if not settings.customer_bot_token:
        return None
    try:
        r = _session.post(API.format(token=settings.customer_bot_token, method=method), json=payload, timeout=timeout)
        data = r.json()
    except Exception:
        logger.warning("falha ao chamar o Telegram (%s)", method)
        return None
    if not data.get("ok"):
        logger.warning("Telegram recusou %s: %s", method, data.get("description", "?"))
        return None
    return data


# ---------------------------------------------------------------- Telegram -> cérebro
def to_incoming(update: dict) -> Incoming | None:
    """Converte uma atualização do Telegram. None = ignorar."""
    uid = update.get("update_id")
    msg = update.get("message")
    cb = update.get("callback_query")
    if cb:
        chat = (cb.get("message") or {}).get("chat") or {}
        if chat.get("type") != "private":
            return None
        return Incoming(channel="telegram", external_id=str(chat["id"]), message_id=f"tg:{uid}", data=cb.get("data") or "")
    if not msg:
        return None
    chat = msg.get("chat") or {}
    if chat.get("type") != "private":
        return None
    inc = Incoming(channel="telegram", external_id=str(chat["id"]), message_id=f"tg:{uid}", text=msg.get("text"))
    contact = msg.get("contact")
    if contact:
        if contact.get("user_id") is not None and contact.get("user_id") == (msg.get("from") or {}).get("id"):
            inc.phone = str(contact.get("phone_number") or "")
        else:
            inc.contact_rejected = True   # contato de outra pessoa (ou sem dono identificado)
    return inc


# ---------------------------------------------------------------- cérebro -> Telegram
def _button(button) -> dict:
    """Botão de link (abre um endereço) ou de escolha (volta ao bot). O Telegram não aceita os dois juntos."""
    if button.url:
        return {"text": _label(button), "url": button.url}
    return {"text": _label(button), "callback_data": button.data}


def _label(button) -> str:
    """No Telegram não há "descrição" separada: juntamos ao título (ex.: "Manicure · 45 min · R$ 45,00")."""
    return f"{button.text} · {button.description}" if button.description else button.text


def to_payload(chat_id: str, reply: Reply) -> dict:
    payload = {"chat_id": chat_id, "text": reply.text, "disable_web_page_preview": True}
    if reply.ask_contact:
        payload["reply_markup"] = {"keyboard": [[{"text": "📱 Compartilhar meu número", "request_contact": True}]],
                                   "resize_keyboard": True, "one_time_keyboard": True}
    elif reply.buttons:
        payload["reply_markup"] = {"inline_keyboard": [[_button(b) for b in row] for row in reply.buttons]}
    else:
        payload["reply_markup"] = {"remove_keyboard": True}
    return payload


def send_reply(chat_id: str, reply: Reply) -> bool:
    """Envia uma mensagem iniciada pelo SISTEMA (aviso, lembrete). Não mexe no teclado que a pessoa tenha aberto."""
    payload = to_payload(str(chat_id), reply)
    if not reply.buttons and not reply.ask_contact:
        payload.pop("reply_markup", None)
    return call("sendMessage", payload) is not None


def _edit_payload(chat_id, message_id, reply: Reply) -> dict:
    """Troca o conteúdo da mensagem clicada (texto + botões novos). Sem botões, a edição também remove os antigos."""
    payload = to_payload(str(chat_id), reply)
    payload.pop("chat_id")
    if payload["reply_markup"] == {"remove_keyboard": True}:
        payload.pop("reply_markup")   # editMessageText não aceita remove_keyboard; sem reply_markup os botões saem
    return {"chat_id": chat_id, "message_id": message_id, **payload}


def process_update(update: dict) -> None:
    inc = to_incoming(update)
    if inc is None:
        return
    started = time.perf_counter()
    cb = update.get("callback_query")
    ack = _pool.submit(call, "answerCallbackQuery", {"callback_query_id": cb["id"]}) if cb else None   # tira o "relógio" do botão, em paralelo

    with SessionLocal() as db:
        replies = engine.handle(db, inc)
    thinking = time.perf_counter() - started

    pending = list(replies)
    if cb and pending:
        msg = cb.get("message") or {}
        first = pending[0]
        if first.ask_contact:
            # O teclado "compartilhar contato" não existe em edição: manda mensagem nova e só limpa os botões antigos.
            call("editMessageReplyMarkup", {"chat_id": msg["chat"]["id"], "message_id": msg.get("message_id"),
                                            "reply_markup": {"inline_keyboard": []}})
        elif call("editMessageText", _edit_payload(msg["chat"]["id"], msg.get("message_id"), first)):
            pending.pop(0)   # a mensagem clicada virou a resposta: 1 chamada em vez de 3
    for reply in pending:
        call("sendMessage", to_payload(inc.external_id, reply))
    if ack:
        ack.result(timeout=20)
    logger.info("resposta em %d ms (cérebro %d ms, envio %d ms)", (time.perf_counter() - started) * 1000,
                thinking * 1000, (time.perf_counter() - started - thinking) * 1000)


def run() -> None:
    """Escuta o Telegram (long polling: funciona no seu computador, sem endereço público)."""
    me = call("getMe", {})   # abre (e deixa aberta) a conexão antes da primeira mensagem; também confirma o token
    if me:
        logger.info("conectado como @%s", me["result"].get("username"))
    offset, wait = None, 1
    while True:
        data = call("getUpdates", {"timeout": 30, "offset": offset, "allowed_updates": ["message", "callback_query"]}, timeout=45)
        if data is None:
            time.sleep(wait)               # falhou (rede/token): espera pouco na 1ª vez e mais nas seguintes
            wait = min(wait * 2, 15)
            continue
        wait = 1
        for update in data["result"]:
            offset = update["update_id"] + 1
            try:
                process_update(update)
            except Exception:
                logger.exception("erro ao processar atualização do Telegram")
