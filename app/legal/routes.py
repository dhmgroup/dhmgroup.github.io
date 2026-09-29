from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.legal.models import LegalPage
from app.templating import templates

router = APIRouter()


async def published_pages(session: AsyncSession) -> list[LegalPage]:
    result = await session.scalars(
        select(LegalPage).where(LegalPage.is_published).order_by(LegalPage.sort_order, LegalPage.id)
    )
    return list(result.all())


@router.get("/legal.html")
async def legacy_legal() -> RedirectResponse:
    return RedirectResponse("/legal/privacy", status_code=301)


@router.get("/legal/{slug}")
async def legal_page(slug: str, request: Request, session: AsyncSession = Depends(get_session)):
    pages = await published_pages(session)
    page = next((p for p in pages if p.slug == slug), None)
    if page is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request, "public/legal.html", {"page": page, "legal_pages": pages}
    )
