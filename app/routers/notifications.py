from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.auth import get_current_user

router = APIRouter()


class PushSub(BaseModel):
    endpoint: str
    p256dh: str | None = None
    auth: str | None = None


@router.post("/subscribe")
async def subscribe(payload: PushSub, current_user: dict = Depends(get_current_user)):
    # Store push subscription (implement with Supabase)
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(current_user: dict = Depends(get_current_user)):
    return {"ok": True}
