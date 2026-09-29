import json
from typing import Literal
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.admin.context import admin_context
from app.auth.deps import require_admin, verify_csrf
from app.auth.models import User
from app.db import get_session, utcnow
from app.htmx import is_htmx
from app.inquiries.models import STAGES, EventKind, Inquiry, InquiryEvent
from app.inquiries.notify import notify_inquiry
from app.templating import templates

router = APIRouter(
    prefix="/admin/inquiries", dependencies=[Depends(require_admin), Depends(verify_csrf)]
)
PAGE_SIZE = 50
TABS = [*STAGES, "archived"]


def list_state(stage: str | None, q: str | None, page: int | None) -> tuple[str, str, int]:
    return (stage if stage in TABS else "new"), (q or "").strip()[:100], max(page or 1, 1)


def list_url(stage: str, q: str, page: int = 1) -> str:
    params = {"stage": stage, **({"q": q} if q else {}), **({"page": page} if page > 1 else {})}
    return f"/admin/inquiries?{urlencode(params)}"


async def load_list(session: AsyncSession, stage: str, q: str, page: int) -> dict:
    stmt = select(Inquiry)
    if q:
        stmt = stmt.where(
            or_(
                Inquiry.name.icontains(q, autoescape=True),
                Inquiry.email.icontains(q, autoescape=True),
                Inquiry.company.icontains(q, autoescape=True),
            )
        )
    count_stmt = stmt.with_only_columns(Inquiry.stage, Inquiry.archived, func.count()).group_by(
        Inquiry.stage, Inquiry.archived
    )
    counts = dict.fromkeys(TABS, 0)
    for s, archived, n in await session.execute(count_stmt):
        counts["archived" if archived else s] += n

    if stage == "archived":
        stmt = stmt.where(Inquiry.archived)
    else:
        stmt = stmt.where(~Inquiry.archived, Inquiry.stage == stage)
    rows = (
        await session.scalars(
            stmt.order_by(Inquiry.created_at.desc(), Inquiry.id.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE + 1)
        )
    ).all()
    return {
        "items": rows[:PAGE_SIZE],
        "has_next": len(rows) > PAGE_SIZE,
        "counts": counts,
        "tabs": TABS,
        "stage": stage,
        "q": q,
        "page": page,
        "list_url": list_url(stage, q, page),
        "page_url": lambda p: list_url(stage, q, p),
    }


@router.get("")
async def inquiries(
    request: Request,
    stage: str | None = None,
    q: str | None = None,
    page: int | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    listing = await load_list(session, *list_state(stage, q, page))
    if is_htmx(request):
        return templates.TemplateResponse(
            request, "admin/_inquiry_list.html", {**listing, "stages": STAGES}
        )
    context = await admin_context(
        request, session, user, "inquiries", "Inquiries", inquiry=None, **listing
    )
    return templates.TemplateResponse(request, "admin/inquiries.html", context)


REPLY_SUBJECT = "Re: Your quote request – DHM Group"


class StageForm(BaseModel):
    stage: Literal["new", "contacted", "quoted", "won", "lost"]


class NoteForm(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body", mode="before")
    @classmethod
    def _strip(cls, v):
        return str(v or "").strip()


class ArchiveForm(BaseModel):
    archived: bool


async def _get(session: AsyncSession, inquiry_id: int) -> Inquiry:
    inquiry = await session.scalar(
        select(Inquiry)
        .where(Inquiry.id == inquiry_id)
        .options(selectinload(Inquiry.events).joinedload(InquiryEvent.author))
        .execution_options(populate_existing=True)
    )
    if inquiry is None:
        raise HTTPException(status_code=404)
    return inquiry


def _panel_context(request: Request, inquiry: Inquiry, **extra) -> dict:
    mailto = f"mailto:{quote(inquiry.email, safe='@')}?subject={quote(REPLY_SUBJECT)}"
    return {
        "inquiry": inquiry,
        "stages": STAGES,
        "mailto": mailto,
        "note_error": "",
        "csrf_token": request.session["csrf"],
        **extra,
    }


async def _after_action(
    request, session, inquiry_id: int, toast: str, status_code: int = 200, **extra
):
    if not is_htmx(request):
        return RedirectResponse(f"/admin/inquiries/{inquiry_id}", status_code=303)
    inquiry = await _get(session, inquiry_id)
    response = templates.TemplateResponse(
        request,
        "admin/_inquiry_panel.html",
        _panel_context(request, inquiry, **extra),
        status_code=status_code,
    )
    if toast:
        response.headers["HX-Trigger"] = json.dumps({"inquiry-changed": True, "toast": toast})
    return response


def _event(inquiry: Inquiry, user: User | None, kind: EventKind, body: str) -> InquiryEvent:
    return InquiryEvent(
        inquiry_id=inquiry.id, author_id=user.id if user else None, kind=kind, body=body
    )


@router.get("/{inquiry_id}")
async def record(
    request: Request,
    inquiry_id: int,
    stage: str | None = None,
    q: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    inquiry = await _get(session, inquiry_id)
    if inquiry.read_at is None:
        inquiry.read_at = utcnow()
        await session.commit()
        inquiry = await _get(session, inquiry_id)
    if is_htmx(request):
        response = templates.TemplateResponse(
            request, "admin/_inquiry_panel.html", _panel_context(request, inquiry)
        )
        response.headers["HX-Trigger"] = json.dumps({"inquiry-changed": True})
        return response
    list_stage = "archived" if inquiry.archived else inquiry.stage.value
    listing = await load_list(session, *list_state(stage or list_stage, q, 1))
    context = await admin_context(
        request,
        session,
        user,
        "inquiries",
        inquiry.name,
        **listing,
        **_panel_context(request, inquiry),
    )
    return templates.TemplateResponse(request, "admin/inquiries.html", context)


@router.post("/{inquiry_id}/stage")
async def change_stage(
    request: Request,
    inquiry_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    try:
        form = StageForm.model_validate(dict(await request.form()))
    except ValidationError:
        raise HTTPException(status_code=422, detail="Unknown stage") from None
    inquiry = await _get(session, inquiry_id)
    if inquiry.stage == form.stage:
        return await _after_action(request, session, inquiry_id, "")
    old, new = STAGES[inquiry.stage][0], STAGES[form.stage][0]
    inquiry.stage = form.stage
    session.add(_event(inquiry, user, EventKind.STAGE, f"Moved from {old} to {new}"))
    await session.commit()
    return await _after_action(request, session, inquiry_id, f"Moved to {new}")


@router.post("/{inquiry_id}/notes")
async def add_note(
    request: Request,
    inquiry_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    inquiry = await _get(session, inquiry_id)
    try:
        form = NoteForm.model_validate(dict(await request.form()))
    except ValidationError:
        return await _after_action(
            request, session, inquiry_id, "", status_code=422, note_error="Write a note first."
        )
    session.add(_event(inquiry, user, EventKind.NOTE, form.body))
    await session.commit()
    return await _after_action(request, session, inquiry_id, "Note added")


@router.post("/{inquiry_id}/archive")
async def archive(
    request: Request,
    inquiry_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    try:
        form = ArchiveForm.model_validate(dict(await request.form()))
    except ValidationError:
        raise HTTPException(status_code=422, detail="archived must be true or false") from None
    inquiry = await _get(session, inquiry_id)
    if inquiry.archived != form.archived:
        inquiry.archived = form.archived
        body = "Archived" if form.archived else "Restored to the pipeline"
        session.add(_event(inquiry, user, EventKind.SYSTEM, body))
        await session.commit()
    toast = "Archived" if form.archived else "Restored"
    return await _after_action(request, session, inquiry_id, toast)


@router.post("/{inquiry_id}/resend")
async def resend(
    request: Request,
    inquiry_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    inquiry = await _get(session, inquiry_id)
    await notify_inquiry(inquiry_id)
    await session.refresh(inquiry)
    sent = inquiry.notified_at is not None
    body = "Notification resent" if sent else "Resend failed"
    session.add(_event(inquiry, user, EventKind.SYSTEM, body))
    await session.commit()
    toast = "Notification sent" if sent else "Notification still not sent. Check the SMTP settings."
    return await _after_action(request, session, inquiry_id, toast)
