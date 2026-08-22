from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from .config import get_settings

class Base(DeclarativeBase):
    pass

def _engine():
    url = get_settings().database_url
    args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    options = {"connect_args": args, "pool_pre_ping": True}
    if url == "sqlite://":
        options["poolclass"] = StaticPool
    return create_engine(url, **options)

engine = _engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    from . import models
    Base.metadata.create_all(engine)
