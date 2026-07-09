"""Post-meeting email recap.

Sends the bilingual summary + action items to the meeting's creator once
processing completes. When SMTP isn't configured, the recap is logged to the
console instead of sent, so the feature is testable without mail credentials.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import settings
from ..database import SessionLocal
from ..models import Meeting

logger = logging.getLogger("neu.email")


def _render_html(meeting: Meeting) -> str:
    s = meeting.summary
    overview = (s.overview_en if s else None) or "Summary not available."
    overview_ta = (s.overview_ta if s else None) or ""

    def li(items):
        return "".join(f"<li>{_esc(x)}</li>" for x in (items or []))

    actions = ""
    if s and s.action_items:
        rows = "".join(
            f"<tr><td>{_esc(a.get('task',''))}</td><td>{_esc(a.get('owner',''))}</td>"
            f"<td>{_esc(a.get('due',''))}</td></tr>"
            for a in s.action_items
        )
        actions = (
            "<h3>Action items</h3><table cellpadding='6' style='border-collapse:collapse'>"
            "<tr><th align='left'>Task</th><th align='left'>Owner</th><th align='left'>Due</th></tr>"
            f"{rows}</table>"
        )

    decisions = f"<h3>Decisions</h3><ul>{li(s.decisions)}</ul>" if s and s.decisions else ""
    key_points = f"<h3>Key points</h3><ul>{li(s.key_points)}</ul>" if s and s.key_points else ""

    return f"""\
<div style="font-family:system-ui,Segoe UI,sans-serif;max-width:640px;margin:auto;color:#1a1a1a">
  <h2>{_esc(meeting.title)}</h2>
  <p style="color:#666">Neu AI meeting recap</p>
  <h3>Overview</h3>
  <p>{_esc(overview)}</p>
  {f'<p style="color:#444">{_esc(overview_ta)}</p>' if overview_ta else ''}
  {actions}
  {decisions}
  {key_points}
  <hr>
  <p style="color:#888;font-size:12px">Sent by Neu AI — Tamil · English · Tanglish meeting assistant</p>
</div>"""


def _esc(text) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _send_smtp(to_email: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText("Your Neu AI meeting recap is ready. View it in the app.", "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        if settings.smtp_starttls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, [to_email], msg.as_string())


def send_recap(meeting_id: str) -> None:
    """Send (or log) the recap for a completed meeting. Safe to call from the
    pipeline; never raises into the caller."""
    db = SessionLocal()
    try:
        meeting = db.get(Meeting, meeting_id)
        if meeting is None or meeting.created_by is None:
            return
        from ..models import User

        creator = db.get(User, meeting.created_by)
        if creator is None or "@localhost" in creator.email:
            return  # dev user — nothing to email

        subject = f"[Neu AI] Recap: {meeting.title}"
        html = _render_html(meeting)

        if not settings.smtp_host:
            logger.info(
                "Email recap (SMTP not configured) for %s -> %s\n%s",
                meeting.title, creator.email, _plaintext(meeting),
            )
            return
        _send_smtp(creator.email, subject, html)
        logger.info("Recap emailed to %s for '%s'", creator.email, meeting.title)
    except Exception:
        logger.exception("Failed to send recap for %s", meeting_id)
    finally:
        db.close()


def _plaintext(meeting: Meeting) -> str:
    s = meeting.summary
    if not s:
        return "(no summary)"
    lines = [s.overview_en or ""]
    if s.action_items:
        lines.append("Action items:")
        lines += [f"  - {a.get('task')} ({a.get('owner')}, {a.get('due')})" for a in s.action_items]
    return "\n".join(lines)
