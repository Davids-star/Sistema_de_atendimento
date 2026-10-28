"""Verificação do token (ID token) que o Google entrega ao navegador no login."""
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import settings

_request = google_requests.Request()


def verify_google_token(credential: str) -> dict:
    """Confere assinatura, validade e se o token foi emitido para o NOSSO client id.

    Devolve os dados da conta (sub, email, email_verified, name...). Lança ValueError se inválido.
    """
    return id_token.verify_oauth2_token(credential, _request, settings.google_client_id)
