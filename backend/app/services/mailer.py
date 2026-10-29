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
        f"Redefinição de senha - {settings.business_name}",
        "Recebemos um pedido para redefinir a senha do painel de agendamentos.\n\n"
        f"Para criar uma nova senha, abra o link abaixo (vale por {settings.reset_token_minutes} minutos e só pode ser usado uma vez):\n\n"
        f"{link}\n\n"
        "Se não foi você, ignore este e-mail: a sua senha continua a mesma.",
    )


def send_verification_email(to: str, raw_token: str) -> None:
    link = f"{settings.frontend_url.rstrip('/')}/confirmar-email?token={raw_token}"
    send_mail(
        to,
        f"Confirme seu e-mail - {settings.business_name}",
        "Recebemos um cadastro no painel de agendamentos com este e-mail.\n\n"
        f"Para confirmar que ele é seu, abra o link abaixo (vale por {settings.verify_token_hours} horas e só pode ser usado uma vez):\n\n"
        f"{link}\n\n"
        "Depois de confirmar, o dono precisa liberar o seu acesso.\n"
        "Se não foi você, ignore este e-mail: sem a confirmação, essa conta não consegue entrar nem ver nada.",
    )


def send_already_registered_email(to: str) -> None:
    """Quando alguém tenta se cadastrar com um e-mail que já tem conta. Evita revelar isso na tela."""
    link = f"{settings.frontend_url.rstrip('/')}/login"
    send_mail(
        to,
        f"Você já tem uma conta - {settings.business_name}",
        "Alguém tentou criar uma conta no painel de agendamentos com este e-mail, mas ele já está cadastrado.\n\n"
        f"Se foi você, é só entrar: {link}\n"
        "Se esqueceu a senha, use a opção \"Esqueci minha senha\" na tela de entrada.\n\n"
        "Se não foi você, ignore este e-mail.",
    )
