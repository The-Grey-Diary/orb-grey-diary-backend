import httpx
from datetime import date, timedelta
from app.core.config import settings
from app.core.database import get_db

SYSTEM="You are the Grey Guardian — narrator of The Grey Diary. Write the weekly community chronicle. 150-200 words. Poetic, atmospheric, literary. Never name individuals. End with one sentence like a candle being lit."

class GuardianService:
    @staticmethod
    async def generate_weekly_chronicle()->dict:
        db=get_db()
        if not db: return {}
        week_start=date.today()-timedelta(days=date.today().weekday())
        try:
            ex=db.table("guardian_reports").select("*").eq("week_start",str(week_start)).execute()
            if ex.data: return ex.data[0]
            sealed=db.table("capsules").select("id,title",count="exact").eq("status","sealed").gte("sealed_at",str(week_start)).execute()
            revealed=db.table("capsules").select("id",count="exact").eq("status","revealed").gte("revealed_at",str(week_start)).execute()
        except: return {}
        stats={"sealed_count":sealed.count or 0,"revealed_count":revealed.count or 0}
        content=f"This week, {stats['sealed_count']} stories were sealed against the unknown. {stats['revealed_count']} returned with answers. The Grey Diary holds what you cannot carry alone."
        if settings.OPENROUTER_API_KEY:
            try:
                titles=[c["title"] for c in (sealed.data or [])[:5]]
                async with httpx.AsyncClient(timeout=45) as c:
                    r=await c.post("https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization":f"Bearer {settings.OPENROUTER_API_KEY}"},
                        json={"model":"mistralai/mixtral-8x7b-instruct","messages":[{"role":"system","content":SYSTEM},{"role":"user","content":f"Sealed:{stats['sealed_count']} Revealed:{stats['revealed_count']} Titles:{titles}"}],"max_tokens":250,"temperature":0.9})
                    if r.status_code==200: content=r.json()["choices"][0]["message"]["content"].strip()
            except: pass
        try:
            res=db.table("guardian_reports").insert({"week_start":str(week_start),"content":content,"stats":stats,"model_used":"mixtral-8x7b"}).execute()
            return res.data[0] if res.data else {}
        except: return {}

    @staticmethod
    async def generate_personal_report(user_id:str)->str:
        db=get_db()
        if not db: return "Your Personal Guardian will speak soon."
        try:
            caps=db.table("capsules").select("title,mood,category,status").eq("user_id",user_id).order("created_at").execute()
            if not caps.data: return "Seal more stories before your Personal Guardian can speak."
            history="\n".join([f"[{c['mood']}·{c['category']}] {c['title']} ({c['status']})" for c in caps.data[:20]])
        except: return "Your Personal Guardian is awakening."
        content="The pattern of your stories is still forming."
        if settings.OPENROUTER_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=45) as c:
                    r=await c.post("https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization":f"Bearer {settings.OPENROUTER_API_KEY}"},
                        json={"model":"openai/gpt-4o-mini","messages":[{"role":"system","content":"You are the Personal Guardian. Witness this person's diary journey 200-300 words. Literary, honest, kind. Never clinical."},{"role":"user","content":history}],"max_tokens":350})
                    if r.status_code==200: content=r.json()["choices"][0]["message"]["content"].strip()
            except: pass
        try: db.table("personal_reports").insert({"user_id":user_id,"content":content,"capsule_count":len(caps.data)}).execute()
        except: pass
        return content
