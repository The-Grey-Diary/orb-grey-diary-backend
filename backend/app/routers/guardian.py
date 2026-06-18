from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.core.database import get_db

router = APIRouter()

@router.get("/weekly")
async def weekly():
    db=get_db()
    if not db: return {"content":"The Grey Guardian is awakening...","week_start":None}
    r=db.table("guardian_reports").select("*").order("week_start",desc=True).limit(1).execute()
    return r.data[0] if r.data else {"content":"The first chronicle is being written...","week_start":None}

@router.get("/weekly/archive")
async def archive(page:int=1):
    db=get_db()
    if not db: return {"items":[],"page":page}
    r=db.table("guardian_reports").select("*").order("week_start",desc=True).range((page-1)*10,page*10-1).execute()
    return {"items":r.data or [],"page":page}

@router.get("/personal")
async def personal(user:dict=Depends(get_current_user)):
    db=get_db()
    if not db: return {"content":"Your Personal Guardian will speak soon.","capsule_count":0}
    r=db.table("personal_reports").select("*").eq("user_id",user["sub"]).order("generated_at",desc=True).limit(1).execute()
    return r.data[0] if r.data else {"content":"Seal more stories before your Guardian can speak.","capsule_count":0}

@router.post("/personal/generate")
async def gen(user:dict=Depends(get_current_user)):
    from app.services.guardian_service import GuardianService
    content = await GuardianService.generate_personal_report(user["sub"])
    return {"content":content}
