import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db import get_session


class NotAuthenticated(Exception):
    """Raised by require_admin; app.main turns it into a redirect to the sign-in page."""


def safe_next(value: str | None) -> str:
    """Only same-site admin paths; anything else falls back to the overview."""
    if value and value.startswith("/admin") and "\\" not in value and not value.startswith("//"):
        return value
    return "/admin"


async def require_admin(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    uid = request.session.get("uid")
    user = await session.get(User, uid) if isinstance(uid, int) else None
    if user is None or not user.is_active:
        raise NotAuthenticated
    return user


async def verify_csrf(request: Request) -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    expected = request.session.get("csrf")
    sent = request.headers.get("X-CSRF-Token")
    if sent is None and request.headers.get("content-type", "").startswith(
        ("application/x-www-form-urlencoded", "multipart/form-data")
    ):
        sent = (await request.form()).get("csrf_token")
    if not expected or not secrets.compare_digest(str(sent or ""), expected):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
