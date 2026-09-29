import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.inquiries.models import EventKind, Inquiry, InquiryEvent, InquiryStage


def make() -> Inquiry:
    return Inquiry(
        name="Chanda Mulenga",
        email="chanda@company.co.zm",
        services=["Website", "Mobile app"],
        message="A booking site.",
    )


async def test_inquiry_defaults(session):
    inquiry = make()
    session.add(inquiry)
    await session.commit()
    await session.refresh(inquiry)
    assert inquiry.services == ["Website", "Mobile app"]
    assert inquiry.stage is InquiryStage.NEW
    assert inquiry.archived is False
    assert inquiry.read_at is None
    assert inquiry.notified_at is None


async def test_unknown_stage_rejected_by_database(session):
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text(
                    "INSERT INTO inquiries "
                    "(name, email, services, message, stage, archived, created_at) "
                    "VALUES ('a', 'a@b.co', '[]', 'm', 'bogus', false, now())"
                )
            )


async def test_events_cascade_and_order(session, admin):
    inquiry = make()
    session.add(inquiry)
    await session.flush()
    session.add_all(
        [
            InquiryEvent(
                inquiry_id=inquiry.id, author_id=admin.id, kind=EventKind.NOTE, body="first"
            ),
            InquiryEvent(inquiry_id=inquiry.id, kind=EventKind.SYSTEM, body="second"),
        ]
    )
    await session.commit()
    await session.refresh(inquiry, ["events"])
    assert [e.body for e in inquiry.events] == ["second", "first"]
    await session.delete(inquiry)
    await session.commit()
    assert (await session.scalars(select(InquiryEvent))).all() == []
