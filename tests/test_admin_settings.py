from sqlalchemy import select

from app.assets.models import Asset
from app.site.models import SiteSettings

HX = {"HX-Request": "true"}
VALID = {
    "contact_email": "hello@dhmgroup.net",
    "phone": "+260 770 005 939",
    "address": "Plot 4280 Chikola Loop Area\nChingola, Zambia",
    "notify_email": "Leads@DHMGroup.net",
    "linkedin_url": "https://www.linkedin.com/company/dhmgroup",
    "facebook_url": "   ",
    "instagram_url": "",
    "x_url": "",
    "tiktok_url": "",
    "youtube_url": "",
}


async def image(session, alt="DHM logo", ctype="image/png") -> Asset:
    asset = Asset(
        key=f"uploads/{alt or 'no-alt'}-{ctype.replace('/', '-')}.bin",
        filename="x.png",
        content_type=ctype,
        size_bytes=10,
        alt_text=alt,
    )
    session.add(asset)
    await session.commit()
    return asset


async def test_settings_page_shows_defaults_when_unseeded(admin_client):
    t = (await admin_client.get("/admin/settings")).text
    assert 'value="contact@dhmgroup.net"' in t


async def test_save_creates_row_and_normalises(admin_client, session):
    r = await admin_client.post("/admin/settings", data=VALID, headers=HX)
    assert r.status_code == 200
    site = await session.get(SiteSettings, 1)
    assert site.contact_email == "hello@dhmgroup.net"
    assert site.notify_email == "leads@dhmgroup.net"
    assert site.facebook_url is None and site.instagram_url is None


async def test_invalid_values_show_errors(admin_client, session):
    r = await admin_client.post(
        "/admin/settings",
        data={
            **VALID,
            "phone": "0770 005 939",
            "x_url": "javascript:alert(1)",
            "contact_email": "nope",
        },
        headers=HX,
    )
    assert r.status_code == 422
    assert "international format" in r.text
    assert "Use a full https:// link." in r.text
    assert "Enter an email like" in r.text
    assert await session.get(SiteSettings, 1) is None


async def test_slot_requires_image_with_alt_text(admin_client, session):
    no_alt = await image(session, alt="")
    r = await admin_client.post(
        "/admin/settings", data={**VALID, "logo_asset_id": str(no_alt.id)}, headers=HX
    )
    assert r.status_code == 422
    assert "alt text" in r.text
    pdf = await image(session, alt="Brochure", ctype="application/pdf")
    r = await admin_client.post(
        "/admin/settings", data={**VALID, "logo_asset_id": str(pdf.id)}, headers=HX
    )
    assert r.status_code == 422


async def test_slots_drive_public_page(admin_client, client, session):
    logo = await image(session)
    await admin_client.post(
        "/admin/settings", data={**VALID, "logo_asset_id": str(logo.id)}, headers=HX
    )
    t = (await client.get("/")).text
    assert logo.url in t
    assert "/static/img/tagline.png" in t  # unset slot keeps its fallback
    assert "https://www.facebook.com" not in t  # emptied social link is gone


async def test_used_asset_cannot_be_deleted(admin_client, session):
    logo = await image(session)
    await admin_client.post(
        "/admin/settings", data={**VALID, "logo_asset_id": str(logo.id)}, headers=HX
    )
    r = await admin_client.post(f"/admin/assets/{logo.id}/delete", headers=HX)
    assert r.status_code == 409
    assert "Used as the site logo" in r.text
    assert await session.scalar(select(Asset).where(Asset.id == logo.id)) is not None


async def test_empty_links_render_as_empty_inputs(admin_client):
    r = await admin_client.post("/admin/settings", data=VALID, headers=HX)
    assert 'name="facebook_url" type="url" value=""' in r.text
    assert "None" not in r.text
