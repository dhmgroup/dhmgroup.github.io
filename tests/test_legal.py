from app.legal.models import LegalPage
from app.seed import seed


async def test_published_page_renders(client, session):
    await seed(session)
    r = await client.get("/legal/privacy")
    assert r.status_code == 200
    assert "<h1" in r.text and "Privacy policy" in r.text
    assert "We do not sell your information" in r.text
    assert "Last updated" in r.text
    assert 'href="/legal/terms"' in r.text


async def test_unpublished_page_is_404(client, session):
    session.add(LegalPage(slug="cookies", title="Cookies", body_md="x", is_published=False))
    await session.commit()
    r = await client.get("/legal/cookies")
    assert r.status_code == 404
    assert "This page does not exist." in r.text


async def test_unknown_page_is_404(client):
    assert (await client.get("/legal/nope")).status_code == 404


async def test_markdown_body_is_sanitised_on_page(client, session):
    session.add(
        LegalPage(
            slug="xss",
            title="Test",
            body_md="<script>alert(1)</script>\n\n[x](javascript:alert(1))",
            is_published=True,
        )
    )
    await session.commit()
    r = await client.get("/legal/xss")
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text
    assert 'href="javascript' not in r.text


async def test_old_legal_url_redirects(client):
    r = await client.get("/legal.html")
    assert r.status_code == 301
    assert r.headers["location"] == "/legal/privacy"
