from fastapi import APIRouter, FastAPI

from app.api import health
from app.api.v1 import auth, services

app = FastAPI(title="Agendamento Barbearia", version="0.1.0")
app.include_router(health.router)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
api_v1.include_router(services.router)
app.include_router(api_v1)
