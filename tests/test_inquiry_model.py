import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.inquiries.models import Inquiry, InquiryStatus


async def test_inquiry_round_trip(session):
    inquiry = Inquiry(
        name="Chanda Mulenga",
        email="chanda@company.co.zm",
        services=["Website", "Mobile app"],
        message="A booking site.",
    )
    session.add(inquiry)
    await session.commit()
    await session.refresh(inquiry)
    assert inquiry.services == ["Website", "Mobile app"]
    assert inquiry.status is InquiryStatus.NEW
    assert inquiry.company is None
    assert inquiry.created_at is not None
    assert inquiry.notified_at is None


async def test_unknown_status_rejected_by_database(session):
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text(
                    "INSERT INTO inquiries (name, email, services, message, status, created_at) "
                    "VALUES ('a', 'a@b.co', '[]', 'm', 'bogus', now())"
                )
            )
