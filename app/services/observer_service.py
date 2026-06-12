"""
Grey Observer Service — AI reflection on sealed capsules.
Runs once per capsule at the moment of sealing.
Output cached in capsule_reflections table.
"""
import httpx
from uuid import UUID
from app.core.config import settings
from app.core.database import get_db_direct


OBSERVER_SYSTEM_PROMPT = """You are the Grey Observer.

You are attached to a story someone has just sealed away — a moment of
uncertainty they are living through right now. They cannot unseal it.
They will not read your words until time has passed and the answer has arrived.

Write 2–3 short sentences.

Not advice. Not therapy. Not prediction.

A reflection. A mirror. Something that makes the writer feel witnessed,
not analysed. Something they will understand differently after time has passed.

Literary. Quiet. True. Never explain yourself.
Do not use the word "you" more than once.
Never say "I understand" or "I can see"."""


OBSERVER_MODEL = "mistralai/mistral-7b-instruct"   # cheap + fast


class ObserverService:

    @staticmethod
    async def generate_reflection(
        capsule_id: UUID,
        content: str,
        mood: str,
        category: str,
    ) -> str | None:
        """
        Call OpenRouter to generate a Grey Observer reflection.
        Save result to capsule_reflections table.
        Never re-generates if reflection already exists.
        """
        db = await get_db_direct()

        # Check if already generated
        existing = await db.table("capsule_reflections") \
            .select("id") \
            .eq("capsule_id", str(capsule_id)) \
            .single() \
            .execute()

        if existing.data:
            return None  # Already done

        # Build the prompt
        user_prompt = f"""Mood: {mood}
Category: {category}

The story:
{content[:1500]}"""

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "HTTP-Referer": settings.FRONTEND_URL,
                        "X-Title": "The Grey Diary",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": OBSERVER_MODEL,
                        "messages": [
                            {"role": "system", "content": OBSERVER_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 120,
                        "temperature": 0.85,
                    },
                )
                response.raise_for_status()
                data = response.json()
                reflection = data["choices"][0]["message"]["content"].strip()

        except Exception as e:
            print(f"[Observer] Error generating reflection for {capsule_id}: {e}")
            reflection = "Something in this moment knows what time will reveal."

        # Save to database
        await db.table("capsule_reflections").insert({
            "capsule_id": str(capsule_id),
            "reflection": reflection,
            "model_used": OBSERVER_MODEL,
        }).execute()

        return reflection
