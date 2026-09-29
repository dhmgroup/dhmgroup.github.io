from sqlalchemy import select

from app.legal.models import LegalPage
from app.seed import seed

HX = {"HX-Request": "true"}
NEW = {
    "title": "Cookie policy",
    "slug": "cookies",
    "body_md": "We use **no** tracking cookies.",
    "sort_order": "2",
    "is_published": "true",
}


async def test_list_shows_pages(admin_client, session):
    await seed(session)
    t = (await admin_client.get("/admin/legal")).text
    assert "Privacy policy" in t and "Terms of use" in t


async def test_create_page_then_public(admin_client, client, session):
    r = await admin_client.post("/admin/legal", data=NEW, headers=HX)
    assert r.status_code == 200
    page = await session.scalar(select(LegalPage).where(LegalPage.slug == "cookies"))
    assert page.is_published and page.sort_order == 2
    assert "<strong>no</strong>" in (await client.get("/legal/cookies")).text


async def test_unchecked_publish_means_draft(admin_client, session):
    data = {k: v for k, v in NEW.items() if k != "is_published"}
    await admin_client.post("/admin/legal", data=data, headers=HX)
    assert (await session.scalar(select(LegalPage))).is_published is False


async def test_duplicate_slug_is_a_field_error(admin_client, session):
    await seed(session)
    r = await admin_client.post("/admin/legal", data={**NEW, "slug": "privacy"}, headers=HX)
    assert r.status_code == 422
    assert "That address is already used" in r.text


async def test_bad_slug_rejected(admin_client):
    r = await admin_client.post("/admin/legal", data={**NEW, "slug": "Cookie Policy!"}, headers=HX)
    assert r.status_code == 422
    assert "lowercase letters, numbers and hyphens" in r.text


async def test_update_and_delete(admin_client, session):
    await seed(session)
    page = await session.scalar(select(LegalPage).where(LegalPage.slug == "terms"))
    r = await admin_client.post(
        f"/admin/legal/{page.id}", data={**NEW, "slug": "terms", "title": "Terms"}, headers=HX
    )
    assert r.status_code == 200
    await session.refresh(page)
    assert page.title == "Terms"
    r = await admin_client.post(f"/admin/legal/{page.id}/delete", headers=HX)
    assert r.status_code == 200
    assert await session.scalar(select(LegalPage).where(LegalPage.slug == "terms")) is None


async def test_preview_is_sanitised(admin_client):
    r = await admin_client.post(
        "/admin/legal/preview", data={"body_md": "## Hi\n\n<script>x()</script>"}, headers=HX
    )
    assert "<h2>Hi</h2>" in r.text
    assert "<script>" not in r.text


async def test_new_page_form(admin_client):
    r = await admin_client.get("/admin/legal/new")
    assert r.status_code == 200
    assert 'action="/admin/legal"' in r.text
