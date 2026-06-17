from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.core.database import get_db
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    avatar_style: Optional[str] = None

@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    db = get_db()
    if not db: return user
    r = db.table("users").select("*").eq("id", user["sub"]).single().execute()
    return r.data or user

@router.put("/me")
async def update(payload: UserUpdate, user: dict = Depends(get_current_user)):
    db = get_db()
    if not db: raise HTTPException(503, "DB not configured")
    data = {k:v for k,v in payload.model_dump().items() if v is not None}
    r = db.table("users").update(data).eq("id", user["sub"]).execute()
    return r.data[0] if r.data else {}

@router.get("/{user_id}")
async def get_user(user_id: str):
    db = get_db()
    if not db: raise HTTPException(503, "DB not configured")
    r = db.table("users").select("id,display_name,avatar_style,plan,created_at").eq("id", user_id).single().execute()
    if not r.data: raise HTTPException(404, "Not found")
    return r.data
