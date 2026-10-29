"""Localização aproximada (cidade/estado/país) a partir do IP. Nunca derruba o cadastro: se falhar, devolve texto neutro.

Atenção: consultar um serviço externo envia o IP de quem se cadastra a esse serviço (avisado no formulário).
"""
import ipaddress
import logging

import requests

from app.core.config import settings

logger = logging.getLogger("app.geoip")
UNKNOWN = "localização indisponível"


def describe_location(ip: str | None) -> str:
    if not ip:
        return UNKNOWN
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return UNKNOWN
    if addr.is_private or addr.is_loopback or addr.is_link_local:
        return "rede local (sem localização: teste no seu computador)"
    if not settings.geoip_url:
        return UNKNOWN
    try:
        r = requests.get(settings.geoip_url.format(ip=ip), timeout=4, headers={"User-Agent": "agenda-painel"})
        data = r.json() if r.ok else {}
    except Exception:
        logger.warning("consulta de localizacao falhou")   # sem detalhes: a URL/resposta podem conter o IP
        return UNKNOWN
    if not isinstance(data, dict) or data.get("error"):
        return UNKNOWN
    parts = [data.get("city"), data.get("region"), data.get("country_name") or data.get("country")]
    text = ", ".join(str(p).strip() for p in parts if p and str(p).strip())
    return f"{text} (aproximado, pelo IP)" if text else UNKNOWN
