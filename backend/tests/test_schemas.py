"""
Tests for schema validation.
"""
import pytest
from pydantic import ValidationError
from app import schemas


class TestTicketSchemas:
    """Test ticket schemas."""

    def test_ticket_create_valid(self):
        """Test valid ticket creation schema."""
        ticket = schemas.TicketCreate(
            title="Test Ticket",
            description="Test Description",
            created_by="user"
        )
        assert ticket.title == "Test Ticket"
        assert ticket.description == "Test Description"
        assert ticket.created_by == "user"

    def test_ticket_create_missing_fields(self):
        """Test ticket creation with missing required fields."""
        with pytest.raises(ValidationError):
            # Missing description and created_by
            schemas.TicketCreate(title="Test")

    def test_ticket_update_partial(self):
        """Test partial ticket update schema."""
        update = schemas.TicketUpdate(status="closed")
        assert update.status == "closed"
        assert update.assigned_to is None

    def test_ticket_update_all_fields(self):
        """Test ticket update with all fields."""
        update = schemas.TicketUpdate(
            status="in_progress",
            assigned_to="support_user"
        )
        assert update.status == "in_progress"
        assert update.assigned_to == "support_user"


class TestUserSchemas:
    """Test user schemas."""

    def test_user_create_valid(self):
        """Test valid user creation schema."""
        user = schemas.UserCreate(
            username="testuser",
            email="test@example.com",
            password="password123",
            first_name="Test",
            last_name="User"
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password == "password123"

    def test_user_create_minimal(self):
        """Test user creation with minimal fields."""
        user = schemas.UserCreate(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        assert user.first_name is None
        assert user.last_name is None

    def test_support_user_create_valid(self):
        """Test valid support user creation schema."""
        user = schemas.SupportUserCreate(
            username="supportuser",
            email="support@example.com",
            password="password123"
        )
        assert user.username == "supportuser"


class TestNotificationSchemas:
    """Test notification schemas."""

    def test_notification_create_valid(self):
        """Test valid notification creation schema."""
        notification = schemas.NotificationCreate(
            ticket_id=1,
            event_type="ticket_created",
            message="Ticket was created"
        )
        assert notification.ticket_id == 1
        assert notification.event_type == "ticket_created"
        assert notification.message == "Ticket was created"

    def test_notification_create_missing_fields(self):
        """Test notification creation with missing fields."""
        with pytest.raises(ValidationError):
            # Missing event_type and message
            schemas.NotificationCreate(ticket_id=1)
