from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.legal.routes import published_pages
from app.projects.models import Project, ProjectStatus
from app.site.models import SiteSettings, get_site_settings
from app.templating import APP_DIR, templates

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


@router.get("/app-ads.txt")
async def app_ads() -> FileResponse:
    return FileResponse(APP_DIR / "static" / "app-ads.txt", media_type="text/plain")


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots() -> str:
    base = settings.base_url.rstrip("/")
    return f"User-agent: *\nDisallow: /admin\nSitemap: {base}/sitemap.xml\n"


@router.get("/sitemap.xml")
async def sitemap(session: AsyncSession = Depends(get_session)) -> Response:
    base = settings.base_url.rstrip("/")
    urls = [f"{base}/"] + [f"{base}/legal/{p.slug}" for p in await published_pages(session)]
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{escape(u)}</loc></url>\n" for u in urls)
        + "</urlset>\n"
    )
    return Response(body, media_type="application/xml")
