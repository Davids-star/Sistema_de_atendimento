from fastapi import APIRouter, FastAPI

from app.api import health
from app.api.v1 import appointments, auth, clients, dashboard, schedule, services
from fastapi.responses import JSONResponse

from app.core.logging import setup_logging
from app.core.middleware import request_logging
from app.services.appointments import AppointmentError

setup_logging()

app = FastAPI(title="Agendamento Barbearia", version="0.1.0")
app.middleware("http")(request_logging)
app.include_router(health.router)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router)
api_v1.include_router(services.router)
api_v1.include_router(clients.router)
api_v1.include_router(schedule.router)
api_v1.include_router(appointments.router)
api_v1.include_router(dashboard.router)
app.include_router(api_v1)


@app.exception_handler(AppointmentError)
def appointment_error_handler(_, exc: AppointmentError):
    return JSONResponse({"detail": exc.message}, status_code=exc.status_code)
