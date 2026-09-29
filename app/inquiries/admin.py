from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.context import admin_context
from app.auth.deps import require_admin, verify_csrf
from app.auth.models import User
from app.db import get_session
from app.htmx import is_htmx
from app.inquiries.models import STAGES, Inquiry
from app.templating import templates

router = APIRouter(
    prefix="/admin/inquiries", dependencies=[Depends(verify_csrf), Depends(require_admin)]
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
