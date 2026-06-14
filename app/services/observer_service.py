import httpx
from app.core.config import settings
from app.core.database import get_supabase

SYSTEM_PROMPT = """You are the Grey Observer.
You are attached to a story someone just sealed — a moment of uncertainty they are living through.
Write 2-3 short sentences. Not advice. Not therapy. Not prediction.
A mirror. Something that makes the writer feel witnessed.
Literary. Quiet. True."""


class ObserverService:

    @staticmethod
    async def generate_reflection(capsule_id: str, content: str, mood: str, category: str):
        db = get_supabase()
        if not db:
            return

        # Skip if already exists
        existing = db.table("capsule_reflections").select("id")             .eq("capsule_id", capsule_id).execute()
        if existing.data:
            return

        reflection = "Something in this moment already knows what time will reveal."

        if settings.OPENROUTER_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                            "HTTP-Referer": settings.FRONTEND_URL,
                            "X-Title": "The Grey Diary",
                        },
                        json={
                            "model": "mistralai/mistral-7b-instruct",
                            "messages": [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": f"Mood: {mood}\nCategory: {category}\n\n{content[:1500]}"},
                            ],
                            "max_tokens": 120,
                            "temperature": 0.85,
                        },
                    )
                    if r.status_code == 200:
                        reflection = r.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                pass

        try:
            db.table("capsule_reflections").insert({
                "capsule_id": capsule_id,
                "reflection": reflection,
                "model_used": "mistralai/mistral-7b-instruct",
            }).execute()
        except Exception:
            pass
