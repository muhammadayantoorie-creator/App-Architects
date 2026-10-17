"""SQLAlchemy engine, session factory, and declarative base."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://app:app@db:5432/app"
)
if DATABASE_URL.startswith("sqlite"):
    # Test runs only (tests/conftest.py); production uses PostgreSQL.
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30}
    )
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=20, max_overflow=20)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def create_all() -> None:
    Base.metadata.create_all(bind=engine)
