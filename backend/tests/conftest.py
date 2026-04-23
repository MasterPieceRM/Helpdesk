"""
Pytest fixtures for backend tests.
Uses SQLite in-memory database for testing.
"""
from app.auth import CurrentUser, get_current_user
from app.deps import get_db
from app.db import Base
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, MagicMock

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for tests."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Mock users for different roles
def create_mock_user(username: str, roles: list) -> CurrentUser:
    """Create a mock CurrentUser for testing."""
    return CurrentUser(username=username, roles=roles)


@pytest.fixture
def test_db():
    """Create test database tables."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db):
    """Get a test database session."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_db):
    """Create a test client with mocked dependencies."""
    # Import app here to avoid circular imports
    from app.main import app

    # Remove startup event to avoid database connection
    app.router.on_startup = []

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(test_db):
    """Create a test client authenticated as admin."""
    from app.main import app

    # Remove startup event
    app.router.on_startup = []

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: create_mock_user("admin", [
                                                                          "admin"])

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def support_client(test_db):
    """Create a test client authenticated as support."""
    from app.main import app

    # Remove startup event
    app.router.on_startup = []

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: create_mock_user(
        "support_user", ["support"])

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def client_user_client(test_db):
    """Create a test client authenticated as client."""
    from app.main import app

    # Remove startup event
    app.router.on_startup = []

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: create_mock_user(
        "client_user", ["client"])

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_messaging():
    """Mock the messaging module to avoid RabbitMQ calls."""
    with patch("app.main.messaging") as mock:
        mock.publish_ticket_event = MagicMock()
        yield mock


@pytest.fixture
def mock_cache():
    """Mock the cache module to avoid Redis calls."""
    with patch("app.main.cache") as mock:
        mock.get_ticket_list_from_cache = MagicMock(return_value=None)
        mock.set_ticket_list_cache = MagicMock()
        mock.invalidate_ticket_list_cache = MagicMock()
        yield mock


@pytest.fixture
def mock_keycloak():
    """Mock the keycloak_admin module."""
    with patch("app.main.keycloak_admin") as mock:
        mock.create_user = MagicMock(
            return_value=(True, "User created successfully"))
        yield mock
