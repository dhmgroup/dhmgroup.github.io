"""Default content. Inserts only what is missing, so re-running never overwrites edits."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.legal.models import LegalPage
from app.projects.models import Project, ProjectStatus
from app.site.models import DEFAULTS, SiteSettings

LEGAL_PAGES = [
    {
        "slug": "privacy",
        "title": "Privacy policy",
        "sort_order": 0,
        "is_published": True,
        "body_md": (
            "When you request a quote, we collect your name, email address, company name and "
            "the project details you choose to share. We use them only to reply to you and "
            "prepare your quote.\n\n"
            "We do not sell your information or share it with advertisers. This website does "
            "not use tracking cookies.\n\n"
            "To see, correct or delete the information we hold about you, email us and we will "
            "act on your request.\n"
        ),
    },
    {
        "slug": "terms",
        "title": "Terms of use",
        "sort_order": 1,
        "is_published": True,
        "body_md": (
            "The content on this website is provided for general information about DHM Group "
            "and its services. It is not a binding offer; the terms of any project are set out "
            "in its written quote.\n\n"
            "The DHM Group name, logo, Pepaala News and Nchito are the property of DHM Group "
            "and may not be used without permission.\n"
        ),
    },
]

PROJECTS = [
    {
        "name": "Pepaala News",
        "url": "https://pepaala.dhmgroup.net",
        "summary": (
            "Zambian news from across the country, gathered into one feed you can read in a "
            "few minutes."
        ),
        "status": ProjectStatus.LIVE,
        "sort_order": 0,
    },
    {
        "name": "Nchito",
        "url": "https://nchito.dhmgroup.net",
        "summary": (
            "A job board that puts open roles from Zambian employers in front of job seekers, "
            "right on their phone."
        ),
        "status": ProjectStatus.LIVE,
        "sort_order": 1,
    },
]


async def seed(session: AsyncSession) -> None:
    if await session.get(SiteSettings, 1) is None:
        session.add(SiteSettings(id=1, **DEFAULTS))

    slugs = set((await session.scalars(select(LegalPage.slug))).all())
    session.add_all(LegalPage(**p) for p in LEGAL_PAGES if p["slug"] not in slugs)

    names = set((await session.scalars(select(Project.name))).all())
    session.add_all(Project(**p) for p in PROJECTS if p["name"] not in names)

    await session.commit()
