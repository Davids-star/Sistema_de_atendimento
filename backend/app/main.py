from fastapi import APIRouter, FastAPI

from app.api import health
from app.api.v1 import auth, clients, schedule, services
from app.core.logging import setup_logging
from app.core.middleware import request_logging

setup_logging()

app = FastAPI(title="Agendamento Barbearia", version="0.1.0")
app.middleware("http")(request_logging)
app.include_router(health.router)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
api_v1.include_router(services.router)
api_v1.include_router(clients.router)
api_v1.include_router(schedule.router)
app.include_router(api_v1)
