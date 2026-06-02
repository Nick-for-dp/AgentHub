from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _lazy_init() -> tuple[Engine, sessionmaker]:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return _engine, _SessionLocal


def get_db() -> Generator[Session, None, None]:
    _, session_factory = _lazy_init()
    db: Session = session_factory()
    try:
        yield db
    finally:
        db.close()
