"""
Scheduled tasks using APScheduler.
- Every minute: auto-reveal capsules past their reveal_date
- Every Sunday 11 PM IST: generate Grey Guardian weekly chronicle
- Every night 10 PM IST: select tomorrow's Court session
- Every night 10 PM IST: send reveal notifications
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from app.core.database import get_db_direct
from app.services.guardian_service import GuardianService
from app.services.notification_service import NotificationService

IST = pytz.timezone("Asia/Kolkata")


async def auto_reveal_capsules():
    """Reveal capsules whose reveal_date has passed."""
    db = await get_db_direct()
    try:
        # Call the SQL function we created in migrations
        await db.rpc("auto_reveal_capsules").execute()

        # Get newly revealed capsules to send notifications
        newly_revealed = await db.table("capsules") \
            .select("id,user_id,title") \
            .eq("status", "revealed") \
            .is_("revealed_at", "not.null") \
            .execute()

        for capsule in (newly_revealed.data or []):
            await NotificationService.send_reveal_notification(
                user_id=capsule["user_id"],
                capsule_title=capsule["title"],
            )

    except Exception as e:
        print(f"[Scheduler] auto_reveal error: {e}")


async def generate_weekly_guardian():
    """Generate the Grey Guardian weekly chronicle."""
    try:
        print("[Scheduler] Generating weekly Guardian chronicle...")
        report = await GuardianService.generate_weekly_chronicle()
        print(f"[Scheduler] Guardian report generated: {report.get('id')}")
    except Exception as e:
        print(f"[Scheduler] Guardian generation error: {e}")


async def select_court_session():
    """Pick tomorrow's Court story from recently revealed capsules."""
    db = await get_db_direct()
    from datetime import datetime, timedelta
    import random

    try:
        tomorrow = datetime.now(IST).date() + timedelta(days=1)
        tomorrow_10pm = IST.localize(
            datetime(tomorrow.year, tomorrow.month, tomorrow.day, 22, 0, 0)
        )

        # Check if already scheduled
        existing = await db.table("court_sessions") \
            .select("id") \
            .gte("scheduled_for", tomorrow_10pm.isoformat()) \
            .execute()

        if existing.data:
            return

        # Pick from recently revealed public capsules not yet in court
        used_ids = await db.table("court_sessions") \
            .select("capsule_id") \
            .execute()
        used = [r["capsule_id"] for r in (used_ids.data or [])]

        candidates = await db.table("capsules") \
            .select("id") \
            .eq("status", "revealed") \
            .eq("is_public", True) \
            .not_.in_("id", used if used else ["none"]) \
            .limit(20) \
            .execute()

        if not candidates.data:
            return

        chosen = random.choice(candidates.data)

        await db.table("court_sessions").insert({
            "capsule_id": chosen["id"],
            "scheduled_for": tomorrow_10pm.isoformat(),
            "status": "pending",
        }).execute()

        print(f"[Scheduler] Court session created for {tomorrow}: capsule {chosen['id']}")

    except Exception as e:
        print(f"[Scheduler] Court selection error: {e}")


async def activate_todays_court():
    """Activate today's court session at 10 PM IST."""
    db = await get_db_direct()
    from datetime import datetime

    try:
        today_str = datetime.now(IST).strftime("%Y-%m-%d")

        session = await db.table("court_sessions") \
            .select("id,capsule_id") \
            .gte("scheduled_for", f"{today_str}T22:00:00+05:30") \
            .lt("scheduled_for", f"{today_str}T23:59:59+05:30") \
            .eq("status", "pending") \
            .single() \
            .execute()

        if session.data:
            await db.table("court_sessions") \
                .update({"status": "active"}) \
                .eq("id", session.data["id"]) \
                .execute()

            # Notify the capsule author
            capsule = await db.table("capsules") \
                .select("user_id,title") \
                .eq("id", session.data["capsule_id"]) \
                .single() \
                .execute()

            if capsule.data:
                await NotificationService.send_court_notification(
                    user_id=capsule.data["user_id"],
                    capsule_title=capsule.data["title"],
                )

    except Exception as e:
        print(f"[Scheduler] Court activation error: {e}")


def start_scheduler() -> AsyncIOScheduler:
    """Configure and start all scheduled jobs."""
    scheduler = AsyncIOScheduler(timezone=IST)

    # Auto-reveal: every minute
    scheduler.add_job(
        auto_reveal_capsules,
        trigger="interval",
        minutes=1,
        id="auto_reveal",
    )

    # Weekly Guardian: Sunday 11 PM IST
    scheduler.add_job(
        generate_weekly_guardian,
        trigger=CronTrigger(day_of_week="sun", hour=23, minute=0, timezone=IST),
        id="weekly_guardian",
    )

    # Court selection: daily 9 PM IST (pick tomorrow's story)
    scheduler.add_job(
        select_court_session,
        trigger=CronTrigger(hour=21, minute=0, timezone=IST),
        id="court_selection",
    )

    # Court activation: daily 10 PM IST
    scheduler.add_job(
        activate_todays_court,
        trigger=CronTrigger(hour=22, minute=0, timezone=IST),
        id="court_activation",
    )

    scheduler.start()
    print("[Scheduler] All jobs started.")
    return scheduler
