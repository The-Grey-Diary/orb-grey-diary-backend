from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.core.database import get_supabase
from app.schemas.capsule import EchoCreate
from datetime import datetime, timezone

router = APIRouter()


@router.post("/{capsule_id}/echo", status_code=201)
async def add_echo(
    capsule_id: str,
    payload: EchoCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    capsule = db.table("capsules").select("status,user_id")         .eq("id", capsule_id).single().execute()
    if not capsule.data:
        raise HTTPException(status_code=404, detail="Capsule not found")
    if capsule.data["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Not your capsule")
    if capsule.data["status"] != "revealed":
        raise HTTPException(status_code=403, detail="Capsule not yet revealed")
    result = db.table("capsule_echoes").upsert({
        "capsule_id": capsule_id,
        "content": payload.content,
        "mood": payload.mood,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="capsule_id").execute()
    return result.data[0] if result.data else {}


@router.put("/{capsule_id}/echo")
async def update_echo(
    capsule_id: str,
    payload: EchoCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    result = db.table("capsule_echoes").update({
        "content": payload.content,
        "mood": payload.mood,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("capsule_id", capsule_id).execute()
    return result.data[0] if result.data else {}
