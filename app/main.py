import logging
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.admin.routes import router as admin_router
from app.auth.deps import NotAuthenticated
from app.auth.routes import router as auth_router
from app.config import settings
from app.db import engine, get_session
from app.htmx import is_htmx
from app.inquiries.admin import router as inquiries_admin_router
from app.inquiries.routes import router as inquiries_router
from app.legal.routes import router as legal_router
from app.public.routes import router as public_router
from app.templating import APP_DIR, templates

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="dhm_admin",
    max_age=8 * 60 * 60,
    same_site="lax",
    https_only=settings.env == "production",
)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
app.include_router(legal_router)
app.include_router(public_router)
app.include_router(inquiries_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(inquiries_admin_router)


@app.exception_handler(NotAuthenticated)
async def not_authenticated(request: Request, exc: NotAuthenticated):
    target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    login = f"/admin/login?next={quote(target, safe='/?=&')}"
    if is_htmx(request):
        return Response(status_code=204, headers={"HX-Redirect": login})
    return RedirectResponse(login, status_code=303)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(request, "public/404.html", status_code=404)
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def server_error(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path, exc_info=exc)
    return templates.TemplateResponse(request, "public/500.html", status_code=500)


@app.get("/healthz")
async def healthz(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return JSONResponse({"status": "database unavailable"}, status_code=503)
    return {"status": "ok"}
