from __future__ import annotations

import threading
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine_options: dict[str, object] = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options["pool_recycle"] = 1800

engine: Engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

_schema_lock = threading.Lock()
_schema_ready = False


def ensure_schema() -> None:
    """Verify the configured database and create only this application's tables."""
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        # Import registers every model before create_all.
        import app.models  # noqa: F401

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        Base.metadata.create_all(bind=engine)
        _schema_ready = True


def database_status() -> tuple[bool, str | None]:
    try:
        ensure_schema()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except SQLAlchemyError as exc:
        # Never expose a URL (and therefore a password) in the API response.
        return False, f"{exc.__class__.__name__}: no fue posible conectar con MySQL"


def get_db() -> Generator[Session, None, None]:
    ensure_schema()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
