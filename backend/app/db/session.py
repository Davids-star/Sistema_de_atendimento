"""Conexão com o PostgreSQL e sessão por requisição."""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """Classe base de todos os modelos."""


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
