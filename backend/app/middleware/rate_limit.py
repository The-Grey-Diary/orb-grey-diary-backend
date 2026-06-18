from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next): return await call_next(request)
