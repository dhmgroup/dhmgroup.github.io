from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.context import admin_context
from app.admin.forms import Stripped, field_errors, hx_toast
from app.auth.deps import require_admin, verify_csrf
from app.auth.models import User
from app.db import get_session
from app.htmx import is_htmx
from app.legal.models import LegalPage
from app.legal.render import render_markdown
from app.templating import templates

router = APIRouter(
    prefix="/admin/legal", dependencies=[Depends(require_admin), Depends(verify_csrf)]
)
MESSAGES = {
    "title": "Give the page a title.",
    "slug": "Use lowercase letters, numbers and hyphens, for example cookie-policy.",
    "sort_order": "Use a number from 0 to 999.",
    "body_md": "Keep the page under 50,000 characters.",
}
DUPLICATE = "That address is already used by another page."


class LegalForm(BaseModel):
    title: Stripped = Field(min_length=1, max_length=200)
    slug: Stripped = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    body_md: str = Field(default="", max_length=50_000)
    sort_order: int = Field(default=0, ge=0, le=999)
    is_published: bool = False


async def _pages(session: AsyncSession):
    stmt = select(LegalPage).order_by(LegalPage.sort_order, LegalPage.id)
    return (await session.scalars(stmt)).all()


async def _get(session: AsyncSession, page_id: int) -> LegalPage:
    page = await session.get(LegalPage, page_id)
    if page is None:
        raise HTTPException(status_code=404)
    return page


def _blank() -> LegalPage:
    return LegalPage(title="", slug="", body_md="", sort_order=0, is_published=False)


async def _render(
    request, session, user, page, values=None, errors=None, status_code=200, toast=""
):
    """The editor panel for htmx requests, the full list + editor page otherwise."""
    context = {
        "page": page,
        "values": values or {},
        "errors": errors or {},
        "pages": await _pages(session),
        "csrf_token": request.session["csrf"],
    }
    if is_htmx(request):
        response = templates.TemplateResponse(
            request, "admin/_legal_editor.html", context, status_code=status_code
        )
    else:
        full = await admin_context(request, session, user, "legal", "Legal pages", **context)
        response = templates.TemplateResponse(
            request, "admin/legal.html", full, status_code=status_code
        )
    return hx_toast(response, toast, **{"legal-changed": True}) if toast else response


async def _save(request, session, user, page: LegalPage | None):
    data = dict(await request.form())
    shown = page or _blank()
    try:
        form = LegalForm.model_validate(data)
    except ValidationError as exc:
        return await _render(request, session, user, shown, data, field_errors(exc, MESSAGES), 422)
    target = page or LegalPage()
    for field, value in form.model_dump().items():
        setattr(target, field, value)
    if page is None:
        session.add(target)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        shown = await _get(session, page.id) if page else _blank()
        return await _render(request, session, user, shown, data, {"slug": DUPLICATE}, 422)
    if not is_htmx(request):
        return RedirectResponse(f"/admin/legal/{target.id}", status_code=303)
    toast = "Page saved" if page else "Page created"
    return await _render(request, session, user, target, toast=toast)


@router.get("")
async def legal_list(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    if is_htmx(request):
        context = {"pages": await _pages(session), "page": None}
        return templates.TemplateResponse(request, "admin/_legal_list.html", context)
    return await _render(request, session, user, None)


@router.get("/new")
async def new_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    return await _render(request, session, user, _blank())


@router.post("/preview", response_class=HTMLResponse)
async def preview(request: Request):
    return render_markdown(str((await request.form()).get("body_md") or ""))


@router.post("")
async def create(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    return await _save(request, session, user, None)


@router.get("/{page_id}")
async def edit(
    request: Request,
    page_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    return await _render(request, session, user, await _get(session, page_id))


@router.post("/{page_id}")
async def update(
    request: Request,
    page_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    return await _save(request, session, user, await _get(session, page_id))


@router.post("/{page_id}/delete")
async def delete(
    request: Request,
    page_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    await session.delete(await _get(session, page_id))
    await session.commit()
    if not is_htmx(request):
        return RedirectResponse("/admin/legal", status_code=303)
    return await _render(request, session, user, None, toast="Page deleted")
