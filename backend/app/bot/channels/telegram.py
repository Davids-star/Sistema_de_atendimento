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

import requests

from app.bot import engine
from app.bot.types import Incoming, Reply
from app.core.config import settings
from app.db.session import SessionLocal

logger = logging.getLogger("app.bot.telegram")
API = "https://api.telegram.org/bot{token}/{method}"


def call(method: str, payload: dict, timeout: int = 15) -> dict | None:
    if not settings.customer_bot_token:
        return None
    try:
        r = requests.post(API.format(token=settings.customer_bot_token, method=method), json=payload, timeout=timeout)
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
def to_payload(chat_id: str, reply: Reply) -> dict:
    payload = {"chat_id": chat_id, "text": reply.text, "disable_web_page_preview": True}
    if reply.ask_contact:
        payload["reply_markup"] = {"keyboard": [[{"text": "📱 Compartilhar meu número", "request_contact": True}]],
                                   "resize_keyboard": True, "one_time_keyboard": True}
    elif reply.buttons:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": b.text, "callback_data": b.data} for b in row]
                                                       for row in reply.buttons]}
    else:
        payload["reply_markup"] = {"remove_keyboard": True}
    return payload


def process_update(update: dict) -> None:
    inc = to_incoming(update)
    if inc is None:
        return
    cb = update.get("callback_query")
    if cb:   # tira o "relógio" do botão e remove os botões antigos para ninguém tocar duas vezes
        call("answerCallbackQuery", {"callback_query_id": cb["id"]})
        msg = cb.get("message") or {}
        call("editMessageReplyMarkup", {"chat_id": msg["chat"]["id"], "message_id": msg.get("message_id"),
                                        "reply_markup": {"inline_keyboard": []}})
    with SessionLocal() as db:
        replies = engine.handle(db, inc)
    for reply in replies:
        call("sendMessage", to_payload(inc.external_id, reply))


def run() -> None:
    """Escuta o Telegram (long polling: funciona no seu computador, sem endereço público)."""
    offset = None
    while True:
        data = call("getUpdates", {"timeout": 30, "offset": offset, "allowed_updates": ["message", "callback_query"]}, timeout=45)
        if data is None:
            time.sleep(5)   # sem internet ou token errado: tenta de novo sem fritar o processador
            continue
        for update in data["result"]:
            offset = update["update_id"] + 1
            try:
                process_update(update)
            except Exception:
                logger.exception("erro ao processar atualização do Telegram")
