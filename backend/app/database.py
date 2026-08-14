from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base


def engine():
    return create_engine(settings().database_url, connect_args={"check_same_thread": False} if settings().database_url.startswith("sqlite") else {})


SessionLocal = sessionmaker(bind=engine(), expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine())


def session():
    with SessionLocal() as db:
        yield db
