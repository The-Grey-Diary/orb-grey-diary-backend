"""
Admin metrics endpoint — locked to SCHEDULER_SECRET header.
Never expose this publicly. Hit it from a browser or curl with:
  curl -H "x-admin-secret: YOUR_SCHEDULER_SECRET" \
       https://orb-grey-diary-backend-632388399077.us-central1.run.app/admin/stats
"""
from fastapi import APIRouter, Header, HTTPException
from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


def verify_admin(x_admin_secret: str = Header(None)):
    if not x_admin_secret or x_admin_secret != settings.SCHEDULER_SECRET:
        raise HTTPException(403, "Forbidden")


@router.get("/stats")
async def admin_stats(x_admin_secret: str = Header(None)):
    verify_admin(x_admin_secret)
    db = get_db()
    if not db:
        raise HTTPException(503, "DB not configured")

    try:
        users       = db.table("users").select("id,plan,created_at").execute()
        capsules    = db.table("capsules").select("id,status,created_at").execute()
        echoes      = db.table("capsule_echoes").select("id").execute()
        reactions   = db.table("reactions").select("id").execute()

        user_rows     = users.data or []
        capsule_rows  = capsules.data or []

        plan_counts = {}
        for u in user_rows:
            p = u.get("plan", "free")
            plan_counts[p] = plan_counts.get(p, 0) + 1

        status_counts = {}
        for c in capsule_rows:
            s = c.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        paid = sum(v for k, v in plan_counts.items() if k != "free")
        free = plan_counts.get("free", 0)
        total_users = len(user_rows)
        conversion_pct = round((paid / total_users * 100), 1) if total_users else 0

        return {
            "users": {
                "total": total_users,
                "free": free,
                "paid": paid,
                "conversion_pct": conversion_pct,
                "by_plan": plan_counts,
            },
            "capsules": {
                "total": len(capsule_rows),
                "by_status": status_counts,
            },
            "engagement": {
                "total_echoes": len(echoes.data or []),
                "total_reactions": len(reactions.data or []),
            },
        }
    except Exception as e:
        raise HTTPException(500, str(e))
