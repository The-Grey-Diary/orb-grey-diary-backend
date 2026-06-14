from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CapsuleCreate(BaseModel):
    title: str
    content: str
    category: str
    mood: str
    reveal_date: datetime
    is_public: bool = True
    status: str = "draft"


class CapsuleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    mood: Optional[str] = None
    reveal_date: Optional[datetime] = None
    is_public: Optional[bool] = None


class CapsuleSeal(BaseModel):
    reveal_date: datetime


class CapsuleOut(BaseModel):
    id: str
    user_id: str
    title: str
    content: str
    category: str
    mood: str
    reveal_date: datetime
    status: str
    is_public: bool
    view_count: int = 0
    sealed_at: Optional[datetime] = None
    revealed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class CapsuleListOut(BaseModel):
    items: List[CapsuleOut]
    total: int
    page: int
    per_page: int
    has_more: bool


class CapsuleStats(BaseModel):
    total_sealed: int = 0
    total_revealed: int = 0
    total_users: int = 0
    revealing_tonight: int = 0


class EchoCreate(BaseModel):
    content: str
    mood: Optional[str] = None
