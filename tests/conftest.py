"""Pytest fixtures and configuration.

Uses an in-memory SQLite database via StaticPool and FastAPI dependency override.
"""

from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

import app.models
from app.database import Base, get_db
from app.main import app
from app.services.seed import seed_database

import os

# Database URL for testing: defaults to thread-safe in-memory SQLite, or can be set to MySQL via TEST_DATABASE_URL
DEFAULT_SQLITE_URL = "sqlite:///file:cineverse_test_db?mode=memory&cache=shared&uri=true"
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", DEFAULT_SQLITE_URL)

from sqlalchemy import event

if TEST_DATABASE_URL.startswith("sqlite"):
    test_engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 15},
        poolclass=QueuePool,
    )
    _keepalive_conn = test_engine.connect()

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout = 15000")
        cursor.close()
else:
    test_engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    )
    _keepalive_conn = None

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all schema tables and populate seed data once per test session."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    seed_database(session, target_engine=test_engine)
    session.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a database session for tests."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """TestClient configured with SQLite database dependency override."""
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
