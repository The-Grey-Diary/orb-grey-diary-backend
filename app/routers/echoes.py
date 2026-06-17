from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone
from app.core.auth import get_current_user
from app.core.database import get_db
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
class EchoIn(BaseModel): content:str; mood:Optional[str]=None

@router.post("/{capsule_id}/echo",status_code=201)
async def add(capsule_id:str,payload:EchoIn,user:dict=Depends(get_current_user)):
    db=get_db()
    if not db: raise HTTPException(503,"DB not configured")
    r=db.table("capsules").select("status,user_id").eq("id",capsule_id).single().execute()
    if not r.data: raise HTTPException(404,"Not found")
    if r.data["user_id"]!=user["sub"]: raise HTTPException(403,"Not yours")
    if r.data["status"]!="revealed": raise HTTPException(403,"Not yet revealed")
    u=db.table("capsule_echoes").upsert({"capsule_id":capsule_id,"content":payload.content,"mood":payload.mood,"updated_at":datetime.now(timezone.utc).isoformat()},on_conflict="capsule_id").execute()
    return u.data[0] if u.data else {}

@router.put("/{capsule_id}/echo")
async def update(capsule_id:str,payload:EchoIn,user:dict=Depends(get_current_user)):
    db=get_db()
    if not db: raise HTTPException(503,"DB not configured")
    u=db.table("capsule_echoes").update({"content":payload.content,"mood":payload.mood,"updated_at":datetime.now(timezone.utc).isoformat()}).eq("capsule_id",capsule_id).execute()
    return u.data[0] if u.data else {}
