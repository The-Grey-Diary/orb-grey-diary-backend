from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.core.database import get_supabase

router = APIRouter()


@router.get("/weekly")
async def get_weekly_chronicle():
    db = get_supabase()
    if not db:
        return {"content": "The Grey Guardian is awakening...", "week_start": None}
    result = db.table("guardian_reports")         .select("*")         .order("week_start", desc=True)         .limit(1).execute()
    if result.data:
        return result.data[0]
    return {"content": "The first chronicle is being written...", "week_start": None}


@router.get("/weekly/archive")
async def get_guardian_archive(page: int = 1):
    db = get_supabase()
    if not db:
        return {"items": [], "page": page}
    result = db.table("guardian_reports")         .select("*")         .order("week_start", desc=True)         .range((page-1)*10, page*10-1).execute()
    return {"items": result.data or [], "page": page}


@router.get("/personal")
async def get_personal_report(current_user: dict = Depends(get_current_user)):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    result = db.table("personal_reports")         .select("*")         .eq("user_id", current_user["sub"])         .order("generated_at", desc=True)         .limit(1).execute()
    if result.data:
        return result.data[0]
    return {"content": "Your Personal Guardian will speak after you seal more stories.", "capsule_count": 0}


@router.post("/personal/generate")
async def generate_personal_report(current_user: dict = Depends(get_current_user)):
    from app.services.guardian_service import GuardianService
    content = await GuardianService.generate_personal_report(current_user["sub"])
    return {"content": content}
