"""
Email notifications via Resend.
Fails silently if RESEND_API_KEY isn't set, so the app never breaks
because of a missing email config — it just skips sending.
"""
from app.core.config import settings

FROM_ADDRESS = "The Grey Diary <hello@thegreydiary.online>"


def _send(to_email: str, subject: str, html: str):
    if not settings.RESEND_API_KEY or not to_email:
        return
    try:
        import resend
        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send({
            "from": FROM_ADDRESS,
            "to": [to_email],
            "subject": subject,
            "html": html,
        })
    except Exception:
        # Never let an email failure break the reveal/court flow
        pass


class NotificationService:

    @staticmethod
    async def send_reveal_notification(to_email: str, display_name: str, capsule_title: str, frontend_url: str):
        subject = "Your capsule has revealed: \u201c" + capsule_title + "\u201d"
        html = f"""
        <div style="background:#0B0B0D;padding:40px 20px;font-family:sans-serif;color:#F5F5F5">
          <div style="max-width:480px;margin:0 auto;background:#141417;border:1px solid rgba(196,168,74,.25);border-radius:16px;padding:32px">
            <div style="font-size:11px;color:#C4A84A;letter-spacing:.1em;text-transform:uppercase;margin-bottom:16px">The Grey Diary</div>
            <h1 style="font-family:Georgia,serif;font-style:italic;font-size:24px;color:#F0F0FA;margin:0 0 14px">The seal has broken.</h1>
            <p style="font-size:14px;color:#B0B0C8;line-height:1.7;margin:0 0 8px">Hi {display_name or "there"},</p>
            <p style="font-size:14px;color:#B0B0C8;line-height:1.7;margin:0 0 24px">
              The capsule you sealed — <em>&ldquo;{capsule_title}&rdquo;</em> — has just revealed.
              Time has had its say. Now it's your turn to add the Echo: what actually happened.
            </p>
            <a href="{frontend_url}/home/" style="display:inline-block;background:linear-gradient(135deg,#8B7CFF,#5A4FCC);color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;font-size:14px">
              Read it now
            </a>
          </div>
        </div>
        """
        _send(to_email, subject, html)

    @staticmethod
    async def send_court_notification(to_email: str, display_name: str, capsule_title: str, frontend_url: str):
        subject = "Your story is in The Court tonight"
        html = f"""
        <div style="background:#0B0B0D;padding:40px 20px;font-family:sans-serif;color:#F5F5F5">
          <div style="max-width:480px;margin:0 auto;background:#141417;border:1px solid rgba(139,124,255,.25);border-radius:16px;padding:32px">
            <div style="font-size:11px;color:#8B7CFF;letter-spacing:.1em;text-transform:uppercase;margin-bottom:16px">The Court</div>
            <h1 style="font-family:Georgia,serif;font-style:italic;font-size:24px;color:#F0F0FA;margin:0 0 14px">Your story is being heard tonight.</h1>
            <p style="font-size:14px;color:#B0B0C8;line-height:1.7;margin:0 0 24px">
              <em>&ldquo;{capsule_title}&rdquo;</em> was selected for tonight's Court session. The community will ask questions — you can answer as many as you'd like.
            </p>
            <a href="{frontend_url}/explore/" style="display:inline-block;background:linear-gradient(135deg,#8B7CFF,#5A4FCC);color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;font-size:14px">
              Open The Court
            </a>
          </div>
        </div>
        """
        _send(to_email, subject, html)
