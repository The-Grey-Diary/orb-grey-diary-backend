from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Placeholder rate limit middleware — expand later with Redis."""
    async def dispatch(self, request: Request, call_next):
        return await call_next(request)
