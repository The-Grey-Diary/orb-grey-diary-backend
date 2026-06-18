import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("grey-diary")

app = FastAPI(title="The Grey Diary API", version="1.0.0", docs_url="/docs")

# CORS — specific origins, credentials=True requires explicit origins not "*"
origins = [
    "https://thegreydiary.online",
    "https://www.thegreydiary.online",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET","POST","PUT","DELETE","OPTIONS","PATCH"],
    allow_headers=["*"],
)

@app.get("/health")
async def health(): return {"status":"ok","service":"grey-diary-api","env":settings.APP_ENV}

@app.get("/")
async def root(): return {"message":"The Grey Diary API"}

_errors = []
def _load():
    try:
        from app.routers.auth import router as auth_r
        from app.routers.users import router as users_r
        from app.routers.capsules import router as cap_r
        from app.routers.echoes import router as echo_r
        from app.routers.court import router as court_r
        from app.routers.guardian import router as guard_r
        from app.routers.payments import router as pay_r
        from app.routers.notifications import router as notif_r
        from app.routers.tasks import router as task_r
        from app.routers.wrapped import router as wrapped_r
        app.include_router(auth_r,  prefix="/auth",          tags=["Auth"])
        app.include_router(users_r, prefix="/users",         tags=["Users"])
        app.include_router(cap_r,   prefix="/capsules",      tags=["Capsules"])
        app.include_router(echo_r,  prefix="/capsules",      tags=["Echoes"])
        app.include_router(court_r, prefix="/court",         tags=["Court"])
        app.include_router(guard_r, prefix="/guardian",      tags=["Guardian"])
        app.include_router(pay_r,   prefix="/payments",      tags=["Payments"])
        app.include_router(notif_r, prefix="/notifications", tags=["Notifications"])
        app.include_router(task_r,                           tags=["Tasks"])
        app.include_router(wrapped_r, prefix="/wrapped",     tags=["Wrapped"])
        logger.info("All routers loaded OK")
    except Exception as e:
        logger.error(f"Router load error: {e}")
        _errors.append(str(e))
_load()

@app.get("/debug")
async def debug(): return {"errors":_errors,"env":settings.APP_ENV}
