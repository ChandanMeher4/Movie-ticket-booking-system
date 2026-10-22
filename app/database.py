"""Database session and engine management.

Provides SQLAlchemy 2.0 engine, declarative base, and dependency injection session generator.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

connect_args = {}
if settings.sync_database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    connect_args["charset"] = "utf8mb4"

engine = create_engine(
    settings.sync_database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and safely closes it."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
