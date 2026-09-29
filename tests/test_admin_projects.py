from sqlalchemy import select

from app.projects.models import Project
from app.seed import seed

HX = {"HX-Request": "true"}
NEW = {
    "name": "Mobi Pay",
    "summary": "Payments for market traders.",
    "url": "https://mobipay.dhmgroup.net",
    "ios_url": "",
    "android_url": "  ",
    "status": "coming_soon",
    "is_published": "true",
}


async def names(session):
    stmt = select(Project.name).order_by(Project.sort_order, Project.id)
    return (await session.scalars(stmt)).all()


async def test_list_in_order(admin_client, session):
    await seed(session)
    t = (await admin_client.get("/admin/projects")).text
    assert t.index("Pepaala News") < t.index("Nchito")


async def test_create_goes_last_and_public(admin_client, client, session):
    await seed(session)
    r = await admin_client.post("/admin/projects", data=NEW, headers=HX)
    assert r.status_code == 200
    assert await names(session) == ["Pepaala News", "Nchito", "Mobi Pay"]
    project = await session.scalar(select(Project).where(Project.name == "Mobi Pay"))
    assert project.android_url is None
    t = (await client.get("/")).text
    assert "Mobi Pay" in t and "Coming soon" in t


async def test_bad_links_rejected(admin_client, session):
    r = await admin_client.post(
        "/admin/projects", data={**NEW, "ios_url": "javascript:alert(1)"}, headers=HX
    )
    assert r.status_code == 422
    assert "Use a full https:// link." in r.text
    assert await session.scalar(select(Project)) is None


async def test_move_up_down_and_edges(admin_client, session):
    await seed(session)
    nchito = await session.scalar(select(Project).where(Project.name == "Nchito"))
    pepaala = await session.scalar(select(Project).where(Project.name == "Pepaala News"))
    await admin_client.post(
        f"/admin/projects/{nchito.id}/move", data={"direction": "up"}, headers=HX
    )
    assert await names(session) == ["Nchito", "Pepaala News"]
    r = await admin_client.post(
        f"/admin/projects/{nchito.id}/move", data={"direction": "up"}, headers=HX
    )
    assert r.status_code == 200
    assert await names(session) == ["Nchito", "Pepaala News"]
    await admin_client.post(
        f"/admin/projects/{pepaala.id}/move", data={"direction": "down"}, headers=HX
    )
    assert await names(session) == ["Nchito", "Pepaala News"]


async def test_update_and_delete(admin_client, session):
    await seed(session)
    project = await session.scalar(select(Project).where(Project.name == "Nchito"))
    r = await admin_client.post(
        f"/admin/projects/{project.id}",
        data={
            **NEW,
            "name": "Nchito",
            "status": "live",
            "ios_url": "https://apps.apple.com/app/id1",
        },
        headers=HX,
    )
    assert r.status_code == 200
    await session.refresh(project)
    assert project.ios_url == "https://apps.apple.com/app/id1"
    await admin_client.post(f"/admin/projects/{project.id}/delete", headers=HX)
    assert await names(session) == ["Pepaala News"]


async def test_new_project_form(admin_client):
    r = await admin_client.get("/admin/projects/new")
    assert r.status_code == 200
    assert 'action="/admin/projects"' in r.text
