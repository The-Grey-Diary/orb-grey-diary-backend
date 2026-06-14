from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.core.database import get_supabase
from app.schemas.user import UserUpdate

router = APIRouter()


@router.get("/me")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    db = get_supabase()
    if not db:
        return current_user
    result = db.table("users").select("*").eq("id", current_user["sub"]).single().execute()
    return result.data or current_user


@router.put("/me")
async def update_my_profile(
    payload: UserUpdate,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    result = db.table("users").update(data).eq("id", current_user["sub"]).execute()
    return result.data[0] if result.data else {}


@router.get("/{user_id}")
async def get_user_profile(user_id: str):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    result = db.table("users")         .select("id,display_name,avatar_style,plan,created_at")         .eq("id", user_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return result.data
