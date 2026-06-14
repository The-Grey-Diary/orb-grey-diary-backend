from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app.core.auth import get_current_user
from app.core.database import get_supabase
from app.core.config import settings

router = APIRouter()

PLANS = {
    "plus":    {"price_inr": 149, "price_usd": 2, "features": ["25 capsules", "Guardian archive", "Early reveals"]},
    "premium": {"price_inr": 399, "price_usd": 5, "features": ["Unlimited capsules", "Private vault", "Personal Guardian"]},
}


class OrderCreate(BaseModel):
    plan: str
    provider: str = "razorpay"


class PaymentVerify(BaseModel):
    provider: str
    plan: str
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    razorpay_signature: str | None = None


@router.get("/plans")
async def get_plans():
    return PLANS


@router.post("/create-order")
async def create_order(
    payload: OrderCreate,
    current_user: dict = Depends(get_current_user),
):
    if payload.plan not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    if not settings.RAZORPAY_KEY_ID:
        raise HTTPException(status_code=503, detail="Payment not configured")
    try:
        import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        order = client.order.create({
            "amount": PLANS[payload.plan]["price_inr"] * 100,
            "currency": "INR",
            "notes": {"plan": payload.plan, "user_id": current_user["sub"]},
        })
        return {"order_id": order["id"], "amount": order["amount"],
                "currency": "INR", "key": settings.RAZORPAY_KEY_ID}
    except ImportError:
        raise HTTPException(status_code=503, detail="Razorpay not installed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify")
async def verify_payment(
    payload: PaymentVerify,
    current_user: dict = Depends(get_current_user),
):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    # Update user plan
    from datetime import datetime, timedelta
    expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
    db.table("users").update({
        "plan": payload.plan,
        "plan_expires_at": expires,
    }).eq("id", current_user["sub"]).execute()
    return {"success": True, "plan": payload.plan}


@router.post("/cancel")
async def cancel_subscription(current_user: dict = Depends(get_current_user)):
    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")
    db.table("users").update({"plan": "free", "plan_expires_at": None})         .eq("id", current_user["sub"]).execute()
    return {"ok": True}
