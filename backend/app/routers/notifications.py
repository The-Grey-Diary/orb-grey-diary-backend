from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.core.auth import get_current_user

router = APIRouter()
class PushSub(BaseModel): endpoint:str; p256dh:Optional[str]=None; auth_key:Optional[str]=None

@router.post("/subscribe")
async def subscribe(payload:PushSub,user:dict=Depends(get_current_user)): return {"ok":True}
@router.post("/unsubscribe")
async def unsubscribe(user:dict=Depends(get_current_user)): return {"ok":True}
