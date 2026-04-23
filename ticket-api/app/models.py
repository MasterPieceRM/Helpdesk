from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from .db import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    # open / in_progress / closed
    status = Column(String(50), nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(100), nullable=False, default="anonymous")
    assigned_to = Column(String(100), nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey(
        "tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
