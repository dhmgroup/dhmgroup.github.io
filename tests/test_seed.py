from sqlalchemy import func, select

from app.legal.models import LegalPage
from app.projects.models import Project, ProjectStatus
from app.seed import seed
from app.site.models import SiteSettings


async def test_seed_creates_default_content(session):
    await seed(session)
    settings = await session.get(SiteSettings, 1)
    assert settings.contact_email == "contact@dhmgroup.net"
    assert settings.youtube_url == "https://www.youtube.com/@dhmgroup"
    slugs = (await session.scalars(select(LegalPage.slug).order_by(LegalPage.sort_order))).all()
    assert slugs == ["privacy", "terms"]
    names = (await session.scalars(select(Project.name).order_by(Project.sort_order))).all()
    assert names == ["Pepaala News", "Nchito"]
    pepaala = await session.scalar(select(Project).where(Project.name == "Pepaala News"))
    assert pepaala.status is ProjectStatus.LIVE
    assert pepaala.url == "https://pepaala.dhmgroup.net"


async def test_seed_is_idempotent_and_keeps_edits(session):
    await seed(session)
    settings = await session.get(SiteSettings, 1)
    settings.phone = "+260 999 999 999"
    await session.commit()

    await seed(session)

    assert (await session.get(SiteSettings, 1)).phone == "+260 999 999 999"
    assert await session.scalar(select(func.count()).select_from(LegalPage)) == 2
    assert await session.scalar(select(func.count()).select_from(Project)) == 2
