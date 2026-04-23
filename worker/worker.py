import os
import json
import time
import pika
import requests
from pika.exceptions import AMQPConnectionError

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "user")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "password")
QUEUE_NAME = "ticket_events"
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")


def connect():
    """Try to connect to RabbitMQ with retries."""
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)

    while True:
        try:
            print(
                f"[Worker] Trying to connect to RabbitMQ at {RABBITMQ_HOST} as {RABBITMQ_USER}...")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    credentials=credentials,
                )
            )
            print("[Worker] Connected to RabbitMQ")
            return connection
        except Exception as e:
            print(f"[Worker] Connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)
            time.sleep(5)


def callback(ch, method, properties, body):
    try:
        message = json.loads(body.decode("utf-8"))
        event_type = message.get("event_type")
        data = message.get("data", {})

        ticket_id = data.get("id")
        title = data.get("title")
        status = data.get("status")
        created_by = data.get("created_by")
        assigned_to = data.get("assigned_to")

        print("------------------------------------------------")
        print(f"[Worker] Received event: {event_type}")
        print(f"  Ticket #{ticket_id} - {title}")
        print(f"  Status: {status}")
        print(f"  Created by: {created_by}")
        print(f"  Assigned to: {assigned_to}")

        # Generate notification message based on event type
        if event_type == "ticket_created":
            notification_msg = f"Ticket created by {created_by}"
            print("  Action: notify support team about NEW ticket")
        elif event_type == "ticket_closed":
            notification_msg = f"Ticket closed (was created by {created_by})"
            print("  Action: send email to client about CLOSED ticket")
        elif event_type == "ticket_status_changed":
            notification_msg = f"Status changed to '{status}'"
            print("  Action: notify client/support about STATUS CHANGE")
        elif event_type == "ticket_assigned":
            notification_msg = f"Ticket assigned to {assigned_to}"
            print("  Action: notify ASSIGNEE about new ticket assignment")
        elif event_type == "ticket_deleted":
            notification_msg = f"Ticket was deleted"
            print("  Action: notify stakeholders that ticket was DELETED")
        else:
            notification_msg = f"Unknown event: {event_type}"
            print("  Action: (unknown event type)")

        # Save notification to database via backend API
        if ticket_id:
            try:
                payload = {
                    "ticket_id": ticket_id,
                    "event_type": event_type,
                    "message": notification_msg,
                }
                resp = requests.post(
                    f"{BACKEND_URL}/notifications", json=payload, timeout=10)
                if resp.status_code == 200:
                    print(f"  [DB] Notification saved for ticket #{ticket_id}")
                else:
                    print(
                        f"  [DB] Failed to save notification: {resp.status_code} {resp.text}")
            except Exception as e:
                print(f"  [DB] Error saving notification: {e}")

        print("------------------------------------------------")

        time.sleep(1)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"[Worker] Error processing message: {e}")
        # no ack -> message will be redelivered


def main():
    connection = connect()
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    print("[Worker] Waiting for messages. To exit press CTRL+C")
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("Stopping worker...")
        channel.stop_consuming()
        connection.close()


if __name__ == "__main__":
    main()
