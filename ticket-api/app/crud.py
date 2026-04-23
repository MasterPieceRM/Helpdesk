from sqlalchemy.orm import Session
from . import models, schemas


def get_tickets(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Ticket).offset(skip).limit(limit).all()


def create_ticket(db: Session, ticket: schemas.TicketCreate):
    db_ticket = models.Ticket(
        title=ticket.title,
        description=ticket.description,
        created_by=ticket.created_by
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket


def update_ticket(db: Session, ticket_id: int, ticket_update: schemas.TicketUpdate):
    db_ticket = db.query(models.Ticket).filter(
        models.Ticket.id == ticket_id).first()
    if not db_ticket:
        return None
    if ticket_update.status is not None:
        db_ticket.status = ticket_update.status
    if ticket_update.assigned_to is not None:
        db_ticket.assigned_to = ticket_update.assigned_to
    db.commit()
    db.refresh(db_ticket)
    return db_ticket


def delete_ticket(db: Session, ticket_id: int):
    ticket = db.query(models.Ticket).filter(
        models.Ticket.id == ticket_id).first()
    if not ticket:
        return None
    db.delete(ticket)
    db.commit()
    return ticket


def get_ticket(db: Session, ticket_id: int):
    return db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()


def get_tickets_by_creator(db: Session, username: str):
    return (
        db.query(models.Ticket)
        .filter(models.Ticket.created_by == username)
        .all()
    )


def get_tickets_by_assignee(db: Session, username: str):
    return (
        db.query(models.Ticket)
        .filter(models.Ticket.assigned_to == username)
        .all()
    )


# Notification CRUD operations
def create_notification(db: Session, notification: schemas.NotificationCreate):
    db_notification = models.Notification(
        ticket_id=notification.ticket_id,
        event_type=notification.event_type,
        message=notification.message,
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification


def get_notifications_by_ticket(db: Session, ticket_id: int):
    return (
        db.query(models.Notification)
        .filter(models.Notification.ticket_id == ticket_id)
        .order_by(models.Notification.created_at.desc())
        .all()
    )
