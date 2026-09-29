from datetime import UTC, datetime

from app.inquiries.models import Inquiry, InquiryStage
from app.templating import local_time


def lead(**kw) -> Inquiry:
    return Inquiry(**{"name": "Chanda", "email": "c@x.co", "message": "m", **kw})


async def test_overview_lists_unread_and_needs_reply(admin_client, session):
    session.add_all(
        [
            lead(name="Unread New"),
            lead(name="Read New", read_at=datetime.now(UTC)),
            lead(name="Quoted Lead", stage=InquiryStage.QUOTED, read_at=datetime.now(UTC)),
            lead(name="Spam", archived=True),
        ]
    )
    await session.commit()
    r = await admin_client.get("/admin")
    assert r.status_code == 200
    t = r.text
    assert "Unread New" in t and "Read New" in t  # both are stage New = needs a reply
    assert "Quoted Lead" in t  # in progress
    assert "Spam" not in t
    assert 'data-unread-count="1"' in t  # nav badge counts unread, non-archived
    assert 'name="csrf-token"' in t
    assert "hx-headers:inherited=" in t


async def test_overview_empty_state(admin_client):
    t = (await admin_client.get("/admin")).text
    assert "No leads waiting" in t


def test_local_time_formats_in_lusaka():
    now = datetime(2026, 9, 29, 12, 5, tzinfo=UTC)
    assert local_time(datetime(2026, 9, 29, 9, 30, tzinfo=UTC), now=now) == "11:30"
    assert local_time(datetime(2026, 3, 1, 9, 0, tzinfo=UTC), now=now) == "1 Mar"
    assert local_time(datetime(2025, 3, 1, 9, 0, tzinfo=UTC), now=now) == "1 Mar 2025"
    assert (
        local_time(datetime(2026, 9, 29, 9, 30, tzinfo=UTC), "long", now=now)
        == "29 Sep 2026, 11:30"
    )


async def test_admin_does_not_swap_error_pages(admin_client):
    t = (await admin_client.get("/admin")).text
    assert '<meta name="htmx-config"' in t
    assert '"noSwap":[204,304,403,404,"5xx"]' in t


async def test_nav_lists_every_section(admin_client):
    t = (await admin_client.get("/admin")).text
    for href in (
        "/admin/inquiries",
        "/admin/legal",
        "/admin/projects",
        "/admin/settings",
        "/admin/assets",
    ):
        assert f'href="{href}"' in t


async def test_admin_404_uses_admin_error_page(admin_client):
    r = await admin_client.get("/admin/legal/999999")
    assert r.status_code == 404
    assert "Back to the admin" in r.text
    assert "Everything we do is on the home page" not in r.text


async def test_public_404_unchanged(client):
    r = await client.get("/no-such-page")
    assert "Everything we do is on the home page" in r.text
