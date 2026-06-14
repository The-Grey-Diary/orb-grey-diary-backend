from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import auth, users, capsules, echoes, court, guardian, payments, notifications, tasks

app = FastAPI(
    title="The Grey Diary API",
    description="Where stories wait for their endings.",
    version="1.0.0",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
)

# CORS
origins = ["*"] if settings.APP_ENV == "development" else [
    settings.FRONTEND_URL,
    "https://grey-diary.pages.dev",
    "https://thegreydiary.online",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router,          prefix="/auth",         tags=["Auth"])
app.include_router(users.router,         prefix="/users",        tags=["Users"])
app.include_router(capsules.router,      prefix="/capsules",     tags=["Capsules"])
app.include_router(echoes.router,        prefix="/capsules",     tags=["Echoes"])
app.include_router(court.router,         prefix="/court",        tags=["Court"])
app.include_router(guardian.router,      prefix="/guardian",     tags=["Guardian"])
app.include_router(payments.router,      prefix="/payments",     tags=["Payments"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(tasks.router,                                  tags=["Tasks"])


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "grey-diary-api",
        "env": settings.APP_ENV,
        "supabase_configured": bool(settings.SUPABASE_URL),
    }


@app.get("/")
async def root():
    return {"message": "The Grey Diary API", "docs": "/docs"}
