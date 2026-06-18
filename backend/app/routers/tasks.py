from fastapi import APIRouter, Header, HTTPException
from datetime import datetime
import pytz
from app.core.config import settings
from app.core.database import get_db

router = APIRouter()
IST = pytz.timezone("Asia/Kolkata")

def verify(x_scheduler_secret:str=Header(None)):
    if x_scheduler_secret != settings.SCHEDULER_SECRET: raise HTTPException(403,"Forbidden")

@router.post("/tasks/auto-reveal")
async def auto_reveal(x_scheduler_secret:str=Header(None)):
    verify(x_scheduler_secret)
    db=get_db()
    if not db: return {"ok":False}
    try:
        now=datetime.now(IST).isoformat()
        db.table("capsules").update({"status":"revealed","revealed_at":now}).eq("status","sealed").lte("reveal_date",now).execute()
        return {"ok":True,"ran_at":now}
    except Exception as e: return {"ok":False,"error":str(e)}

@router.post("/tasks/court-selection")
async def court_selection(x_scheduler_secret:str=Header(None)):
    verify(x_scheduler_secret)
    db=get_db()
    if not db: return {"ok":False}
    import random
    from datetime import timedelta
    try:
        tomorrow=datetime.now(IST).date()+timedelta(days=1)
        t10pm=IST.localize(datetime(tomorrow.year,tomorrow.month,tomorrow.day,22,0))
        if db.table("court_sessions").select("id").gte("scheduled_for",t10pm.isoformat()).execute().data:
            return {"ok":True,"note":"already scheduled"}
        used=[r["capsule_id"] for r in (db.table("court_sessions").select("capsule_id").execute().data or [])]
        cands=[c for c in (db.table("capsules").select("id").eq("status","revealed").eq("is_public",True).limit(20).execute().data or []) if c["id"] not in used]
        if not cands: return {"ok":False,"reason":"no candidates"}
        chosen=random.choice(cands)
        db.table("court_sessions").insert({"capsule_id":chosen["id"],"scheduled_for":t10pm.isoformat(),"status":"pending"}).execute()
        return {"ok":True}
    except Exception as e: return {"ok":False,"error":str(e)}

@router.post("/tasks/court-activation")
async def court_activation(x_scheduler_secret:str=Header(None)):
    verify(x_scheduler_secret)
    db=get_db()
    if not db: return {"ok":False}
    try:
        today=datetime.now(IST).strftime("%Y-%m-%d")
        r=db.table("court_sessions").select("id").gte("scheduled_for",f"{today}T22:00:00").lt("scheduled_for",f"{today}T23:59:59").eq("status","pending").execute()
        if r.data: db.table("court_sessions").update({"status":"active"}).eq("id",r.data[0]["id"]).execute()
        return {"ok":True}
    except Exception as e: return {"ok":False,"error":str(e)}

@router.post("/tasks/weekly-guardian")
async def weekly_guardian(x_scheduler_secret:str=Header(None)):
    verify(x_scheduler_secret)
    try:
        from app.services.guardian_service import GuardianService
        report=await GuardianService.generate_weekly_chronicle()
        return {"ok":True}
    except Exception as e: return {"ok":False,"error":str(e)}
