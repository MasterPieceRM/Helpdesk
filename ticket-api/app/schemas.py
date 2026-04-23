from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TicketBase(BaseModel):
    title: str
    description: str


class TicketCreate(TicketBase):
    created_by: str


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None


class TicketOut(TicketBase):
    id: int
    status: str
    created_by: str
    assigned_to: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# User registration schema
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


# Admin creates support user schema
class SupportUserCreate(BaseModel):
    username: str
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


# Notification schemas
class NotificationCreate(BaseModel):
    ticket_id: int
    event_type: str
    message: str


class NotificationOut(BaseModel):
    id: int
    ticket_id: int
    event_type: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True
