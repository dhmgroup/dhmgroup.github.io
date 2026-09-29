import io

from sqlalchemy import select

from app.assets import storage
from app.assets.models import Asset

HX = {"HX-Request": "true"}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


async def upload(admin_client, data=PNG, name="logo.png", ctype="image/png", alt=""):
    return await admin_client.post(
        "/admin/assets",
        files={"file": (name, io.BytesIO(data), ctype)},
        data={"alt_text": alt},
        headers=HX,
    )


async def test_upload_stores_object_and_row(admin_client, session, admin):
    r = await upload(admin_client, alt="DHM logo")
    assert r.status_code == 200
    asset = await session.scalar(select(Asset))
    assert asset.key.startswith("uploads/") and asset.key.endswith(".png")
    assert (asset.filename, asset.content_type, asset.size_bytes) == (
        "logo.png",
        "image/png",
        len(PNG),
    )
    assert asset.alt_text == "DHM logo" and asset.uploaded_by == admin.id
    assert await storage.exists(asset.key)
    assert asset.url in r.text
    await storage.delete(asset.key)


async def test_extension_comes_from_content_not_name(admin_client, session):
    await upload(admin_client, name="evil.exe")
    asset = await session.scalar(select(Asset))
    assert asset.key.endswith(".png")
    await storage.delete(asset.key)


async def test_disguised_file_rejected(admin_client, session):
    r = await upload(admin_client, data=b"<!doctype html><script>alert(1)</script>", name="x.png")
    assert r.status_code == 415
    assert (await session.scalars(select(Asset))).all() == []


async def test_oversize_rejected(admin_client, session):
    r = await upload(admin_client, data=PNG + b"\x00" * (10 * 1024 * 1024))
    assert r.status_code == 413
    assert (await session.scalars(select(Asset))).all() == []


async def test_alt_text_update(admin_client, session):
    await upload(admin_client)
    asset = await session.scalar(select(Asset))
    r = await admin_client.post(
        f"/admin/assets/{asset.id}/alt", data={"alt_text": "  Logo  "}, headers=HX
    )
    assert r.status_code == 200
    await session.refresh(asset)
    assert asset.alt_text == "Logo"
    await storage.delete(asset.key)


async def test_delete_removes_row_and_object(admin_client, session):
    await upload(admin_client)
    asset = await session.scalar(select(Asset))
    key = asset.key
    r = await admin_client.post(f"/admin/assets/{asset.id}/delete", headers=HX)
    assert r.status_code == 200
    assert (await session.scalars(select(Asset))).all() == []
    assert not await storage.exists(key)


async def test_grid_lists_assets(admin_client, session):
    await upload(admin_client, alt="First")
    t = (await admin_client.get("/admin/assets")).text
    asset = await session.scalar(select(Asset))
    assert asset.url in t and "First" in t
    await storage.delete(asset.key)


async def test_assets_require_login(client):
    assert (await client.get("/admin/assets")).status_code == 303


async def test_filter_and_search(admin_client, session):
    session.add_all(
        [
            Asset(
                key="uploads/a.png",
                filename="logo.png",
                content_type="image/png",
                size_bytes=1,
                alt_text="Logo",
            ),
            Asset(
                key="uploads/b.png",
                filename="banner.png",
                content_type="image/png",
                size_bytes=1,
                alt_text="",
            ),
            Asset(
                key="uploads/c.pdf",
                filename="brochure.pdf",
                content_type="application/pdf",
                size_bytes=1,
            ),
        ]
    )
    await session.commit()
    names = lambda t: [n for n in ("logo.png", "banner.png", "brochure.pdf") if n in t]  # noqa: E731
    assert names((await admin_client.get("/admin/assets?kind=pdf", headers=HX)).text) == [
        "brochure.pdf"
    ]
    assert names((await admin_client.get("/admin/assets?kind=no-alt", headers=HX)).text) == [
        "banner.png"
    ]
    assert names((await admin_client.get("/admin/assets?q=LOGO", headers=HX)).text) == ["logo.png"]
    assert len(names((await admin_client.get("/admin/assets?kind=bogus", headers=HX)).text)) == 3
