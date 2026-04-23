"""
Tests for API endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client):
        """Test health endpoint returns ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestTicketEndpoints:
    """Test ticket API endpoints."""

    def test_create_ticket_as_admin(self, admin_client, mock_messaging, mock_cache):
        """Test creating a ticket as admin."""
        response = admin_client.post("/tickets", json={
            "title": "Test Ticket",
            "description": "Test Description",
            "created_by": "ignored"  # Should be overwritten by auth
        })

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Ticket"
        assert data["description"] == "Test Description"
        assert data["created_by"] == "admin"  # From mock user
        assert data["status"] == "open"

    def test_create_ticket_as_client(self, client_user_client, mock_messaging, mock_cache):
        """Test creating a ticket as client."""
        response = client_user_client.post("/tickets", json={
            "title": "Client Ticket",
            "description": "Client Description",
            "created_by": "someone_else"
        })

        assert response.status_code == 200
        data = response.json()
        # Forced to authenticated user
        assert data["created_by"] == "client_user"

    def test_list_tickets_as_admin(self, admin_client, mock_messaging, mock_cache):
        """Test listing tickets as admin sees all."""
        # Create some tickets first
        admin_client.post("/tickets", json={
            "title": "Ticket 1",
            "description": "Desc 1",
            "created_by": "user"
        })
        admin_client.post("/tickets", json={
            "title": "Ticket 2",
            "description": "Desc 2",
            "created_by": "user"
        })

        response = admin_client.get("/tickets")

        assert response.status_code == 200
        tickets = response.json()
        assert len(tickets) == 2

    def test_list_tickets_as_client_sees_own(self, client_user_client, mock_messaging, mock_cache):
        """Test client only sees their own tickets."""
        # Client creates a ticket (will be created as client_user)
        client_user_client.post("/tickets", json={
            "title": "Client Ticket",
            "description": "Desc",
            "created_by": "client_user"
        })

        # Create another ticket directly in DB as different user
        from tests.conftest import TestingSessionLocal
        from app import crud, schemas
        db = TestingSessionLocal()
        crud.create_ticket(db, schemas.TicketCreate(
            title="Other User Ticket",
            description="Desc",
            created_by="other_user"
        ))
        db.close()

        # Client should only see their own ticket
        response = client_user_client.get("/tickets")

        assert response.status_code == 200
        tickets = response.json()
        assert len(tickets) == 1
        assert tickets[0]["title"] == "Client Ticket"

    def test_get_ticket_as_admin(self, admin_client, mock_messaging, mock_cache):
        """Test getting a specific ticket as admin."""
        # Create a ticket
        create_response = admin_client.post("/tickets", json={
            "title": "Test Ticket",
            "description": "Desc",
            "created_by": "user"
        })
        ticket_id = create_response.json()["id"]

        response = admin_client.get(f"/tickets/{ticket_id}")

        assert response.status_code == 200
        assert response.json()["id"] == ticket_id

    def test_get_ticket_not_found(self, admin_client):
        """Test getting a non-existent ticket."""
        response = admin_client.get("/tickets/9999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Ticket not found"

    def test_update_ticket_as_admin(self, admin_client, mock_messaging, mock_cache):
        """Test updating a ticket as admin."""
        # Create a ticket
        create_response = admin_client.post("/tickets", json={
            "title": "Test Ticket",
            "description": "Desc",
            "created_by": "user"
        })
        ticket_id = create_response.json()["id"]

        # Update it
        response = admin_client.patch(f"/tickets/{ticket_id}", json={
            "status": "in_progress",
            "assigned_to": "support_user"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"
        assert data["assigned_to"] == "support_user"

    def test_update_ticket_not_found(self, admin_client, mock_messaging, mock_cache):
        """Test updating a non-existent ticket."""
        response = admin_client.patch("/tickets/9999", json={
            "status": "closed"
        })

        assert response.status_code == 404

    def test_delete_ticket_as_admin(self, admin_client, mock_messaging, mock_cache):
        """Test deleting a ticket as admin."""
        # Create a ticket
        create_response = admin_client.post("/tickets", json={
            "title": "Test Ticket",
            "description": "Desc",
            "created_by": "user"
        })
        ticket_id = create_response.json()["id"]

        # Delete it
        response = admin_client.delete(f"/tickets/{ticket_id}")

        assert response.status_code == 200
        assert "deleted" in response.json()["detail"].lower()

        # Verify it's gone
        get_response = admin_client.get(f"/tickets/{ticket_id}")
        assert get_response.status_code == 404

    def test_delete_ticket_not_found(self, admin_client, mock_messaging, mock_cache):
        """Test deleting a non-existent ticket."""
        response = admin_client.delete("/tickets/9999")

        assert response.status_code == 404


class TestNotificationEndpoints:
    """Test notification API endpoints."""

    def test_create_notification(self, admin_client, mock_messaging, mock_cache):
        """Test creating a notification."""
        # Create a ticket first
        create_response = admin_client.post("/tickets", json={
            "title": "Test Ticket",
            "description": "Desc",
            "created_by": "user"
        })
        ticket_id = create_response.json()["id"]

        # Create a notification
        response = admin_client.post("/notifications", json={
            "ticket_id": ticket_id,
            "event_type": "ticket_created",
            "message": "Ticket was created"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["ticket_id"] == ticket_id
        assert data["event_type"] == "ticket_created"

    def test_create_notification_ticket_not_found(self, admin_client):
        """Test creating a notification for non-existent ticket."""
        response = admin_client.post("/notifications", json={
            "ticket_id": 9999,
            "event_type": "test",
            "message": "Test"
        })

        assert response.status_code == 404

    def test_get_ticket_notifications_as_admin(self, admin_client, mock_messaging, mock_cache):
        """Test getting notifications for a ticket as admin."""
        # Create a ticket
        create_response = admin_client.post("/tickets", json={
            "title": "Test Ticket",
            "description": "Desc",
            "created_by": "user"
        })
        ticket_id = create_response.json()["id"]

        # Create notifications
        admin_client.post("/notifications", json={
            "ticket_id": ticket_id,
            "event_type": "ticket_created",
            "message": "Created"
        })
        admin_client.post("/notifications", json={
            "ticket_id": ticket_id,
            "event_type": "ticket_assigned",
            "message": "Assigned"
        })

        # Get notifications
        response = admin_client.get(f"/tickets/{ticket_id}/notifications")

        assert response.status_code == 200
        notifications = response.json()
        assert len(notifications) == 2

    def test_get_ticket_notifications_not_found(self, admin_client):
        """Test getting notifications for non-existent ticket."""
        response = admin_client.get("/tickets/9999/notifications")

        assert response.status_code == 404


class TestMeEndpoint:
    """Test the /me endpoint."""

    def test_me_as_admin(self, admin_client):
        """Test /me endpoint as admin."""
        response = admin_client.get("/me")

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert "admin" in data["roles"]

    def test_me_as_client(self, client_user_client):
        """Test /me endpoint as client."""
        response = client_user_client.get("/me")

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "client_user"
        assert "client" in data["roles"]


class TestRegistrationEndpoint:
    """Test user registration endpoint."""

    def test_register_user_success(self, client, mock_keycloak):
        """Test successful user registration."""
        response = client.post("/register", json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "first_name": "New",
            "last_name": "User"
        })

        assert response.status_code == 200
        assert "message" in response.json()

    def test_register_user_failure(self, client, mock_keycloak):
        """Test failed user registration."""
        mock_keycloak.create_user.return_value = (False, "User already exists")

        response = client.post("/register", json={
            "username": "existinguser",
            "email": "existing@example.com",
            "password": "password123"
        })

        assert response.status_code == 400
        assert "User already exists" in response.json()["detail"]


class TestAdminEndpoints:
    """Test admin-only endpoints."""

    def test_create_support_user_as_admin(self, admin_client, mock_keycloak):
        """Test creating support user as admin."""
        response = admin_client.post("/admin/users/support", json={
            "username": "newsupport",
            "email": "support@example.com",
            "password": "password123",
            "first_name": "Support",
            "last_name": "User"
        })

        assert response.status_code == 200
        assert "created successfully" in response.json()["message"]

    def test_create_support_user_as_client_forbidden(self, client_user_client, mock_keycloak):
        """Test that clients cannot create support users."""
        response = client_user_client.post("/admin/users/support", json={
            "username": "newsupport",
            "email": "support@example.com",
            "password": "password123"
        })

        assert response.status_code == 403
