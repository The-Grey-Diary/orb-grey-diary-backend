"""
Grey Guardian Service — weekly community chronicle + personal reports.
Weekly job runs every Sunday 11 PM IST.
Personal Guardian runs on user request (premium only).
"""
import httpx
from datetime import date, timedelta
from app.core.config import settings
from app.core.database import get_db_direct


GUARDIAN_SYSTEM_PROMPT = """You are the Grey Guardian.

You are the narrator of The Grey Diary — a community where people seal
their uncertain moments and return after time has passed to share what happened.

Each week you survey the emotional landscape of this community.
You write the weekly chronicle for everyone to read.

Rules:
- Never name or identify any individual.
- Speak of the collective emotional truth of the week.
- Weave the stats naturally into the narrative. Do not list them.
- 150–200 words.
- Literary. Atmospheric. Like a letter from time itself.
- End with one sentence that feels like a candle being lit."""


PERSONAL_GUARDIAN_SYSTEM_PROMPT = """You are the Personal Guardian.

You have been given someone's complete history on The Grey Diary —
their sealed stories, their echoes, the moods they carried, the time that passed.

You are not a therapist. You are not an analyst. You are a witness.

Write a personal reflection (200–300 words) on who this person appears to be
becoming across their stories. What patterns of fear and hope do you see?
What seems to be changing? What has time consistently proven to them?

Be literary. Be honest. Be kind. Never be clinical.
Never use the words "journey" or "growth" or "process"."""


GUARDIAN_MODEL = "mistralai/mixtral-8x7b-instruct"
PERSONAL_MODEL = "openai/gpt-4o-mini"


class GuardianService:

    @staticmethod
    async def generate_weekly_chronicle() -> dict:
        """
        Generate the weekly Grey Guardian chronicle.
        Called by scheduled job every Sunday 11 PM IST.
        """
        db = await get_db_direct()
        week_start = date.today() - timedelta(days=date.today().weekday())

        # Check if already generated this week
        existing = await db.table("guardian_reports") \
            .select("id,content") \
            .eq("week_start", str(week_start)) \
            .single() \
            .execute()

        if existing.data:
            return existing.data

        # Pull this week's stats
        stats = await GuardianService._get_weekly_stats(db, week_start)

        # Build prompt
        prompt = f"""This week's data from The Grey Diary community:

Capsules sealed: {stats['sealed_count']}
Capsules revealed: {stats['revealed_count']}
Most common fear: {stats['top_fear_category']}
Most common hope: {stats['top_hope_category']}
Top mood across all stories: {stats['top_mood']}

Some anonymous fragments sealed this week (never identify):
{chr(10).join(['- ' + t for t in stats['sample_titles'][:5]])}

Write the weekly chronicle."""

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "HTTP-Referer": settings.FRONTEND_URL,
                        "X-Title": "The Grey Diary",
                    },
                    json={
                        "model": GUARDIAN_MODEL,
                        "messages": [
                            {"role": "system", "content": GUARDIAN_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 250,
                        "temperature": 0.9,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"].strip()

        except Exception as e:
            print(f"[Guardian] Weekly generation error: {e}")
            content = "This week, the community sealed its fears and returned with truths. Time, as always, proved kinder than the waiting."

        result = await db.table("guardian_reports").insert({
            "week_start": str(week_start),
            "content": content,
            "stats": stats,
            "model_used": GUARDIAN_MODEL,
        }).execute()

        return result.data[0]

    @staticmethod
    async def generate_personal_report(user_id: str) -> str:
        """
        Generate a Personal Guardian reflection for a premium user.
        Max once per week.
        """
        db = await get_db_direct()

        # Get user's capsule history
        capsules = await db.table("capsules") \
            .select("title,content,mood,category,status,created_at,revealed_at") \
            .eq("user_id", user_id) \
            .order("created_at") \
            .execute()

        echoes = await db.table("capsule_echoes") \
            .select("content,mood,created_at,capsule_id") \
            .execute()

        if not capsules.data:
            return "Your story here is still beginning. Seal more moments before your Personal Guardian can speak."

        # Build history summary
        history_lines = []
        for c in capsules.data:
            days_waited = ""
            if c.get("revealed_at") and c.get("created_at"):
                # rough days calculation
                days_waited = " (waited)"
            history_lines.append(
                f"[{c['mood']} · {c['category']}] \"{c['title']}\" — "
                f"Status: {c['status']}{days_waited}"
            )

        echo_lines = [f"Echo: {e['content'][:100]}" for e in echoes.data]

        prompt = f"""User history on The Grey Diary:

SEALED STORIES:
{chr(10).join(history_lines[:20])}

ECHOES (what they wrote after time passed):
{chr(10).join(echo_lines[:10])}

Write their Personal Guardian reflection."""

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "HTTP-Referer": settings.FRONTEND_URL,
                    },
                    json={
                        "model": PERSONAL_MODEL,
                        "messages": [
                            {"role": "system", "content": PERSONAL_GUARDIAN_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 350,
                        "temperature": 0.88,
                    },
                )
                response.raise_for_status()
                reflection = response.json()["choices"][0]["message"]["content"].strip()

        except Exception as e:
            print(f"[Personal Guardian] Error for user {user_id}: {e}")
            reflection = "The pattern of your stories is still forming. Return here when time has had more to say."

        await db.table("personal_reports").insert({
            "user_id": user_id,
            "content": reflection,
            "capsule_count": len(capsules.data),
        }).execute()

        return reflection

    @staticmethod
    async def _get_weekly_stats(db, week_start: date) -> dict:
        """Pull aggregated stats for the week."""
        week_end = week_start + timedelta(days=7)

        sealed = await db.table("capsules") \
            .select("id,mood,category,title", count="exact") \
            .eq("status", "sealed") \
            .gte("sealed_at", str(week_start)) \
            .lt("sealed_at", str(week_end)) \
            .execute()

        revealed = await db.table("capsules") \
            .select("id", count="exact") \
            .eq("status", "revealed") \
            .gte("revealed_at", str(week_start)) \
            .lt("revealed_at", str(week_end)) \
            .execute()

        capsule_data = sealed.data or []
        mood_counts = {}
        cat_counts = {"Fear": {}, "Hope": {}}

        for c in capsule_data:
            mood_counts[c["mood"]] = mood_counts.get(c["mood"], 0) + 1
            if c["mood"] in ("Fear", "Hope"):
                cat_counts[c["mood"]][c["category"]] = \
                    cat_counts[c["mood"]].get(c["category"], 0) + 1

        top_mood = max(mood_counts, key=mood_counts.get) if mood_counts else "Unknown"
        top_fear = max(cat_counts["Fear"], key=cat_counts["Fear"].get) if cat_counts["Fear"] else "Unknown"
        top_hope = max(cat_counts["Hope"], key=cat_counts["Hope"].get) if cat_counts["Hope"] else "Unknown"

        return {
            "sealed_count": len(capsule_data),
            "revealed_count": revealed.count or 0,
            "top_mood": top_mood,
            "top_fear_category": top_fear,
            "top_hope_category": top_hope,
            "sample_titles": [c["title"] for c in capsule_data[:8]],
        }
