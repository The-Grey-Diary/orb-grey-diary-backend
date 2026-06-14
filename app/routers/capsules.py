from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import Optional
from datetime import datetime, timezone
import pytz

from app.core.auth import get_current_user, optional_user
from app.core.database import get_supabase
from app.schemas.capsule import CapsuleCreate, CapsuleUpdate, CapsuleSeal, CapsuleStats

router = APIRouter()
IST = pytz.timezone("Asia/Kolkata")

PLAN_LIMITS = {"free": 3, "plus": 25, "premium": 9999}


@router.get("/stats", response_model=CapsuleStats)
async def community_stats():
    db = get_supabase()
    if not db:
        return CapsuleStats()
    try:
        sealed = db.table("capsules").select("id", count="exact")             .eq("status", "sealed").execute()
        revealed = db.table("capsules").select("id", count="exact")             .eq("status", "revealed").execute()
        users = db.table("users").select("id", count="exact").execute()
        tonight = db.table("capsules").select("id", count="exact")             .eq("status", "sealed")             .lte("reveal_date", datetime.now(IST).strftime("%Y-%m-%dT23:59:59"))             .execute()
        return CapsuleStats(
            total_sealed=sealed.count or 0,
            total_revealed=revealed.count or 0,
            total_users=users.count or 0,
            revealing_tonight=tonight.count or 0,
        )
    except Exception:
        return CapsuleStats()


@router.get("/mine")
async def my_capsules(
    page: int = Query(1, ge=1),
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        return {"items": [], "total": 0, "page": page, "per_page": 20, "has_more": False}
    q = db.table("capsules").select("*").eq("user_id", current_user["sub"])
    if status:
        q = q.eq("status", status)
    result = q.order("created_at", desc=True).range((page-1)*20, page*20-1).execute()
    return {"items": result.data or [], "total": len(result.data or []),
            "page": page, "per_page": 20, "has_more": len(result.data or []) == 20}


@router.get("/")
async def explore_capsules(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    category: Optional[str] = None,
    mood: Optional[str] = None,
    sort: str = Query("recent"),
    current_user: Optional[dict] = Depends(optional_user),
):
    db = get_supabase()
    if not db:
        return {"items": [], "total": 0, "page": page, "per_page": per_page, "has_more": False}
    q = db.table("capsules").select(
        "*, users(display_name, avatar_style)"
    ).eq("status", "revealed").eq("is_public", True)
    if category:
        q = q.eq("category", category)
    if mood:
        q = q.eq("mood", mood)
    q = q.order("revealed_at", desc=True)
    result = q.range((page-1)*per_page, page*per_page-1).execute()
    items = result.data or []
    return {"items": items, "total": len(items), "page": page,
            "per_page": per_page, "has_more": len(items) == per_page}


@router.post("/", status_code=201)
async def create_capsule(
    payload: CapsuleCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")

    # Check plan limit
    user_result = db.table("users").select("plan").eq("id", current_user["sub"]).single().execute()
    plan = user_result.data.get("plan", "free") if user_result.data else "free"
    limit = PLAN_LIMITS.get(plan, 3)
    count_result = db.table("capsules").select("id", count="exact")         .eq("user_id", current_user["sub"]).neq("status", "revealed").execute()
    if (count_result.count or 0) >= limit:
        raise HTTPException(status_code=403, detail=f"Plan limit reached. Upgrade to seal more.")

    data = {
        "user_id": current_user["sub"],
        "title": payload.title,
        "content": payload.content,
        "category": payload.category,
        "mood": payload.mood,
        "reveal_date": payload.reveal_date.isoformat(),
        "status": payload.status,
        "is_public": payload.is_public,
    }
    if payload.status == "sealed":
        data["sealed_at"] = datetime.now(timezone.utc).isoformat()

    result = db.table("capsules").insert(data).execute()
    capsule = result.data[0]

    if payload.status == "sealed":
        from app.services.observer_service import ObserverService
        background_tasks.add_task(
            ObserverService.generate_reflection,
            capsule_id=capsule["id"],
            content=capsule["content"],
            mood=capsule["mood"],
            category=capsule["category"],
        )
    return capsule


@router.get("/{capsule_id}")
async def get_capsule(
    capsule_id: str,
    current_user: Optional[dict] = Depends(optional_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    result = db.table("capsules").select("*").eq("id", capsule_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Capsule not found")
    capsule = result.data
    if capsule["status"] != "revealed":
        if not current_user or current_user["sub"] != capsule["user_id"]:
            raise HTTPException(status_code=403, detail="This capsule is still sealed")
    # Increment view count
    db.table("capsules").update({"view_count": capsule["view_count"] + 1})         .eq("id", capsule_id).execute()
    return capsule


@router.put("/{capsule_id}")
async def update_capsule(
    capsule_id: str,
    payload: CapsuleUpdate,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    result = db.table("capsules").select("*").eq("id", capsule_id).single().execute()
    if not result.data or result.data["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=404, detail="Capsule not found")
    if result.data["status"] != "draft":
        raise HTTPException(status_code=403, detail="Cannot edit a sealed capsule")
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    updated = db.table("capsules").update(data).eq("id", capsule_id).execute()
    return updated.data[0]


@router.delete("/{capsule_id}", status_code=204)
async def delete_capsule(
    capsule_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    result = db.table("capsules").select("status,user_id").eq("id", capsule_id).single().execute()
    if not result.data or result.data["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=404, detail="Not found")
    if result.data["status"] != "draft":
        raise HTTPException(status_code=403, detail="Cannot delete a sealed capsule")
    db.table("capsules").delete().eq("id", capsule_id).execute()


@router.post("/{capsule_id}/seal")
async def seal_capsule(
    capsule_id: str,
    payload: CapsuleSeal,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    result = db.table("capsules").select("*").eq("id", capsule_id).single().execute()
    if not result.data or result.data["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=404, detail="Not found")
    if result.data["status"] != "draft":
        raise HTTPException(status_code=403, detail="Already sealed")
    sealed = db.table("capsules").update({
        "status": "sealed",
        "reveal_date": payload.reveal_date.isoformat(),
        "sealed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", capsule_id).execute()
    background_tasks.add_task(
        __import__("app.services.observer_service", fromlist=["ObserverService"])
        .ObserverService.generate_reflection,
        capsule_id=capsule_id,
        content=result.data["content"],
        mood=result.data["mood"],
        category=result.data["category"],
    )
    return sealed.data[0]


@router.post("/{capsule_id}/react")
async def react(
    capsule_id: str,
    reaction_type: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    if reaction_type not in ("heart", "heartbreak", "fire", "candle"):
        raise HTTPException(status_code=400, detail="Invalid reaction type")
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        db.table("reactions").insert({
            "capsule_id": capsule_id,
            "user_id": current_user["sub"],
            "type": reaction_type,
        }).execute()
    except Exception:
        pass  # duplicate reaction ignored
    return {"ok": True}


@router.delete("/{capsule_id}/react")
async def unreact(
    capsule_id: str,
    reaction_type: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    db.table("reactions").delete()         .eq("capsule_id", capsule_id)         .eq("user_id", current_user["sub"])         .eq("type", reaction_type).execute()
    return {"ok": True}
