from app.core.config import settings
_db = None
def get_db():
    global _db
    if _db is None and settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        from supabase import create_client
        _db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _db
async def get_db_direct(): return get_db()
