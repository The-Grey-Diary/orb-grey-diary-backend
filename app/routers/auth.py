"""
Auth router — Backend-callback OAuth flow.
Google redirects to THIS backend endpoint directly.
No more 422 errors from frontend-to-backend code exchange.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.core.config import settings
from app.core.auth import create_access_token
from app.core.database import get_db
import httpx

router = APIRouter()

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"

# The redirect_uri Google calls — points to THIS backend
GOOGLE_REDIRECT_URI = f"{settings.BACKEND_URL}/auth/google/callback"


@router.get("/google")
async def google_login():
    """Step 1: Redirect user to Google OAuth page."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google OAuth not configured")
    params = "&".join([
        f"client_id={settings.GOOGLE_CLIENT_ID}",
        f"redirect_uri={GOOGLE_REDIRECT_URI}",
        "response_type=code",
        "scope=openid email profile",
        "access_type=offline",
        "prompt=select_account",
    ])
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/google/callback")
async def google_callback(code: str = None, error: str = None):
    """Step 2: Google redirects here with the code. Backend exchanges it."""
    if error:
        return RedirectResponse(f"{settings.FRONTEND_URL}/?error={error}")
    if not code:
        return RedirectResponse(f"{settings.FRONTEND_URL}/?error=no_code")

    # Exchange code for tokens
    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            return RedirectResponse(f"{settings.FRONTEND_URL}/?error=token_exchange_failed")

        tokens    = token_resp.json()
        user_resp = await client.get(
            GOOGLE_USER_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        google_user = user_resp.json()

    db = get_db()
    if not db:
        return RedirectResponse(f"{settings.FRONTEND_URL}/?error=db_not_configured")

    # Find or create user
    try:
        existing = db.table("users").select("*").eq("google_id", google_user["sub"]).execute()
        if existing.data:
            user = existing.data[0]
        else:
            result = db.table("users").insert({
                "email":        google_user.get("email", ""),
                "google_id":    google_user["sub"],
                "display_name": google_user.get("name", "Grey Writer"),
                "avatar_style": "default",
                "plan":         "free",
            }).execute()
            user = result.data[0]
    except Exception as e:
        return RedirectResponse(f"{settings.FRONTEND_URL}/?error=db_error")

    # Create JWT and redirect frontend to /auth/success with token
    token = create_access_token({"sub": user["id"], "email": user["email"]})
    return RedirectResponse(f"{settings.FRONTEND_URL}/auth/success/?token={token}")


@router.get("/me")
async def get_me(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    from app.core.auth import decode_token
    payload = decode_token(auth[7:])
    db = get_db()
    if not db:
        return {"id": payload["sub"], "email": payload.get("email", "")}
    r = db.table("users").select("*").eq("id", payload["sub"]).single().execute()
    if not r.data: raise HTTPException(404, "User not found")
    return r.data

@router.post("/logout")
async def logout(): return {"ok": True}
