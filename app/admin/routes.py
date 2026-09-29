from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.context import admin_context
from app.auth.deps import require_admin, verify_csrf
from app.auth.models import User
from app.db import get_session
from app.inquiries.models import Inquiry, InquiryStage
from app.templating import templates

router = APIRouter(prefix="/admin", dependencies=[Depends(verify_csrf), Depends(require_admin)])


@router.get("")
async def overview(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    needs_reply = (
        await session.scalars(
            select(Inquiry)
            .where(Inquiry.stage == InquiryStage.NEW, ~Inquiry.archived)
            .order_by(Inquiry.created_at.desc())
            .limit(10)
        )
    ).all()
    in_progress = (
        await session.scalars(
            select(Inquiry)
            .where(
                Inquiry.stage.in_([InquiryStage.CONTACTED, InquiryStage.QUOTED]),
                ~Inquiry.archived,
            )
            .order_by(Inquiry.created_at.desc())
            .limit(10)
        )
    ).all()
    context = await admin_context(
        request,
        session,
        user,
        "overview",
        "Overview",
        needs_reply=needs_reply,
        in_progress=in_progress,
    )
    return templates.TemplateResponse(request, "admin/overview.html", context)
