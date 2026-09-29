import logging
from email.message import EmailMessage
from email.utils import formataddr

import aiosmtplib

from app.config import settings
from app.db import SessionLocal, utcnow
from app.inquiries.models import Inquiry
from app.site.models import get_site_settings

logger = logging.getLogger("app.inquiries")


def build_message(inquiry: Inquiry, to: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Quote request from {inquiry.name}"
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Reply-To"] = formataddr((inquiry.name, inquiry.email))
    services = ", ".join(inquiry.services) or "Not specified"
    msg.set_content(
        f"Name: {inquiry.name}\n"
        f"Email: {inquiry.email}\n"
        f"Company: {inquiry.company or '-'}\n"
        f"Services: {services}\n\n"
        f"{inquiry.message}\n"
    )
    return msg


async def notify_inquiry(inquiry_id: int, session_factory=SessionLocal) -> None:
    """Email the team about a saved inquiry. Runs as a background task after the commit."""
    async with session_factory() as session:
        inquiry = await session.get(Inquiry, inquiry_id)
        if inquiry is None:
            return
        site = await get_site_settings(session)
        try:
            await aiosmtplib.send(
                build_message(inquiry, site.notify_email),
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username or None,
                password=settings.smtp_password or None,
                use_tls=settings.smtp_tls,
                start_tls=settings.smtp_starttls,
            )
        except (aiosmtplib.SMTPException, OSError):
            logger.exception("Could not send the notification for inquiry %s", inquiry_id)
            return
        inquiry.notified_at = utcnow()
        await session.commit()
