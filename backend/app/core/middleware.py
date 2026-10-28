"""Middlewares: limite de requisições, id por requisição, log de acesso e captura de erros."""
import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core import rate_limit
from app.core.config import settings
from app.core.logging import request_id_var

logger = logging.getLogger("app.http")

# Fora do limite geral: verificação de saúde e (futuramente) o webhook da Meta, que vem de poucos IPs.
RATE_LIMIT_EXEMPT = ("/health", "/ready", "/webhooks/")


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


async def rate_limiting(request: Request, call_next):
    path = request.url.path
    if settings.rate_limit_per_minute > 0 and not path.startswith(RATE_LIMIT_EXEMPT):
        key = client_ip(request)
        if rate_limit.general.count(key, 60) >= settings.rate_limit_per_minute:
            logger.warning("limite de requisicoes excedido (ip=%s)", key)
            return JSONResponse({"detail": "Muitas requisições. Aguarde um momento."}, status_code=429,
                                headers={"Retry-After": str(rate_limit.general.retry_after(key, 60))})
        rate_limit.general.hit(key, 60)
    return await call_next(request)


async def request_logging(request: Request, call_next):
    rid = uuid.uuid4().hex[:8]
    request_id_var.set(rid)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # Stack trace completo vai para o log; o cliente recebe só o id para você achar a linha.
        logger.exception("ERRO NAO TRATADO %s %s", request.method, request.url.path)
        return JSONResponse({"detail": "Erro interno do servidor", "request_id": rid},
                            status_code=500, headers={"X-Request-ID": rid})
    ms = (time.perf_counter() - start) * 1000
    level = logging.ERROR if response.status_code >= 500 else logging.INFO
    logger.log(level, "%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, ms)
    response.headers["X-Request-ID"] = rid
    return response
