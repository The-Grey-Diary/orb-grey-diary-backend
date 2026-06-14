from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_ENV: str = "production"
    FRONTEND_URL: str = "*"
    COURT_TIME_IST: str = "22:00"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # JWT
    JWT_SECRET_KEY: str = "please-change-in-production-256-bit-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # OpenRouter AI
    OPENROUTER_API_KEY: str = ""

    # Razorpay
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Email
    RESEND_API_KEY: str = ""

    # Cron security
    SCHEDULER_SECRET: str = "change-this-scheduler-secret"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"   # IMPORTANT: ignore Cloud Run injected vars


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
