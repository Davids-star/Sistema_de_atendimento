"""Links externos montados com segurança."""
import re
from urllib.parse import quote


def whatsapp_url(phone: str | None, text: str | None = None) -> str | None:
    """Link oficial wa.me com a mensagem pronta. Só aceita número brasileiro com DDI (12-13 dígitos); senão, None."""
    digits = re.sub(r"\D", "", phone or "")
    if not re.fullmatch(r"55\d{10,11}", digits):
        return None
    return f"https://wa.me/{digits}" + (f"?text={quote(text, safe='')}" if text else "")
