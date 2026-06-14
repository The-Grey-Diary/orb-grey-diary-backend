"""
Task endpoints called by Cloud Scheduler.
Protected by x-scheduler-secret header.
"""
from fastapi import APIRouter, Header, HTTPException
from datetime import datetime
import pytz

from app.core.config import settings
from app.core.database import get_supabase

router = APIRouter()
IST = pytz.timezone("Asia/Kolkata")


def verify(x_scheduler_secret: str = Header(None)):
    if x_scheduler_secret != settings.SCHEDULER_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/tasks/auto-reveal")
async def auto_reveal(x_scheduler_secret: str = Header(None)):
    verify(x_scheduler_secret)
    db = get_supabase()
    if not db:
        return {"ok": False, "reason": "db not configured"}
    try:
        await db.rpc("auto_reveal_capsules").execute()
    except Exception as e:
        # Fallback: manual update
        now = datetime.now(IST).isoformat()
        db.table("capsules").update({
            "status": "revealed",
            "revealed_at": now,
        }).eq("status", "sealed").lte("reveal_date", now).execute()
    return {"ok": True, "ran_at": datetime.now(IST).isoformat()}


@router.post("/tasks/court-selection")
async def court_selection(x_scheduler_secret: str = Header(None)):
    verify(x_scheduler_secret)
    db = get_supabase()
    if not db:
        return {"ok": False, "reason": "db not configured"}
    import random
    from datetime import timedelta

    tomorrow = datetime.now(IST).date() + timedelta(days=1)
    tomorrow_10pm = IST.localize(datetime(tomorrow.year, tomorrow.month, tomorrow.day, 22, 0, 0))

    existing = db.table("court_sessions").select("id")         .gte("scheduled_for", tomorrow_10pm.isoformat()).execute()
    if existing.data:
        return {"ok": True, "note": "already scheduled"}

    used = db.table("court_sessions").select("capsule_id").execute()
    used_ids = [r["capsule_id"] for r in (used.data or [])]
    q = db.table("capsules").select("id").eq("status", "revealed").eq("is_public", True).limit(20)
    candidates = q.execute()
    available = [c for c in (candidates.data or []) if c["id"] not in used_ids]
    if not available:
        return {"ok": False, "reason": "no candidates"}
    chosen = random.choice(available)
    db.table("court_sessions").insert({
        "capsule_id": chosen["id"],
        "scheduled_for": tomorrow_10pm.isoformat(),
        "status": "pending",
    }).execute()
    return {"ok": True, "capsule_id": chosen["id"]}


@router.post("/tasks/court-activation")
async def court_activation(x_scheduler_secret: str = Header(None)):
    verify(x_scheduler_secret)
    db = get_supabase()
    if not db:
        return {"ok": False, "reason": "db not configured"}
    today = datetime.now(IST).strftime("%Y-%m-%d")
    session = db.table("court_sessions").select("id")         .gte("scheduled_for", f"{today}T22:00:00")         .lt("scheduled_for", f"{today}T23:59:59")         .eq("status", "pending").execute()
    if session.data:
        db.table("court_sessions").update({"status": "active"})             .eq("id", session.data[0]["id"]).execute()
    return {"ok": True}


@router.post("/tasks/weekly-guardian")
async def weekly_guardian(x_scheduler_secret: str = Header(None)):
    verify(x_scheduler_secret)
    from app.services.guardian_service import GuardianService
    report = await GuardianService.generate_weekly_chronicle()
    return {"ok": True, "report_id": str(report.get("id", "")) if report else None}
