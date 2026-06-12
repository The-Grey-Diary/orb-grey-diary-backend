"""Capsules router — create, seal, reveal, explore."""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import Optional
from uuid import UUID

from app.core.auth import get_current_user, optional_user
from app.schemas.capsule import (
    CapsuleCreate, CapsuleUpdate, CapsuleOut,
    CapsuleSeal, CapsuleListOut, CapsuleStats
)
from app.services.capsule_service import CapsuleService
from app.services.observer_service import ObserverService
from app.core.database import get_db

router = APIRouter()


@router.post("/", response_model=CapsuleOut, status_code=201)
async def create_capsule(
    payload: CapsuleCreate,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Create a new capsule (draft or sealed)."""
    service = CapsuleService(db)

    # Check plan limits
    active_count = await service.count_active(current_user.id)
    limits = {"free": 3, "plus": 25, "premium": 999}
    limit = limits.get(current_user.plan, 3)

    if active_count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Plan limit reached. Upgrade to seal more capsules."
        )

    capsule = await service.create(current_user.id, payload)

    # If sealing immediately, trigger Observer AI in background
    if payload.status == "sealed":
        background_tasks.add_task(
            ObserverService.generate_reflection,
            capsule_id=capsule.id,
            content=capsule.content,
            mood=capsule.mood,
            category=capsule.category,
        )

    return capsule


@router.get("/", response_model=CapsuleListOut)
async def explore_capsules(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    category: Optional[str] = None,
    mood: Optional[str] = None,
    sort: str = Query("recent", regex="^(recent|reactions|discussed)$"),
    db=Depends(get_db),
    current_user=Depends(optional_user),
):
    """Explore public revealed capsules."""
    service = CapsuleService(db)
    return await service.list_public(
        page=page, per_page=per_page,
        category=category, mood=mood, sort=sort,
        viewer_id=current_user.id if current_user else None,
    )


@router.get("/stats", response_model=CapsuleStats)
async def community_stats(db=Depends(get_db)):
    """Community pulse — counts, mood distribution, recent activity."""
    service = CapsuleService(db)
    return await service.get_community_stats()


@router.get("/mine", response_model=CapsuleListOut)
async def my_capsules(
    page: int = Query(1, ge=1),
    status: Optional[str] = None,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get the current user's own capsules."""
    service = CapsuleService(db)
    return await service.list_by_user(current_user.id, page=page, status=status)


@router.get("/{capsule_id}", response_model=CapsuleOut)
async def get_capsule(
    capsule_id: UUID,
    db=Depends(get_db),
    current_user=Depends(optional_user),
):
    """Get a single capsule. Author sees all states. Public sees only revealed."""
    service = CapsuleService(db)
    capsule = await service.get_by_id(capsule_id)

    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")

    # Non-revealed capsules only visible to owner
    if capsule.status != "revealed" and (
        not current_user or current_user.id != capsule.user_id
    ):
        raise HTTPException(status_code=403, detail="This capsule is still sealed")

    await service.increment_view(capsule_id)
    return capsule


@router.put("/{capsule_id}", response_model=CapsuleOut)
async def update_capsule(
    capsule_id: UUID,
    payload: CapsuleUpdate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update a capsule. Only allowed in draft state."""
    service = CapsuleService(db)
    capsule = await service.get_by_id(capsule_id)

    if not capsule or capsule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Capsule not found")

    if capsule.status != "draft":
        raise HTTPException(status_code=403, detail="Cannot edit a sealed capsule")

    return await service.update(capsule_id, payload)


@router.delete("/{capsule_id}", status_code=204)
async def delete_capsule(
    capsule_id: UUID,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a capsule. Only allowed in draft state."""
    service = CapsuleService(db)
    capsule = await service.get_by_id(capsule_id)

    if not capsule or capsule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Capsule not found")

    if capsule.status != "draft":
        raise HTTPException(status_code=403, detail="Cannot delete a sealed capsule")

    await service.delete(capsule_id)


@router.post("/{capsule_id}/seal", response_model=CapsuleOut)
async def seal_capsule(
    capsule_id: UUID,
    payload: CapsuleSeal,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Seal a draft capsule with a reveal date."""
    service = CapsuleService(db)
    capsule = await service.get_by_id(capsule_id)

    if not capsule or capsule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Capsule not found")

    if capsule.status != "draft":
        raise HTTPException(status_code=403, detail="Capsule is already sealed")

    sealed = await service.seal(capsule_id, payload.reveal_date)

    # Trigger Grey Observer
    background_tasks.add_task(
        ObserverService.generate_reflection,
        capsule_id=capsule_id,
        content=capsule.content,
        mood=capsule.mood,
        category=capsule.category,
    )

    return sealed


@router.post("/{capsule_id}/react")
async def add_reaction(
    capsule_id: UUID,
    reaction_type: str = Query(..., regex="^(heart|heartbreak|fire|candle)$"),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Add a reaction to a revealed capsule."""
    service = CapsuleService(db)
    await service.add_reaction(capsule_id, current_user.id, reaction_type)
    return {"ok": True}


@router.delete("/{capsule_id}/react")
async def remove_reaction(
    capsule_id: UUID,
    reaction_type: str = Query(..., regex="^(heart|heartbreak|fire|candle)$"),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Remove a reaction."""
    service = CapsuleService(db)
    await service.remove_reaction(capsule_id, current_user.id, reaction_type)
    return {"ok": True}
