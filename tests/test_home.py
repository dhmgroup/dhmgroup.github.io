from sqlalchemy import select

from app.db import get_session
from app.legal.models import LegalPage
from app.main import app
from app.projects.models import Project, ProjectStatus
from app.seed import seed
from app.site.models import SiteSettings


async def test_home_renders_seeded_content(client, session):
    await seed(session)
    r = await client.get("/")
    assert r.status_code == 200
    t = r.text
    assert "We don’t only build apps." in t
    assert 'href="mailto:contact@dhmgroup.net"' in t
    assert 'href="tel:+260770005939"' in t
    assert "Plot 4280 Chikola Loop Area,<br>" in t
    assert "Pepaala News" in t and "Nchito" in t
    assert 'href="/legal/privacy"' in t and 'href="/legal/terms"' in t
    assert '"@type": "Organization"' in t or '"@type":"Organization"' in t
    assert "/static/dist/app.css" in t


async def test_home_renders_without_seed(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "contact@dhmgroup.net" in r.text


async def test_store_buttons(client, session):
    await seed(session)
    pepaala = await session.scalar(select(Project).where(Project.name == "Pepaala News"))
    pepaala.ios_url = "https://apps.apple.com/app/id123"
    await session.commit()
    t = (await client.get("/")).text
    assert 'href="https://apps.apple.com/app/id123"' in t
    assert t.count('aria-disabled="true"') == 3  # Pepaala Android + Nchito iOS/Android


async def test_hidden_and_coming_soon_projects(client, session):
    await seed(session)
    session.add_all(
        [
            Project(name="Draft App", summary="s", is_published=False),
            Project(name="Old App", summary="s", status=ProjectStatus.RETIRED),
            Project(name="Next App", summary="s", status=ProjectStatus.COMING_SOON, sort_order=9),
        ]
    )
    await session.commit()
    t = (await client.get("/")).text
    assert "Draft App" not in t
    assert "Old App" not in t
    assert "Next App" in t and "Coming soon" in t


async def test_project_text_is_escaped(client, session):
    session.add(Project(name='<b>Bold</b> & "Co"', summary="<script>x()</script>"))
    await session.commit()
    t = (await client.get("/")).text
    assert "<b>Bold</b>" not in t
    assert "&lt;b&gt;Bold&lt;/b&gt; &amp;" in t
    assert "<script>x()</script>" not in t


async def test_empty_social_hidden_everywhere(client, session):
    await seed(session)
    (await session.get(SiteSettings, 1)).instagram_url = ""
    await session.commit()
    t = (await client.get("/")).text
    assert "instagram.com" not in t
    assert t.count('aria-label="LinkedIn"') == 2  # quote panel + footer


async def test_unpublished_legal_not_in_footer(client, session):
    await seed(session)
    terms = await session.scalar(select(LegalPage).where(LegalPage.slug == "terms"))
    terms.is_published = False
    await session.commit()
    t = (await client.get("/")).text
    assert 'href="/legal/terms"' not in t


async def test_database_error_renders_500_page(client):
    class DeadSession:
        async def get(self, *_):
            raise OSError("connection refused")

    async def dead():
        yield DeadSession()

    app.dependency_overrides[get_session] = dead
    r = await client.get("/")
    assert r.status_code == 500
    assert "Something went wrong on our side." in r.text


async def test_quote_form_is_htmx_and_has_fallback(client):
    t = (await client.get("/")).text
    assert 'hx-post="/inquiries"' in t
    assert 'method="post"' in t and 'action="/inquiries"' in t
    assert 'hx-target="#quote-panel"' in t
    assert 'name="website"' in t  # honeypot
    assert "/static/vendor/htmx/htmx.min.js" in t
    assert 'id="form-done"' not in t


async def test_sent_flag_shows_confirmation(client):
    t = (await client.get("/?sent=1")).text
    assert 'id="form-done"' in t
    assert "Request received." in t
    assert 'id="quote-form"' not in t


async def test_faq_is_rendered_with_server_side_schema(client):
    t = (await client.get("/")).text
    assert t.count("<details ") == 7
    assert "FAQPage" in t
    assert "How much does a website or app cost?" in t
