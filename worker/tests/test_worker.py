"""
Tests for the worker callback function.
"""
from worker import callback
import pytest
import json
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWorkerCallback:
    """Test the worker callback function."""

    def create_mock_channel(self):
        """Create a mock channel with basic_ack."""
        channel = MagicMock()
        channel.basic_ack = MagicMock()
        return channel

    def create_mock_method(self, delivery_tag=1):
        """Create a mock method with delivery_tag."""
        method = MagicMock()
        method.delivery_tag = delivery_tag
        return method

    def create_message(self, event_type, data):
        """Create a RabbitMQ message body."""
        return json.dumps({
            "event_type": event_type,
            "data": data
        }).encode("utf-8")

    @patch("worker.requests.post")
    @patch("worker.time.sleep")
    def test_ticket_created_event(self, mock_sleep, mock_post):
        """Test processing ticket_created event."""
        mock_post.return_value = MagicMock(status_code=200)

        channel = self.create_mock_channel()
        method = self.create_mock_method()
        body = self.create_message("ticket_created", {
            "id": 1,
            "title": "Test Ticket",
            "status": "open",
            "created_by": "testuser",
            "assigned_to": None
        })

        callback(channel, method, None, body)

        # Verify notification was sent to backend
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["ticket_id"] == 1
        assert call_args[1]["json"]["event_type"] == "ticket_created"
        assert "created by testuser" in call_args[1]["json"]["message"]

        # Verify message was acknowledged
        channel.basic_ack.assert_called_once_with(delivery_tag=1)

    @patch("worker.requests.post")
    @patch("worker.time.sleep")
    def test_ticket_closed_event(self, mock_sleep, mock_post):
        """Test processing ticket_closed event."""
        mock_post.return_value = MagicMock(status_code=200)

        channel = self.create_mock_channel()
        method = self.create_mock_method()
        body = self.create_message("ticket_closed", {
            "id": 2,
            "title": "Closed Ticket",
            "status": "closed",
            "created_by": "user",
            "assigned_to": "support"
        })

        callback(channel, method, None, body)

        call_args = mock_post.call_args
        assert "closed" in call_args[1]["json"]["message"].lower()
        channel.basic_ack.assert_called_once()

    @patch("worker.requests.post")
    @patch("worker.time.sleep")
    def test_ticket_status_changed_event(self, mock_sleep, mock_post):
        """Test processing ticket_status_changed event."""
        mock_post.return_value = MagicMock(status_code=200)

        channel = self.create_mock_channel()
        method = self.create_mock_method()
        body = self.create_message("ticket_status_changed", {
            "id": 3,
            "title": "Status Changed",
            "status": "in_progress",
            "created_by": "user",
            "assigned_to": "support"
        })

        callback(channel, method, None, body)

        call_args = mock_post.call_args
        assert "in_progress" in call_args[1]["json"]["message"]
        channel.basic_ack.assert_called_once()

    @patch("worker.requests.post")
    @patch("worker.time.sleep")
    def test_ticket_assigned_event(self, mock_sleep, mock_post):
        """Test processing ticket_assigned event."""
        mock_post.return_value = MagicMock(status_code=200)

        channel = self.create_mock_channel()
        method = self.create_mock_method()
        body = self.create_message("ticket_assigned", {
            "id": 4,
            "title": "Assigned Ticket",
            "status": "open",
            "created_by": "user",
            "assigned_to": "support_agent"
        })

        callback(channel, method, None, body)

        call_args = mock_post.call_args
        assert "support_agent" in call_args[1]["json"]["message"]
        channel.basic_ack.assert_called_once()

    @patch("worker.requests.post")
    @patch("worker.time.sleep")
    def test_ticket_deleted_event(self, mock_sleep, mock_post):
        """Test processing ticket_deleted event."""
        mock_post.return_value = MagicMock(status_code=200)

        channel = self.create_mock_channel()
        method = self.create_mock_method()
        body = self.create_message("ticket_deleted", {
            "id": 5,
            "title": "Deleted Ticket",
            "status": "open",
            "created_by": "user",
            "assigned_to": None
        })

        callback(channel, method, None, body)

        call_args = mock_post.call_args
        assert "deleted" in call_args[1]["json"]["message"].lower()
        channel.basic_ack.assert_called_once()

    @patch("worker.requests.post")
    @patch("worker.time.sleep")
    def test_unknown_event_type(self, mock_sleep, mock_post):
        """Test processing unknown event type."""
        mock_post.return_value = MagicMock(status_code=200)

        channel = self.create_mock_channel()
        method = self.create_mock_method()
        body = self.create_message("unknown_event", {
            "id": 6,
            "title": "Unknown",
            "status": "open",
            "created_by": "user",
            "assigned_to": None
        })

        callback(channel, method, None, body)

        call_args = mock_post.call_args
        assert "unknown" in call_args[1]["json"]["message"].lower()
        channel.basic_ack.assert_called_once()

    @patch("worker.requests.post")
    @patch("worker.time.sleep")
    def test_backend_api_failure(self, mock_sleep, mock_post):
        """Test handling backend API failure."""
        mock_post.return_value = MagicMock(
            status_code=500, text="Internal Server Error")

        channel = self.create_mock_channel()
        method = self.create_mock_method()
        body = self.create_message("ticket_created", {
            "id": 7,
            "title": "Test",
            "status": "open",
            "created_by": "user",
            "assigned_to": None
        })

        # Should not raise exception even if backend fails
        callback(channel, method, None, body)

        # Message should still be acknowledged
        channel.basic_ack.assert_called_once()

    @patch("worker.requests.post")
    @patch("worker.time.sleep")
    def test_backend_connection_error(self, mock_sleep, mock_post):
        """Test handling backend connection error."""
        mock_post.side_effect = Exception("Connection refused")

        channel = self.create_mock_channel()
        method = self.create_mock_method()
        body = self.create_message("ticket_created", {
            "id": 8,
            "title": "Test",
            "status": "open",
            "created_by": "user",
            "assigned_to": None
        })

        # Should not raise exception
        callback(channel, method, None, body)

        # Message should still be acknowledged
        channel.basic_ack.assert_called_once()

    @patch("worker.requests.post")
    @patch("worker.time.sleep")
    def test_invalid_json_message(self, mock_sleep, mock_post):
        """Test handling invalid JSON message."""
        channel = self.create_mock_channel()
        method = self.create_mock_method()
        body = b"not valid json"

        # Should not raise exception (error is caught)
        callback(channel, method, None, body)

        # Message should NOT be acknowledged (will be redelivered)
        channel.basic_ack.assert_not_called()

    @patch("worker.requests.post")
    @patch("worker.time.sleep")
    def test_missing_ticket_id(self, mock_sleep, mock_post):
        """Test handling message without ticket_id."""
        mock_post.return_value = MagicMock(status_code=200)

        channel = self.create_mock_channel()
        method = self.create_mock_method()
        body = self.create_message("ticket_created", {
            "title": "Test",
            "status": "open",
            "created_by": "user"
            # Missing "id" field
        })

        callback(channel, method, None, body)

        # Notification should not be sent (no ticket_id)
        mock_post.assert_not_called()

        # Message should still be acknowledged
        channel.basic_ack.assert_called_once()
