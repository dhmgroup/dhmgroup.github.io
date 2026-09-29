from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.legal.routes import published_pages
from app.projects.models import Project, ProjectStatus
from app.site.models import SiteSettings, get_site_settings
from app.templating import templates

router = APIRouter()


def organization_ld(site: SiteSettings) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "DHM Group",
        "email": site.contact_email,
        "telephone": site.tel_href.removeprefix("tel:"),
        "address": {
            "@type": "PostalAddress",
            "streetAddress": site.address_one_line,
            "addressCountry": "ZM",
        },
        "sameAs": [url for _, _, url in site.socials],
    }


@router.get("/")
async def home(request: Request, session: AsyncSession = Depends(get_session)):
    site = await get_site_settings(session)
    projects = (
        await session.scalars(
            select(Project)
            .where(Project.is_published, Project.status != ProjectStatus.RETIRED)
            .order_by(Project.sort_order, Project.id)
        )
    ).all()
    return templates.TemplateResponse(
        request,
        "public/index.html",
        {
            "site": site,
            "projects": projects,
            "legal_pages": await published_pages(session),
            "org_ld": organization_ld(site),
        },
    )
