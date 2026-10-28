"""Middleware: id por requisição, log de acesso e captura de erros inesperados."""
import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.logging import request_id_var

logger = logging.getLogger("app.http")


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
