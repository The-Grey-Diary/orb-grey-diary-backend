"""
THE GREY DIARY — FastAPI Backend
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.core.config import settings
from app.core.database import init_db
from app.routers import auth, users, capsules, echoes, court, guardian, payments, notifications
from app.middleware.rate_limit import RateLimitMiddleware
from app.tasks.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    await init_db()
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()


# Sentry setup
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=settings.APP_ENV,
    )


app = FastAPI(
    title="The Grey Diary API",
    description="Where stories wait for their endings.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV == "development" else None,
    redoc_url=None,
)


# ── Middleware ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(auth.router,          prefix="/auth",          tags=["Auth"])
app.include_router(users.router,         prefix="/users",         tags=["Users"])
app.include_router(capsules.router,      prefix="/capsules",      tags=["Capsules"])
app.include_router(echoes.router,        prefix="/capsules",      tags=["Echoes"])
app.include_router(court.router,         prefix="/court",         tags=["Court"])
app.include_router(guardian.router,      prefix="/guardian",      tags=["Guardian"])
app.include_router(payments.router,      prefix="/payments",      tags=["Payments"])
app.include_router(notifications.router, prefix="/notifications",  tags=["Notifications"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "grey-diary-api"}
