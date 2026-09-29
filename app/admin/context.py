from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.inquiries.models import STAGES, Inquiry


async def admin_context(
    request: Request, session: AsyncSession, user: User, section: str, title: str, **extra
) -> dict:
    unread = await session.scalar(
        select(func.count())
        .select_from(Inquiry)
        .where(Inquiry.read_at.is_(None), ~Inquiry.archived)
    )
    return {
        "csrf_token": request.session["csrf"],
        "unread_count": unread,
        "user": user,
        "section": section,
        "title": title,
        "stages": STAGES,
        **extra,
    }
