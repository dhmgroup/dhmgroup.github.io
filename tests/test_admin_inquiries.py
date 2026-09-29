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


import json  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.inquiries import admin as inquiries_admin  # noqa: E402
from app.inquiries.models import EventKind, InquiryEvent  # noqa: E402


async def make_lead(session, **kw) -> Inquiry:
    inquiry = lead(**kw)
    session.add(inquiry)
    await session.commit()
    return inquiry


async def test_opening_marks_read_and_shows_record(admin_client, session):
    inquiry = await make_lead(
        session, name="Chanda Mulenga", services=["Website"], message="Line one\nLine two"
    )
    r = await admin_client.get(f"/admin/inquiries/{inquiry.id}")
    assert r.status_code == 200
    assert "Line one\nLine two" in r.text
    assert "mailto:c@x.co?subject=Re%3A%20Your%20quote%20request" in r.text
    await session.refresh(inquiry)
    assert inquiry.read_at is not None


async def test_htmx_record_is_panel_partial(admin_client, session):
    inquiry = await make_lead(session)
    r = await admin_client.get(f"/admin/inquiries/{inquiry.id}", headers=HX)
    assert r.text.lstrip().startswith('<section id="inquiry-panel"')


async def test_missing_record_is_404(admin_client):
    assert (await admin_client.get("/admin/inquiries/999999")).status_code == 404


async def test_stage_change_records_event_and_triggers(admin_client, session, admin):
    inquiry = await make_lead(session)
    r = await admin_client.post(
        f"/admin/inquiries/{inquiry.id}/stage", data={"stage": "contacted"}, headers=HX
    )
    assert r.status_code == 200
    trigger = json.loads(r.headers["HX-Trigger"])
    assert trigger["inquiry-changed"] is True
    assert trigger["toast"] == "Moved to Contacted"
    await session.refresh(inquiry)
    assert inquiry.stage == "contacted"
    event = await session.scalar(select(InquiryEvent))
    assert (event.kind, event.body, event.author_id) == (
        EventKind.STAGE,
        "Moved from New to Contacted",
        admin.id,
    )


async def test_same_stage_is_a_no_op(admin_client, session):
    inquiry = await make_lead(session)
    await admin_client.post(
        f"/admin/inquiries/{inquiry.id}/stage", data={"stage": "new"}, headers=HX
    )
    assert (await session.scalars(select(InquiryEvent))).all() == []


async def test_invalid_stage_is_422(admin_client, session):
    inquiry = await make_lead(session)
    r = await admin_client.post(
        f"/admin/inquiries/{inquiry.id}/stage", data={"stage": "bogus"}, headers=HX
    )
    assert r.status_code == 422


async def test_notes_append_with_author(admin_client, session, admin):
    inquiry = await make_lead(session)
    for body in ("Called, left voicemail", "Sent quote PDF"):
        r = await admin_client.post(
            f"/admin/inquiries/{inquiry.id}/notes", data={"body": body}, headers=HX
        )
        assert r.status_code == 200
    t = r.text
    assert t.index("Sent quote PDF") < t.index("Called, left voicemail")  # newest first
    notes = (
        await session.scalars(select(InquiryEvent).where(InquiryEvent.kind == EventKind.NOTE))
    ).all()
    assert {n.author_id for n in notes} == {admin.id}


async def test_empty_note_rejected(admin_client, session):
    inquiry = await make_lead(session)
    r = await admin_client.post(
        f"/admin/inquiries/{inquiry.id}/notes", data={"body": "   "}, headers=HX
    )
    assert r.status_code == 422
    assert "Write a note first." in r.text


async def test_archive_and_restore(admin_client, session):
    inquiry = await make_lead(session)
    await admin_client.post(
        f"/admin/inquiries/{inquiry.id}/archive", data={"archived": "true"}, headers=HX
    )
    await session.refresh(inquiry)
    assert inquiry.archived is True
    await admin_client.post(
        f"/admin/inquiries/{inquiry.id}/archive", data={"archived": "false"}, headers=HX
    )
    await session.refresh(inquiry)
    assert inquiry.archived is False
    events = (await session.scalars(select(InquiryEvent).order_by(InquiryEvent.id))).all()
    assert [e.body for e in events] == ["Archived", "Restored to the pipeline"]


async def test_resend_records_outcome(admin_client, session, monkeypatch):
    inquiry = await make_lead(session)

    async def fake_notify(inquiry_id, session_factory=None):
        pass  # leaves notified_at empty = failure

    monkeypatch.setattr(inquiries_admin, "notify_inquiry", fake_notify)
    r = await admin_client.post(f"/admin/inquiries/{inquiry.id}/resend", headers=HX)
    assert (
        json.loads(r.headers["HX-Trigger"])["toast"]
        == "Notification still not sent. Check the SMTP settings."
    )
    event = await session.scalar(select(InquiryEvent))
    assert event.body == "Resend failed"


async def test_plain_post_redirects_back(admin_client, session):
    inquiry = await make_lead(session)
    r = await admin_client.post(f"/admin/inquiries/{inquiry.id}/stage", data={"stage": "quoted"})
    assert r.status_code == 303
    assert r.headers["location"] == f"/admin/inquiries/{inquiry.id}"


async def test_two_admins_both_recorded(admin_client, session):
    from app.auth.users import create_admin

    other = await create_admin(session, "second@dhmgroup.net", "second-password-1")
    inquiry = await make_lead(session)
    session.add(
        InquiryEvent(
            inquiry_id=inquiry.id, author_id=other.id, kind=EventKind.NOTE, body="From second"
        )
    )
    await session.commit()
    r = await admin_client.post(
        f"/admin/inquiries/{inquiry.id}/notes", data={"body": "From first"}, headers=HX
    )
    assert "second@dhmgroup.net" in r.text and "admin@dhmgroup.net" in r.text


async def test_reply_link_encodes_the_address(admin_client, session):
    inquiry = await make_lead(session, email="x?bcc=spy%40evil.test&a=@gmail.com")
    t = (await admin_client.get(f"/admin/inquiries/{inquiry.id}")).text
    assert "mailto:x%3Fbcc%3Dspy%2540evil.test%26a%3D@gmail.com?subject=" in t
