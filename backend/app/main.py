from fastapi import APIRouter, FastAPI

from app.api import health
from app.api.v1 import appointments, auth, clients, dashboard, schedule, services, users
from fastapi.responses import JSONResponse

from app.core.logging import setup_logging
from app.core.middleware import rate_limiting, request_logging
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.services.appointments import AppointmentError

setup_logging()

app = FastAPI(title="Agendamento", version="0.1.0")
# Ordem: o último registrado fica por fora. CORS por fora de tudo para que até as respostas 429 o tenham.
app.middleware("http")(rate_limiting)
app.middleware("http")(request_logging)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Request-ID", "Retry-After"],
)
app.include_router(health.router)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
api_v1.include_router(services.router)
api_v1.include_router(clients.router)
api_v1.include_router(schedule.router)
api_v1.include_router(appointments.router)
api_v1.include_router(dashboard.router)
api_v1.include_router(users.router)
app.include_router(api_v1)


@app.exception_handler(AppointmentError)
def appointment_error_handler(_, exc: AppointmentError):
    return JSONResponse({"detail": exc.message}, status_code=exc.status_code)
