from pydantic import BaseModel
from typing import Optional


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class SupportUserCreate(BaseModel):
    username: str
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
