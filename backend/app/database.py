"""SQLAlchemy 2.0 sync engine + session factory.

Why sync? FastAPI supports both. Sync is simpler for sprint pace and works
fine at the scale of a single research workstation. We can swap to
async (`sqlite+aiosqlite` or `postgresql+asyncpg`) later without changing the
ORM models — only the engine/session-maker need new signatures.

Migrations: `Base.metadata.create_all(engine)` on startup is good enough for
dev. Alembic is deferred to the hardening sprint.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import REPO_ROOT


DB_DIR = REPO_ROOT / "data"
DB_PATH = DB_DIR / "neuratriage.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"


def _make_engine() -> Engine:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        future=True,
    )


engine: Engine = _make_engine()
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables on first run. Idempotent — safe to call repeatedly."""
    from . import models  # noqa: F401  -- ensures all mappers are registered

    models.Base.metadata.create_all(bind=engine)
