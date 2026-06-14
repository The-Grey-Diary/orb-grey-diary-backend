from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.core.auth import get_current_user, optional_user
from app.core.database import get_supabase

router = APIRouter()


class QuestionCreate(BaseModel):
    question: str


class AnswerCreate(BaseModel):
    question_id: str
    answer: str


class VoteCreate(BaseModel):
    verdict: str


@router.get("/today")
async def get_todays_court():
    db = get_supabase()
    if not db:
        return {"message": "No active court session"}
    result = db.table("court_sessions")         .select("*, capsules(title, content, mood, category, users(display_name))")         .eq("status", "active")         .order("scheduled_for", desc=True)         .limit(1).execute()
    return result.data[0] if result.data else {"message": "No active session tonight"}


@router.get("/archive")
async def get_court_archive(page: int = 1):
    db = get_supabase()
    if not db:
        return {"items": [], "page": page}
    result = db.table("court_sessions")         .select("*, capsules(title, mood)")         .eq("status", "archived")         .order("scheduled_for", desc=True)         .range((page-1)*10, page*10-1).execute()
    return {"items": result.data or [], "page": page}


@router.post("/{session_id}/question", status_code=201)
async def ask_question(
    session_id: str,
    payload: QuestionCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    result = db.table("court_questions").insert({
        "session_id": session_id,
        "user_id": current_user["sub"],
        "question": payload.question,
    }).execute()
    return result.data[0] if result.data else {}


@router.put("/{session_id}/answer")
async def answer_question(
    session_id: str,
    payload: AnswerCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    # Verify user owns the capsule for this session
    session = db.table("court_sessions")         .select("capsule_id").eq("id", session_id).single().execute()
    if not session.data:
        raise HTTPException(status_code=404, detail="Session not found")
    capsule = db.table("capsules").select("user_id")         .eq("id", session.data["capsule_id"]).single().execute()
    if not capsule.data or capsule.data["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Not your story")
    result = db.table("court_questions").update({
        "answer": payload.answer, "is_answered": True
    }).eq("id", payload.question_id).execute()
    return result.data[0] if result.data else {}


@router.post("/{session_id}/vote")
async def cast_vote(
    session_id: str,
    payload: VoteCreate,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        db.table("court_votes").insert({
            "session_id": session_id,
            "user_id": current_user["sub"],
            "verdict": payload.verdict,
        }).execute()
    except Exception:
        pass  # duplicate vote ignored
    return {"ok": True}
