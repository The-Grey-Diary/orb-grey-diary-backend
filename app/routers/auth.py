from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
import httpx
from app.core.config import settings
from app.core.auth import create_access_token
from app.core.database import get_supabase

router = APIRouter()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/google")
async def google_login():
    """Redirect user to Google OAuth."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    params = (
        f"client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.FRONTEND_URL}/auth/callback"
        f"&response_type=code"
        f"&scope=openid email profile"
        f"&access_type=offline"
    )
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")


@router.post("/google/callback")
async def google_callback(code: str):
    """Exchange Google code for JWT. Called from frontend."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": f"{settings.FRONTEND_URL}/auth/callback",
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code")
        tokens = token_resp.json()

        # Get user info
        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        google_user = user_resp.json()

    db = get_supabase()
    if not db:
        raise HTTPException(status_code=503, detail="Database not configured")

    # Find or create user
    existing = db.table("users")         .select("*")         .eq("google_id", google_user["sub"])         .execute()

    if existing.data:
        user = existing.data[0]
    else:
        result = db.table("users").insert({
            "email": google_user["email"],
            "google_id": google_user["sub"],
            "display_name": google_user.get("name", "Grey Writer"),
            "avatar_style": "default",
            "plan": "free",
        }).execute()
        user = result.data[0]

    token = create_access_token({"sub": user["id"], "email": user["email"]})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me")
async def get_me(request: Request):
    """Get current user from JWT."""
    from app.core.auth import get_current_user
    # Extract token manually since we need Request
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    from app.core.auth import decode_token
    payload = decode_token(auth_header[7:])
    db = get_supabase()
    if not db:
        return {"id": payload["sub"], "email": payload.get("email", "")}
    result = db.table("users").select("*").eq("id", payload["sub"]).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return result.data


@router.post("/logout")
async def logout():
    return {"ok": True}
