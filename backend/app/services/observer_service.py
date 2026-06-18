import httpx
from app.core.config import settings
from app.core.database import get_db

SYSTEM="You are the Grey Observer. Attached to a story just sealed. Write 2-3 short sentences. Not advice. Not therapy. Not prediction. A mirror. Literary. Quiet. True."

class ObserverService:
    @staticmethod
    async def generate_reflection(capsule_id:str,content:str,mood:str,category:str):
        db=get_db()
        if not db: return
        try:
            if db.table("capsule_reflections").select("id").eq("capsule_id",capsule_id).execute().data: return
        except: return
        reflection="Something in this moment already knows what time will reveal."
        if settings.OPENROUTER_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=30) as c:
                    r=await c.post("https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization":f"Bearer {settings.OPENROUTER_API_KEY}","HTTP-Referer":settings.FRONTEND_URL},
                        json={"model":"mistralai/mistral-7b-instruct","messages":[{"role":"system","content":SYSTEM},{"role":"user","content":f"Mood:{mood} Category:{category}\n{content[:1500]}"}],"max_tokens":120,"temperature":0.85})
                    if r.status_code==200: reflection=r.json()["choices"][0]["message"]["content"].strip()
            except: pass
        try: db.table("capsule_reflections").insert({"capsule_id":capsule_id,"reflection":reflection,"model_used":"mistralai/mistral-7b-instruct"}).execute()
        except: pass
