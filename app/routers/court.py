from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.core.auth import get_current_user
from app.core.database import get_db

router = APIRouter()
class QIn(BaseModel): question:str
class AIn(BaseModel): question_id:str; answer:str
class VIn(BaseModel): verdict:str

@router.get("/today")
async def today():
    db=get_db()
    if not db: return {"message":"No active session"}
    r=db.table("court_sessions").select("*,capsules(title,content,mood,category)").eq("status","active").order("scheduled_for",desc=True).limit(1).execute()
    return r.data[0] if r.data else {"message":"No active session tonight"}

@router.get("/archive")
async def archive(page:int=1):
    db=get_db()
    if not db: return {"items":[],"page":page}
    r=db.table("court_sessions").select("*,capsules(title,mood)").eq("status","archived").order("scheduled_for",desc=True).range((page-1)*10,page*10-1).execute()
    return {"items":r.data or [],"page":page}

@router.post("/{sid}/question",status_code=201)
async def ask(sid:str,payload:QIn,user:dict=Depends(get_current_user)):
    db=get_db()
    if not db: raise HTTPException(503,"DB not configured")
    r=db.table("court_questions").insert({"session_id":sid,"user_id":user["sub"],"question":payload.question}).execute()
    return r.data[0] if r.data else {}

@router.put("/{sid}/answer")
async def answer(sid:str,payload:AIn,user:dict=Depends(get_current_user)):
    db=get_db()
    if not db: raise HTTPException(503,"DB not configured")
    r=db.table("court_questions").update({"answer":payload.answer,"is_answered":True}).eq("id",payload.question_id).execute()
    return r.data[0] if r.data else {}

@router.post("/{sid}/vote")
async def vote(sid:str,payload:VIn,user:dict=Depends(get_current_user)):
    db=get_db()
    if not db: raise HTTPException(503,"DB not configured")
    try: db.table("court_votes").insert({"session_id":sid,"user_id":user["sub"],"verdict":payload.verdict}).execute()
    except: pass
    return {"ok":True}
