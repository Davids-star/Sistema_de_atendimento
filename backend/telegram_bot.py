"""Fica escutando os cliques do Telegram (Liberar / Recusar). Uso: python backend/telegram_bot.py

Usa "long polling": funciona no seu computador, sem precisar de endereço público.
Deixe rodando num terminal separado enquanto usa o painel.
"""
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import telegram  # noqa: E402

logger = logging.getLogger("app.telegram")


def main():
    setup_logging()
    if not settings.telegram_bot_token:
        sys.exit("Defina TELEGRAM_BOT_TOKEN no .env (veja docs/telegram.md).")
    print("Escutando o Telegram… (Ctrl+C para parar)", flush=True)
    offset = None
    while True:
        data = telegram.call("getUpdates", {"timeout": 30, "offset": offset, "allowed_updates": ["message", "callback_query"]}, timeout=45)
        if data is None:
            time.sleep(5)   # sem internet ou token errado: tenta de novo sem fritar o processador
            continue
        for update in data["result"]:
            offset = update["update_id"] + 1
            try:
                with SessionLocal() as db:
                    telegram.handle_update(db, update)
            except Exception:
                logger.exception("erro ao processar atualizacao do Telegram")


if __name__ == "__main__":
    main()
