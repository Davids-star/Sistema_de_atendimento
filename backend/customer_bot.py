"""Executa o bot do CLIENTE no Telegram. Uso: python backend/customer_bot.py

Deixe rodando num terminal separado. O token vem de CUSTOMER_BOT_TOKEN no .env (um bot criado no @BotFather,
diferente do bot de avisos do dono).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.bot.channels import telegram  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402


def main():
    setup_logging()
    if not settings.customer_bot_token:
        sys.exit("Defina CUSTOMER_BOT_TOKEN no .env (veja docs/bot-cliente.md).")
    if settings.customer_bot_token == settings.telegram_bot_token:
        sys.exit("CUSTOMER_BOT_TOKEN não pode ser o mesmo bot do dono (TELEGRAM_BOT_TOKEN): crie outro no @BotFather.")
    print("Bot do cliente escutando o Telegram… (Ctrl+C para parar)", flush=True)
    telegram.run()


if __name__ == "__main__":
    main()
