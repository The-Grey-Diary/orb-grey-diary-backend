from fastapi import APIRouter, Depends
from datetime import datetime
from app.core.auth import get_current_user

router = APIRouter()


@router.get("/{year}")
async def get_wrapped(year: int, user: dict = Depends(get_current_user)):
    from app.services.gamification_service import compute_wrapped
    return await compute_wrapped(user["sub"], year)


@router.get("/")
async def get_wrapped_current_year(user: dict = Depends(get_current_user)):
    from app.services.gamification_service import compute_wrapped
    return await compute_wrapped(user["sub"], datetime.now().year)
