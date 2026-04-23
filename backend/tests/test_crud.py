"""
Tests for CRUD operations.
"""
import pytest
from app import crud, schemas, models


class TestTicketCRUD:
    """Test ticket CRUD operations."""

    def test_create_ticket(self, db_session):
        """Test creating a ticket."""
        ticket_data = schemas.TicketCreate(
            title="Test Ticket",
            description="Test Description",
            created_by="test_user"
        )

        ticket = crud.create_ticket(db_session, ticket_data)

        assert ticket.id is not None
        assert ticket.title == "Test Ticket"
        assert ticket.description == "Test Description"
        assert ticket.created_by == "test_user"
        assert ticket.status == "open"
        assert ticket.assigned_to is None

    def test_get_tickets(self, db_session):
        """Test getting all tickets."""
        # Create some tickets
        for i in range(3):
            ticket_data = schemas.TicketCreate(
                title=f"Ticket {i}",
                description=f"Description {i}",
                created_by="test_user"
            )
            crud.create_ticket(db_session, ticket_data)

        tickets = crud.get_tickets(db_session)

        assert len(tickets) == 3

    def test_get_ticket(self, db_session):
        """Test getting a single ticket by ID."""
        ticket_data = schemas.TicketCreate(
            title="Test Ticket",
            description="Test Description",
            created_by="test_user"
        )
        created = crud.create_ticket(db_session, ticket_data)

        ticket = crud.get_ticket(db_session, created.id)

        assert ticket is not None
        assert ticket.id == created.id
        assert ticket.title == "Test Ticket"

    def test_get_ticket_not_found(self, db_session):
        """Test getting a non-existent ticket."""
        ticket = crud.get_ticket(db_session, 9999)
        assert ticket is None

    def test_update_ticket_status(self, db_session):
        """Test updating ticket status."""
        ticket_data = schemas.TicketCreate(
            title="Test Ticket",
            description="Test Description",
            created_by="test_user"
        )
        created = crud.create_ticket(db_session, ticket_data)

        update_data = schemas.TicketUpdate(status="in_progress")
        updated = crud.update_ticket(db_session, created.id, update_data)

        assert updated.status == "in_progress"

    def test_update_ticket_assignment(self, db_session):
        """Test updating ticket assignment."""
        ticket_data = schemas.TicketCreate(
            title="Test Ticket",
            description="Test Description",
            created_by="test_user"
        )
        created = crud.create_ticket(db_session, ticket_data)

        update_data = schemas.TicketUpdate(assigned_to="support_user")
        updated = crud.update_ticket(db_session, created.id, update_data)

        assert updated.assigned_to == "support_user"

    def test_update_ticket_not_found(self, db_session):
        """Test updating a non-existent ticket."""
        update_data = schemas.TicketUpdate(status="closed")
        updated = crud.update_ticket(db_session, 9999, update_data)
        assert updated is None

    def test_delete_ticket(self, db_session):
        """Test deleting a ticket."""
        ticket_data = schemas.TicketCreate(
            title="Test Ticket",
            description="Test Description",
            created_by="test_user"
        )
        created = crud.create_ticket(db_session, ticket_data)

        deleted = crud.delete_ticket(db_session, created.id)

        assert deleted is not None
        assert deleted.id == created.id

        # Verify it's gone
        assert crud.get_ticket(db_session, created.id) is None

    def test_delete_ticket_not_found(self, db_session):
        """Test deleting a non-existent ticket."""
        deleted = crud.delete_ticket(db_session, 9999)
        assert deleted is None

    def test_get_tickets_by_creator(self, db_session):
        """Test getting tickets by creator."""
        # Create tickets for different users
        for user in ["user1", "user1", "user2"]:
            ticket_data = schemas.TicketCreate(
                title=f"Ticket by {user}",
                description="Description",
                created_by=user
            )
            crud.create_ticket(db_session, ticket_data)

        user1_tickets = crud.get_tickets_by_creator(db_session, "user1")
        user2_tickets = crud.get_tickets_by_creator(db_session, "user2")

        assert len(user1_tickets) == 2
        assert len(user2_tickets) == 1

    def test_get_tickets_by_assignee(self, db_session):
        """Test getting tickets by assignee."""
        # Create and assign tickets
        ticket1 = crud.create_ticket(db_session, schemas.TicketCreate(
            title="Ticket 1", description="Desc", created_by="user"
        ))
        ticket2 = crud.create_ticket(db_session, schemas.TicketCreate(
            title="Ticket 2", description="Desc", created_by="user"
        ))

        crud.update_ticket(db_session, ticket1.id,
                           schemas.TicketUpdate(assigned_to="support1"))
        crud.update_ticket(db_session, ticket2.id,
                           schemas.TicketUpdate(assigned_to="support1"))

        support1_tickets = crud.get_tickets_by_assignee(db_session, "support1")
        support2_tickets = crud.get_tickets_by_assignee(db_session, "support2")

        assert len(support1_tickets) == 2
        assert len(support2_tickets) == 0


class TestNotificationCRUD:
    """Test notification CRUD operations."""

    def test_create_notification(self, db_session):
        """Test creating a notification."""
        # First create a ticket
        ticket = crud.create_ticket(db_session, schemas.TicketCreate(
            title="Test Ticket", description="Desc", created_by="user"
        ))

        notification_data = schemas.NotificationCreate(
            ticket_id=ticket.id,
            event_type="ticket_created",
            message="Ticket created by user"
        )

        notification = crud.create_notification(db_session, notification_data)

        assert notification.id is not None
        assert notification.ticket_id == ticket.id
        assert notification.event_type == "ticket_created"
        assert notification.message == "Ticket created by user"

    def test_get_notifications_by_ticket(self, db_session):
        """Test getting notifications for a ticket."""
        # Create a ticket
        ticket = crud.create_ticket(db_session, schemas.TicketCreate(
            title="Test Ticket", description="Desc", created_by="user"
        ))

        # Create multiple notifications
        for event in ["ticket_created", "ticket_assigned", "ticket_status_changed"]:
            crud.create_notification(db_session, schemas.NotificationCreate(
                ticket_id=ticket.id,
                event_type=event,
                message=f"Event: {event}"
            ))

        notifications = crud.get_notifications_by_ticket(db_session, ticket.id)

        assert len(notifications) == 3

    def test_get_notifications_empty(self, db_session):
        """Test getting notifications for a ticket with no notifications."""
        ticket = crud.create_ticket(db_session, schemas.TicketCreate(
            title="Test Ticket", description="Desc", created_by="user"
        ))

        notifications = crud.get_notifications_by_ticket(db_session, ticket.id)

        assert len(notifications) == 0
