from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.config import settings

router = APIRouter()
PLANS = {"plus":{"price_inr":149,"features":["25 capsules","Guardian archive","Early reveals"]},
         "premium":{"price_inr":399,"features":["Unlimited capsules","Private vault","Personal Guardian"]}}

class OrderIn(BaseModel): plan:str; provider:str="razorpay"
class VerifyIn(BaseModel): provider:str; plan:str; razorpay_order_id:Optional[str]=None; razorpay_payment_id:Optional[str]=None; razorpay_signature:Optional[str]=None

@router.get("/plans")
async def plans(): return PLANS

@router.post("/create-order")
async def create_order(payload:OrderIn,user:dict=Depends(get_current_user)):
    if payload.plan not in PLANS: raise HTTPException(400,"Invalid plan")
    if not settings.RAZORPAY_KEY_ID: raise HTTPException(503,"Payments not configured")
    try:
        import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        order = client.order.create({"amount":PLANS[payload.plan]["price_inr"]*100,"currency":"INR"})
        return {"order_id":order["id"],"amount":order["amount"],"currency":"INR","key":settings.RAZORPAY_KEY_ID}
    except ImportError: raise HTTPException(503,"razorpay not installed")
    except Exception as e: raise HTTPException(500,str(e))

@router.post("/verify")
async def verify(payload:VerifyIn,user:dict=Depends(get_current_user)):
    db=get_db()
    if not db: raise HTTPException(503,"DB not configured")
    expires=(datetime.utcnow()+timedelta(days=30)).isoformat()
    db.table("users").update({"plan":payload.plan,"plan_expires_at":expires}).eq("id",user["sub"]).execute()
    return {"success":True,"plan":payload.plan}

@router.post("/cancel")
async def cancel(user:dict=Depends(get_current_user)):
    db=get_db()
    if not db: raise HTTPException(503,"DB not configured")
    db.table("users").update({"plan":"free","plan_expires_at":None}).eq("id",user["sub"]).execute()
    return {"ok":True}
