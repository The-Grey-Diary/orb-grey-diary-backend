import httpx
from datetime import date, timedelta
from app.core.config import settings
from app.core.database import get_supabase

GUARDIAN_PROMPT = """You are the Grey Guardian — narrator of The Grey Diary.
Write the weekly community chronicle. 150-200 words.
Poetic, atmospheric, literary. Never name individuals.
Include the stats naturally. End with one sentence like a candle being lit."""

PERSONAL_PROMPT = """You are the Personal Guardian.
You have seen someone's complete story on The Grey Diary.
Write a personal reflection 200-300 words. You are a witness, not a therapist.
Never use the words "journey", "growth", or "process"."""


class GuardianService:

    @staticmethod
    async def generate_weekly_chronicle() -> dict:
        db = get_supabase()
        if not db:
            return {}

        week_start = date.today() - timedelta(days=date.today().weekday())
        existing = db.table("guardian_reports").select("*")             .eq("week_start", str(week_start)).execute()
        if existing.data:
            return existing.data[0]

        # Get stats
        sealed = db.table("capsules").select("id,mood,category,title", count="exact")             .eq("status", "sealed")             .gte("sealed_at", str(week_start)).execute()
        revealed = db.table("capsules").select("id", count="exact")             .eq("status", "revealed")             .gte("revealed_at", str(week_start)).execute()

        stats = {
            "sealed_count": sealed.count or 0,
            "revealed_count": revealed.count or 0,
        }
        sample_titles = [c["title"] for c in (sealed.data or [])[:5]]

        content = f"This week, {stats['sealed_count']} stories were sealed against the unknown. {stats['revealed_count']} returned with answers. The Grey Diary holds what you cannot carry alone."

        if settings.OPENROUTER_API_KEY:
            try:
                prompt = f"Sealed: {stats['sealed_count']}. Revealed: {stats['revealed_count']}. Sample titles: {sample_titles}. Write the chronicle."
                async with httpx.AsyncClient(timeout=45) as client:
                    r = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                            "HTTP-Referer": settings.FRONTEND_URL,
                        },
                        json={
                            "model": "mistralai/mixtral-8x7b-instruct",
                            "messages": [
                                {"role": "system", "content": GUARDIAN_PROMPT},
                                {"role": "user", "content": prompt},
                            ],
                            "max_tokens": 250,
                            "temperature": 0.9,
                        },
                    )
                    if r.status_code == 200:
                        content = r.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                pass

        result = db.table("guardian_reports").insert({
            "week_start": str(week_start),
            "content": content,
            "stats": stats,
            "model_used": "mistralai/mixtral-8x7b-instruct",
        }).execute()
        return result.data[0] if result.data else {}

    @staticmethod
    async def generate_personal_report(user_id: str) -> str:
        db = get_supabase()
        if not db:
            return "Your Personal Guardian will speak soon."

        capsules = db.table("capsules").select("title,mood,category,status")             .eq("user_id", user_id).order("created_at").execute()

        if not capsules.data:
            return "Seal more stories before your Personal Guardian can speak."

        history = "\n".join([f"[{c['mood']}·{c['category']}] {c['title']} ({c['status']})" for c in capsules.data[:20]])
        content = "The pattern of your stories is still forming. Return here when time has had more to say."

        if settings.OPENROUTER_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=45) as client:
                    r = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                        json={
                            "model": "openai/gpt-4o-mini",
                            "messages": [
                                {"role": "system", "content": PERSONAL_PROMPT},
                                {"role": "user", "content": history},
                            ],
                            "max_tokens": 350,
                        },
                    )
                    if r.status_code == 200:
                        content = r.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                pass

        db.table("personal_reports").insert({
            "user_id": user_id,
            "content": content,
            "capsule_count": len(capsules.data),
        }).execute()
        return content
