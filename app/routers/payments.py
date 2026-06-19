from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import hmac, hashlib
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.config import settings

router = APIRouter()

PLANS = {
    "plus":    {"price_inr": 149, "name": "Grey Plus",    "features": ["25 active capsules", "Guardian archive", "Emotional themes", "Early reveals"]},
    "premium": {"price_inr": 399, "name": "Grey Premium", "features": ["Unlimited capsules", "Private vault", "Future letters", "Personal Guardian"]},
}

class OrderIn(BaseModel):
    plan: str
    provider: str = "razorpay"

class VerifyIn(BaseModel):
    provider: str
    plan: str
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None


@router.get("/plans")
async def plans():
    return PLANS


@router.post("/create-order")
async def create_order(payload: OrderIn, user: dict = Depends(get_current_user)):
    if payload.plan not in PLANS:
        raise HTTPException(400, "Invalid plan")
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(503, "Payments not configured — missing Razorpay keys")
    try:
        import razorpay
    except ImportError:
        raise HTTPException(503, "razorpay package not installed on server")

    try:
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        order = client.order.create({
            "amount": PLANS[payload.plan]["price_inr"] * 100,
            "currency": "INR",
            "notes": {"plan": payload.plan, "user_id": user["sub"]},
        })
        return {
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID,
            "plan_name": PLANS[payload.plan]["name"],
        }
    except Exception as e:
        raise HTTPException(500, f"Razorpay order creation failed: {e}")


@router.post("/verify")
async def verify(payload: VerifyIn, user: dict = Depends(get_current_user)):
    if payload.plan not in PLANS:
        raise HTTPException(400, "Invalid plan")

    # ── Signature verification — this is what stops anyone from forging a free upgrade ──
    if not (payload.razorpay_order_id and payload.razorpay_payment_id and payload.razorpay_signature):
        raise HTTPException(400, "Missing payment verification fields")

    if not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(503, "Payments not configured")

    body = f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}"
    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, payload.razorpay_signature):
        raise HTTPException(400, "Payment signature verification failed")

    db = get_db()
    if not db:
        raise HTTPException(503, "DB not configured")

    expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    db.table("users").update({
        "plan": payload.plan,
        "plan_expires_at": expires,
    }).eq("id", user["sub"]).execute()

    return {"success": True, "plan": payload.plan, "expires_at": expires}


@router.post("/cancel")
async def cancel(user: dict = Depends(get_current_user)):
    db = get_db()
    if not db:
        raise HTTPException(503, "DB not configured")
    db.table("users").update({"plan": "free", "plan_expires_at": None}).eq("id", user["sub"]).execute()
    return {"ok": True}
