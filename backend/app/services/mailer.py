"""Envio de e-mail. Três modos (MAIL_MODE no .env):

- off:     não envia nada (padrão; o endpoint continua respondendo normalmente)
- console: imprime o e-mail no terminal do servidor. SÓ para testes locais: o link de redefinição
           é equivalente a uma senha temporária, por isso nunca vai para o arquivo de log.
- smtp:    envia de verdade (ex.: Gmail com "senha de app", porta 587).
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("app.mail")


def send_mail(to: str, subject: str, body: str) -> None:
    mode = settings.mail_mode
    if mode == "console":
        print(f"\n=== E-MAIL (modo console) ===\nPara: {to}\nAssunto: {subject}\n\n{body}\n=============================\n", flush=True)
        return
    if mode != "smtp":
        logger.warning("e-mail NAO enviado: MAIL_MODE=%s (configure smtp para enviar de verdade)", mode)
        return
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:
        # Registra a falha (sem o conteúdo do e-mail); o usuário recebe a mesma resposta de sempre.
        logger.exception("falha ao enviar e-mail via SMTP")


def send_reset_email(to: str, raw_token: str) -> None:
    link = f"{settings.frontend_url.rstrip('/')}/redefinir-senha?token={raw_token}"
    send_mail(
        to,
        "Redefinição de senha - Painel da Barbearia",
        "Recebemos um pedido para redefinir a senha do painel da barbearia.\n\n"
        f"Para criar uma nova senha, abra o link abaixo (vale por {settings.reset_token_minutes} minutos e só pode ser usado uma vez):\n\n"
        f"{link}\n\n"
        "Se não foi você, ignore este e-mail: a sua senha continua a mesma.",
    )
