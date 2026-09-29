from datetime import UTC, datetime, timedelta

from app.inquiries.models import Inquiry, InquiryStage

HX = {"HX-Request": "true"}


def lead(**kw) -> Inquiry:
    return Inquiry(**{"name": "Chanda", "email": "c@x.co", "message": "m", **kw})


async def test_list_defaults_to_new_with_counts(admin_client, session):
    session.add_all(
        [
            lead(name="Alpha"),
            lead(name="Bravo", stage=InquiryStage.QUOTED),
            lead(name="Charlie", archived=True),
        ]
    )
    await session.commit()
    t = (await admin_client.get("/admin/inquiries")).text
    assert "Alpha" in t and "Bravo" not in t and "Charlie" not in t
    assert 'data-count-new="1"' in t and 'data-count-quoted="1"' in t
    assert 'data-count-archived="1"' in t


async def test_stage_tab_and_archived(admin_client, session):
    session.add_all(
        [lead(name="Bravo", stage=InquiryStage.QUOTED), lead(name="Charlie", archived=True)]
    )
    await session.commit()
    assert "Bravo" in (await admin_client.get("/admin/inquiries?stage=quoted")).text
    assert "Charlie" in (await admin_client.get("/admin/inquiries?stage=archived")).text


async def test_unknown_stage_falls_back_to_new(admin_client):
    assert (await admin_client.get("/admin/inquiries?stage=bogus")).status_code == 200


async def test_search_matches_name_email_company_literally(admin_client, session):
    session.add_all(
        [
            lead(name="Mwansa", company="100% Foods"),
            lead(name="Other", company="1000 Foods"),
            lead(name="Mail Match", email="boss@acme.zm"),
        ]
    )
    await session.commit()
    t = (await admin_client.get("/admin/inquiries?q=100%25")).text
    assert "Mwansa" in t and "Other" not in t
    assert "Mail Match" in (await admin_client.get("/admin/inquiries?q=acme")).text


async def test_htmx_returns_list_partial(admin_client, session):
    session.add(lead(name="Alpha"))
    await session.commit()
    r = await admin_client.get("/admin/inquiries?stage=new", headers=HX)
    assert r.status_code == 200
    assert r.text.lstrip().startswith('<section id="inquiry-list"')
    assert "<html" not in r.text


async def test_pagination(admin_client, session):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    session.add_all(
        [lead(name=f"Lead {n:03}", created_at=start + timedelta(minutes=n)) for n in range(55)]
    )
    await session.commit()
    first = (await admin_client.get("/admin/inquiries")).text
    assert "Lead 054" in first and "Lead 004" not in first and "page=2" in first
    second = (await admin_client.get("/admin/inquiries?page=2")).text
    assert "Lead 004" in second and "Lead 054" not in second


async def test_unread_rows_show_dot(admin_client, session):
    session.add_all([lead(name="Unread"), lead(name="Seen", read_at=datetime.now(UTC))])
    await session.commit()
    t = (await admin_client.get("/admin/inquiries")).text
    assert t.count('aria-label="Unread"') == 1
