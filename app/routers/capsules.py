from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import Optional
from datetime import datetime, timezone
from app.core.auth import get_current_user, optional_user
from app.core.database import get_db
from pydantic import BaseModel

router = APIRouter()
PLAN_LIMITS = {"free":3,"plus":25,"premium":9999}

class CapsuleCreate(BaseModel):
    title: str; content: str; category: str; mood: str
    reveal_date: datetime; is_public: bool = True; status: str = "draft"

class CapsuleUpdate(BaseModel):
    title: Optional[str]=None; content: Optional[str]=None
    category: Optional[str]=None; mood: Optional[str]=None
    reveal_date: Optional[datetime]=None; is_public: Optional[bool]=None

class SealIn(BaseModel):
    reveal_date: datetime

@router.get("/stats")
async def stats():
    db = get_db()
    if not db: return {"total_sealed":0,"total_revealed":0,"total_users":0,"revealing_tonight":0}
    try:
        s = db.table("capsules").select("id",count="exact").eq("status","sealed").execute()
        r = db.table("capsules").select("id",count="exact").eq("status","revealed").execute()
        u = db.table("users").select("id",count="exact").execute()
        return {"total_sealed":s.count or 0,"total_revealed":r.count or 0,"total_users":u.count or 0,"revealing_tonight":0}
    except: return {"total_sealed":0,"total_revealed":0,"total_users":0,"revealing_tonight":0}

@router.get("/mine")
async def mine(page:int=1, status:Optional[str]=None, user:dict=Depends(get_current_user)):
    db = get_db()
    if not db: return {"items":[],"total":0,"page":page,"per_page":20,"has_more":False}
    q = db.table("capsules").select("*").eq("user_id",user["sub"])
    if status: q = q.eq("status",status)
    r = q.order("created_at",desc=True).range((page-1)*20,page*20-1).execute()
    return {"items":r.data or [],"total":len(r.data or []),"page":page,"per_page":20,"has_more":len(r.data or [])==20}

@router.get("/")
async def explore(page:int=Query(1,ge=1),per_page:int=Query(20,ge=1,le=50),
                  category:Optional[str]=None,mood:Optional[str]=None,
                  user:Optional[dict]=Depends(optional_user)):
    db = get_db()
    if not db: return {"items":[],"total":0,"page":page,"per_page":per_page,"has_more":False}
    q = db.table("capsules").select("*").eq("status","revealed").eq("is_public",True)
    if category: q = q.eq("category",category)
    if mood: q = q.eq("mood",mood)
    r = q.order("revealed_at",desc=True).range((page-1)*per_page,page*per_page-1).execute()
    items = r.data or []
    return {"items":items,"total":len(items),"page":page,"per_page":per_page,"has_more":len(items)==per_page}

@router.post("/",status_code=201)
async def create(payload:CapsuleCreate,bg:BackgroundTasks,user:dict=Depends(get_current_user)):
    db = get_db()
    if not db: raise HTTPException(503,"DB not configured")
    ur = db.table("users").select("plan").eq("id",user["sub"]).single().execute()
    plan = ur.data.get("plan","free") if ur.data else "free"
    cr = db.table("capsules").select("id",count="exact").eq("user_id",user["sub"]).neq("status","revealed").execute()
    if (cr.count or 0) >= PLAN_LIMITS.get(plan,3): raise HTTPException(403,"Plan limit reached")
    data = {"user_id":user["sub"],"title":payload.title,"content":payload.content,
            "category":payload.category,"mood":payload.mood,
            "reveal_date":payload.reveal_date.isoformat(),"status":payload.status,"is_public":payload.is_public}
    if payload.status=="sealed": data["sealed_at"]=datetime.now(timezone.utc).isoformat()
    r = db.table("capsules").insert(data).execute()
    cap = r.data[0]
    if payload.status=="sealed":
        from app.services.observer_service import ObserverService
        bg.add_task(ObserverService.generate_reflection,cap["id"],cap["content"],cap["mood"],cap["category"])
    return cap

@router.get("/{capsule_id}")
async def get_one(capsule_id:str,user:Optional[dict]=Depends(optional_user)):
    db = get_db()
    if not db: raise HTTPException(503,"DB not configured")
    r = db.table("capsules").select("*").eq("id",capsule_id).single().execute()
    if not r.data: raise HTTPException(404,"Not found")
    c = r.data
    if c["status"]!="revealed" and (not user or user["sub"]!=c["user_id"]): raise HTTPException(403,"Still sealed")
    db.table("capsules").update({"view_count":c["view_count"]+1}).eq("id",capsule_id).execute()
    return c

@router.put("/{capsule_id}")
async def update(capsule_id:str,payload:CapsuleUpdate,user:dict=Depends(get_current_user)):
    db = get_db()
    if not db: raise HTTPException(503,"DB not configured")
    r = db.table("capsules").select("status,user_id").eq("id",capsule_id).single().execute()
    if not r.data or r.data["user_id"]!=user["sub"]: raise HTTPException(404,"Not found")
    if r.data["status"]!="draft": raise HTTPException(403,"Cannot edit sealed capsule")
    data={k:v for k,v in payload.model_dump().items() if v is not None}
    u=db.table("capsules").update(data).eq("id",capsule_id).execute()
    return u.data[0]

@router.delete("/{capsule_id}",status_code=204)
async def delete(capsule_id:str,user:dict=Depends(get_current_user)):
    db = get_db()
    if not db: raise HTTPException(503,"DB not configured")
    r = db.table("capsules").select("status,user_id").eq("id",capsule_id).single().execute()
    if not r.data or r.data["user_id"]!=user["sub"]: raise HTTPException(404,"Not found")
    if r.data["status"]!="draft": raise HTTPException(403,"Cannot delete sealed capsule")
    db.table("capsules").delete().eq("id",capsule_id).execute()

@router.post("/{capsule_id}/seal")
async def seal(capsule_id:str,payload:SealIn,bg:BackgroundTasks,user:dict=Depends(get_current_user)):
    db = get_db()
    if not db: raise HTTPException(503,"DB not configured")
    r = db.table("capsules").select("*").eq("id",capsule_id).single().execute()
    if not r.data or r.data["user_id"]!=user["sub"]: raise HTTPException(404,"Not found")
    if r.data["status"]!="draft": raise HTTPException(403,"Already sealed")
    u = db.table("capsules").update({"status":"sealed","reveal_date":payload.reveal_date.isoformat(),"sealed_at":datetime.now(timezone.utc).isoformat()}).eq("id",capsule_id).execute()
    from app.services.observer_service import ObserverService
    bg.add_task(ObserverService.generate_reflection,capsule_id,r.data["content"],r.data["mood"],r.data["category"])
    return u.data[0]

@router.post("/{capsule_id}/react")
async def react(capsule_id:str,reaction_type:str=Query(...),user:dict=Depends(get_current_user)):
    if reaction_type not in ("heart","heartbreak","fire","candle"): raise HTTPException(400,"Invalid")
    db = get_db()
    if not db: raise HTTPException(503,"DB not configured")
    try: db.table("reactions").insert({"capsule_id":capsule_id,"user_id":user["sub"],"type":reaction_type}).execute()
    except: pass
    return {"ok":True}

@router.delete("/{capsule_id}/react")
async def unreact(capsule_id:str,reaction_type:str=Query(...),user:dict=Depends(get_current_user)):
    db = get_db()
    if not db: raise HTTPException(503,"DB not configured")
    db.table("reactions").delete().eq("capsule_id",capsule_id).eq("user_id",user["sub"]).eq("type",reaction_type).execute()
    return {"ok":True}
