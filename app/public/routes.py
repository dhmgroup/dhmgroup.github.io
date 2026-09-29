from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.inquiries.forms import SERVICES
from app.legal.routes import published_pages
from app.projects.models import Project, ProjectStatus
from app.site.models import SiteSettings, get_site_settings
from app.templating import APP_DIR, templates

router = APIRouter()


FAQS = [
    (
        "How much does a website or app cost?",
        "Every project is priced on its scope: the number of pages or screens, the features, "
        "and anything it connects to. Send the quote form and we reply with a written quote "
        "before any work starts.",
    ),
    (
        "How long does a project take?",
        "It depends on scope. A company website moves much faster than an app with accounts "
        "and payments on two platforms. Your quote includes a timeline with clear milestones.",
    ),
    (
        "Do you build for both iOS and Android?",
        "Yes. Our own apps, Pepaala News and Nchito, are live on the App Store and Google Play, "
        "and we take client apps through the same store review process.",
    ),
    (
        "Can I get email on my own domain?",
        "Yes. We set up business email on your domain so your team sends from name@yourcompany "
        "instead of a free address, and we manage the mailboxes for you.",
    ),
    (
        "Do you work with small businesses?",
        "Yes. We work with sole traders, growing companies, startups and larger organisations. "
        "Tell us what you need and we will scope something that fits your budget.",
    ),
    (
        "What happens after launch?",
        "We can host, monitor and update your website or app, the same way we look after our "
        "own products. Ongoing support is agreed as part of your quote.",
    ),
    (
        "What should I prepare before asking for a quote?",
        "A short description of what you want, who it is for, and any deadline. Links to sites "
        "or apps you like help too. You do not need a technical specification.",
    ),
]

FAQ_LD = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
        for q, a in FAQS
    ],
}


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


async def home_context(session: AsyncSession) -> dict:
    """Everything the landing page template needs; the inquiries route reuses it."""
    site = await get_site_settings(session)
    projects = (
        await session.scalars(
            select(Project)
            .where(Project.is_published, Project.status != ProjectStatus.RETIRED)
            .order_by(Project.sort_order, Project.id)
        )
    ).all()
    return {
        "site": site,
        "projects": projects,
        "legal_pages": await published_pages(session),
        "org_ld": organization_ld(site),
        "faqs": FAQS,
        "faq_ld": FAQ_LD,
        "quote_services": SERVICES,
        "form": None,
        "errors": {},
        "done": False,
    }


@router.get("/")
async def home(request: Request, sent: bool = False, session: AsyncSession = Depends(get_session)):
    context = await home_context(session)
    context["done"] = sent
    return templates.TemplateResponse(request, "public/index.html", context)


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
