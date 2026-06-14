from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    avatar_style: str = "default"
    plan: str = "free"
    created_at: Optional[datetime] = None


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    avatar_style: Optional[str] = None
