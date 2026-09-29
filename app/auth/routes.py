import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.deps import safe_next, verify_csrf
from app.auth.models import User
from app.auth.users import hash_password, verify_password
from app.db import get_session, utcnow
from app.ratelimit import RateLimiter
from app.templating import templates

router = APIRouter(prefix="/admin")
login_limiter = RateLimiter(limit=5, window=900)
_DUMMY_HASH = hash_password("timing-equaliser-not-a-password")


def _render(request, *, email="", next_path="/admin", error="", status_code=200):
    request.session.setdefault("csrf", secrets.token_urlsafe(32))
    context = {
        "email": email,
        "next": next_path,
        "error": error,
        "csrf_token": request.session["csrf"],
    }
    return templates.TemplateResponse(request, "admin/login.html", context, status_code=status_code)


@router.get("/login")
async def login_page(request: Request, next: str | None = None):
    return _render(request, next_path=safe_next(next))


@router.post("/login")
async def login(request: Request, session: AsyncSession = Depends(get_session)):
    form = await request.form()
    email = str(form.get("email") or "").strip().lower()
    password = str(form.get("password") or "")
    next_path = safe_next(str(form.get("next") or ""))
    ip = request.client.host if request.client else "unknown"

    if not login_limiter.hit(f"{ip}|{email}"):
        return _render(
            request,
            email=email,
            next_path=next_path,
            status_code=429,
            error="Too many attempts. Wait 15 minutes and try again.",
        )

    user = await session.scalar(select(User).where(User.email == email))
    ok = await run_in_threadpool(
        verify_password, user.password_hash if user else _DUMMY_HASH, password
    )
    if not (user and ok and user.is_active):
        return _render(
            request,
            email=email,
            next_path=next_path,
            status_code=401,
            error="Email or password is incorrect.",
        )

    user.last_login_at = utcnow()
    await session.commit()
    request.session.clear()
    request.session.update(uid=user.id, csrf=secrets.token_urlsafe(32))
    return RedirectResponse(next_path, status_code=303)


@router.post("/logout", dependencies=[Depends(verify_csrf)])
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)
