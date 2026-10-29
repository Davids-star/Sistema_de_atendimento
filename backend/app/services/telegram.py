"""Telegram: avisos ao dono e botões para liberar/recusar cadastros.

Segurança:
- o token do bot nunca vai para logs (as exceções do `requests` trazem a URL, por isso não as registramos);
- só o chat configurado em TELEGRAM_CHAT_ID pode liberar ou recusar;
- os textos são enviados SEM formatação (parse_mode), para um nome malicioso não injetar nada.
"""
import logging

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AdminUser
from app.services import users as users_service

logger = logging.getLogger("app.telegram")
API = "https://api.telegram.org/bot{token}/{method}"


def enabled() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def call(method: str, payload: dict, timeout: int = 15) -> dict | None:
    """Chama a API do Telegram. Devolve o JSON ou None se falhar (a falha é registrada sem o token)."""
    if not settings.telegram_bot_token:
        return None
    try:
        r = requests.post(API.format(token=settings.telegram_bot_token, method=method), json=payload, timeout=timeout)
        data = r.json()
    except Exception:
        logger.warning("falha ao chamar o Telegram (%s)", method)
        return None
    if not data.get("ok"):
        logger.warning("Telegram recusou %s: %s", method, data.get("description", "?"))
        return None
    return data


def send_message(chat_id: str, text: str, buttons: list[list[dict]] | None = None) -> dict | None:
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    return call("sendMessage", payload)


def approval_buttons(user_id: int) -> list[list[dict]]:
    return [[{"text": "✅ Liberar acesso", "callback_data": f"approve:{user_id}"},
             {"text": "🚫 Recusar", "callback_data": f"reject:{user_id}"}]]


# ---------- recebendo os cliques (long polling) ----------
def _owner(db: Session) -> AdminUser | None:
    return db.scalar(select(AdminUser).where(AdminUser.is_owner, AdminUser.is_active).order_by(AdminUser.id))


def handle_update(db: Session, update: dict) -> None:
    """Processa uma atualização do Telegram: o comando /start e os cliques nos botões."""
    message = update.get("message")
    if message and (message.get("text") or "").startswith("/start"):
        chat_id = str(message["chat"]["id"])
        if chat_id == str(settings.telegram_chat_id):
            send_message(chat_id, "✅ Tudo certo! Este chat está ligado ao painel e vai receber os avisos de novos cadastros.")
        else:
            # Ajuda a configurar: mostra o número do chat para colocar no .env (não é segredo).
            send_message(chat_id, f"Para ligar este chat ao painel, coloque no .env:\nTELEGRAM_CHAT_ID={chat_id}")
        return

    cb = update.get("callback_query")
    if not cb:
        return
    cb_id = cb["id"]
    chat_id = str((cb.get("message") or {}).get("chat", {}).get("id", ""))
    sender = str(cb.get("from", {}).get("id", ""))
    answer = lambda text: call("answerCallbackQuery", {"callback_query_id": cb_id, "text": text, "show_alert": True})

    # Só o dono (chat configurado) decide. Qualquer outro clique é ignorado e registrado.
    if not enabled() or chat_id != str(settings.telegram_chat_id) or sender != str(settings.telegram_chat_id):
        logger.warning("clique no Telegram de chat nao autorizado")
        answer("Você não tem permissão para isso.")
        return

    action, _, raw_id = (cb.get("data") or "").partition(":")
    owner = _owner(db)
    user = db.get(AdminUser, int(raw_id)) if raw_id.isdigit() else None
    if action not in ("approve", "reject") or owner is None or user is None:
        answer("Pedido inválido ou usuário não encontrado.")
        return

    try:
        if action == "approve":
            changed = users_service.approve(db, owner, user, via="telegram")
            result = f"✅ Acesso liberado para {user.name}." if changed else f"ℹ️ {user.name} já tinha acesso liberado."
        else:
            changed = users_service.deactivate(db, owner, user, via="telegram")
            result = f"🚫 Cadastro de {user.name} recusado." if changed else f"ℹ️ {user.name} já estava desativado."
    except users_service.UserActionError as e:
        answer(e.message)
        return

    answer("Feito!")
    msg = cb.get("message") or {}
    # Troca os botões pelo resultado, para não clicar duas vezes.
    call("editMessageText", {"chat_id": chat_id, "message_id": msg.get("message_id"),
                             "text": (msg.get("text") or "") + f"\n\n{result}", "disable_web_page_preview": True})
