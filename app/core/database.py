from supabase import create_client, Client
from app.core.config import settings

_client: Client | None = None


def get_supabase() -> Client | None:
    global _client
    if _client is None:
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            _client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY,
            )
    return _client


async def get_db() -> Client | None:
    return get_supabase()


async def get_db_direct() -> Client | None:
    return get_supabase()
