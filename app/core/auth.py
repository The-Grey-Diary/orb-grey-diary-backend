"""JWT auth using PyJWT (not python-jose — avoids Docker conflict)."""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.exceptions import InvalidTokenError
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.core.config import settings

security = HTTPBearer(auto_error=False)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {e}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_token(credentials.credentials)


async def optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[dict]:
    if not credentials:
        return None
    try:
        return decode_token(credentials.credentials)
    except Exception:
        return None
