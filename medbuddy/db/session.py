"""Engine + session factory. SQLite by default; DATABASE_URL swaps to Postgres."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from medbuddy.config import get_settings

_settings = get_settings()

# check_same_thread only applies to SQLite; harmless to compute unconditionally.
_connect_args = (
    {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(_settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create all tables. Fine for a PoC; swap for Alembic if this ever goes further."""
    from medbuddy.db.models import Base

    Base.metadata.create_all(engine)
