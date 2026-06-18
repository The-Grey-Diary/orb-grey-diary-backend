"""
Gamification engine — levels, achievement badges, and annual "Wrapped" stats.
Everything here is computed on the fly from existing capsules/echoes/reactions
data. No new database tables or migrations required.
"""
from datetime import datetime, timezone
from collections import Counter
from app.core.database import get_db

# ─────────────────────────────────────────────────────────────────────────
# LEVELS
# ─────────────────────────────────────────────────────────────────────────
LEVELS = [
    (0,  "Grey Wanderer",  "Just beginning to write into the unknown."),
    (3,  "Grey Seeker",    "Returning to the page, again and again."),
    (10, "Grey Sage",      "You've sat with uncertainty long enough to trust it."),
    (25, "Grey Oracle",    "Your archive has become a record of becoming."),
    (50, "Grey Eternal",   "Few have sealed this many moments. You are the diary now."),
]

def get_level(total_capsules: int) -> dict:
    current = LEVELS[0]
    next_level = None
    for i, lvl in enumerate(LEVELS):
        if total_capsules >= lvl[0]:
            current = lvl
            next_level = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
        else:
            break
    progress = None
    if next_level:
        span = next_level[0] - current[0]
        done = total_capsules - current[0]
        progress = {
            "current_count": total_capsules,
            "next_threshold": next_level[0],
            "next_title": next_level[1],
            "pct": round(min(100, (done / span) * 100)) if span else 100,
        }
    return {
        "title": current[1],
        "tagline": current[2],
        "min_capsules": current[0],
        "progress": progress,
    }


# ─────────────────────────────────────────────────────────────────────────
# BADGES — each is a small pure function over a user's capsule data
# ─────────────────────────────────────────────────────────────────────────
BADGE_CATALOG = {
    "first_echo":      {"name": "First Echo",        "icon": "🌊", "desc": "Returned to add what happened."},
    "night_sealer":     {"name": "Night Sealer",      "icon": "🌙", "desc": "Sealed a story between midnight and 4am."},
    "long_wait":        {"name": "The Long Wait",     "icon": "⏳", "desc": "Held a capsule sealed for 180 days or more."},
    "founding_writer":  {"name": "Founding Writer",   "icon": "🕯️", "desc": "Among the first 1,000 to write here."},
    "five_moods":       {"name": "Full Spectrum",     "icon": "🎭", "desc": "Sealed a story in every mood."},
    "court_appearance": {"name": "Heard in Court",    "icon": "⚖️", "desc": "A story selected for The Court."},
    "resonant":         {"name": "Resonant",          "icon": "🔥", "desc": "A story that moved the community — 50+ reactions."},
    "century":          {"name": "The Century",       "icon": "💯", "desc": "100 capsules sealed. A true archivist."},
}

import pytz
IST = pytz.timezone("Asia/Kolkata")


async def compute_badges(user_id: str) -> list:
    db = get_db()
    if not db:
        return []
    earned = []

    try:
        caps = db.table("capsules").select(
            "id,mood,sealed_at,reveal_date,status,created_at"
        ).eq("user_id", user_id).execute().data or []
    except Exception:
        return []

    total = len(caps)

    # century / founding writer style count badges
    if total >= 100:
        earned.append("century")

    # five_moods
    moods_seen = {c["mood"] for c in caps if c.get("mood")}
    if {"Fear", "Hope", "Love", "Regret", "Unknown"}.issubset(moods_seen):
        earned.append("five_moods")

    # night_sealer — any sealed_at between 00:00-04:00 IST
    for c in caps:
        if c.get("sealed_at"):
            try:
                dt = datetime.fromisoformat(c["sealed_at"].replace("Z", "+00:00")).astimezone(IST)
                if 0 <= dt.hour < 4:
                    earned.append("night_sealer")
                    break
            except Exception:
                pass

    # long_wait — reveal_date - sealed_at >= 180 days
    for c in caps:
        if c.get("sealed_at") and c.get("reveal_date"):
            try:
                sealed = datetime.fromisoformat(c["sealed_at"].replace("Z", "+00:00"))
                reveal = datetime.fromisoformat(c["reveal_date"].replace("Z", "+00:00"))
                if (reveal - sealed).days >= 180:
                    earned.append("long_wait")
                    break
            except Exception:
                pass

    # first_echo
    try:
        cap_ids = [c["id"] for c in caps]
        if cap_ids:
            echoes = db.table("capsule_echoes").select("id").in_("capsule_id", cap_ids).limit(1).execute()
            if echoes.data:
                earned.append("first_echo")
    except Exception:
        pass

    # court_appearance
    try:
        cap_ids = [c["id"] for c in caps]
        if cap_ids:
            court = db.table("court_sessions").select("id").in_("capsule_id", cap_ids).limit(1).execute()
            if court.data:
                earned.append("court_appearance")
    except Exception:
        pass

    # resonant — 50+ total reactions across all capsules
    try:
        cap_ids = [c["id"] for c in caps]
        if cap_ids:
            reactions = db.table("reactions").select("id", count="exact").in_("capsule_id", cap_ids).execute()
            if (reactions.count or 0) >= 50:
                earned.append("resonant")
    except Exception:
        pass

    # founding_writer — user is among first 1000 created
    try:
        user_row = db.table("users").select("created_at").eq("id", user_id).single().execute()
        if user_row.data:
            earlier = db.table("users").select("id", count="exact") \
                .lt("created_at", user_row.data["created_at"]).execute()
            if (earlier.count or 0) < 1000:
                earned.append("founding_writer")
    except Exception:
        pass

    return [
        {"id": b, **BADGE_CATALOG[b]}
        for b in earned if b in BADGE_CATALOG
    ]


# ─────────────────────────────────────────────────────────────────────────
# WRAPPED — annual personalized recap
# ─────────────────────────────────────────────────────────────────────────
async def compute_wrapped(user_id: str, year: int) -> dict:
    db = get_db()
    if not db:
        return {"year": year, "empty": True}

    try:
        caps = db.table("capsules").select(
            "id,title,mood,category,status,sealed_at,reveal_date,revealed_at,view_count"
        ).eq("user_id", user_id).execute().data or []
    except Exception:
        caps = []

    year_caps = [c for c in caps if c.get("sealed_at") and c["sealed_at"].startswith(str(year))]

    if not year_caps:
        return {"year": year, "empty": True, "total_lifetime": len(caps)}

    moods = Counter(c["mood"] for c in year_caps if c.get("mood"))
    cats = Counter(c["category"] for c in year_caps if c.get("category"))
    revealed = [c for c in year_caps if c["status"] == "revealed"]

    waits = []
    for c in year_caps:
        if c.get("sealed_at") and c.get("reveal_date"):
            try:
                s = datetime.fromisoformat(c["sealed_at"].replace("Z", "+00:00"))
                r = datetime.fromisoformat(c["reveal_date"].replace("Z", "+00:00"))
                waits.append((r - s).days)
            except Exception:
                pass

    cap_ids = [c["id"] for c in year_caps]
    total_echoes = 0
    total_reactions = 0
    try:
        if cap_ids:
            e = db.table("capsule_echoes").select("id", count="exact").in_("capsule_id", cap_ids).execute()
            total_echoes = e.count or 0
            r = db.table("reactions").select("id", count="exact").in_("capsule_id", cap_ids).execute()
            total_reactions = r.count or 0
    except Exception:
        pass

    most_viewed = max(year_caps, key=lambda c: c.get("view_count", 0), default=None)
    badges = await compute_badges(user_id)

    return {
        "year": year,
        "empty": False,
        "total_sealed": len(year_caps),
        "total_revealed": len(revealed),
        "dominant_mood": moods.most_common(1)[0][0] if moods else None,
        "dominant_category": cats.most_common(1)[0][0] if cats else None,
        "longest_wait_days": max(waits) if waits else None,
        "shortest_wait_days": min(waits) if waits else None,
        "total_echoes": total_echoes,
        "total_reactions": total_reactions,
        "most_viewed_title": most_viewed["title"] if most_viewed else None,
        "badges_earned": badges,
        "first_capsule_title": year_caps[0]["title"] if year_caps else None,
    }
