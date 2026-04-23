import os
import json
import pika

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "user")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "password")
QUEUE_NAME = "ticket_events"


def publish_ticket_event(event_type: str, payload: dict):
    """
    Send a message to RabbitMQ with info about a ticket event.

    event_type: e.g. "ticket_created", "ticket_closed"
    payload: dict with fields like id, title, status, created_by, assigned_to
    """
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            credentials=credentials,
        )
    )
    channel = connection.channel()

    # Ensure queue exists
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    message = {
        "event_type": event_type,
        "data": payload,
    }

    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(message).encode("utf-8"),
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
        ),
    )

    connection.close()
