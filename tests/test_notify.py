import aiosmtplib
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.inquiries import notify
from app.inquiries.models import Inquiry
from app.inquiries.notify import build_message, notify_inquiry


def make_inquiry(**overrides) -> Inquiry:
    fields = {
        "name": "Chánda Mulenga 🚀",
        "email": "chanda@company.co.zm",
        "company": None,
        "services": ["Website"],
        "message": "A booking site.\nWith payments.",
    }
    return Inquiry(**{**fields, **overrides})


def factory_for(session):
    return async_sessionmaker(
        bind=session.bind, join_transaction_mode="create_savepoint", expire_on_commit=False
    )


def test_build_message_headers_and_body():
    msg = build_message(make_inquiry(), "team@dhmgroup.net")
    assert msg["To"] == "team@dhmgroup.net"
    assert msg["Subject"] == "Quote request from Chánda Mulenga 🚀"
    assert "chanda@company.co.zm" in msg["Reply-To"]
    body = msg.get_content()
    assert "Services: Website" in body
    assert "Company: -" in body
    assert "A booking site.\nWith payments." in body
    msg.as_bytes()  # non-ASCII must encode without error


async def test_success_sets_notified_at(session, monkeypatch):
    sent = []

    async def fake_send(message, **kwargs):
        sent.append((message, kwargs))

    monkeypatch.setattr(notify.aiosmtplib, "send", fake_send)
    inquiry = make_inquiry()
    session.add(inquiry)
    await session.commit()

    await notify_inquiry(inquiry.id, session_factory=factory_for(session))

    await session.refresh(inquiry)
    assert inquiry.notified_at is not None
    assert sent[0][0]["To"] == "contact@dhmgroup.net"  # DEFAULTS.notify_email when unseeded
    assert sent[0][1]["hostname"] == "localhost"


async def test_smtp_failure_keeps_inquiry_unnotified(session, monkeypatch):
    async def failing_send(message, **kwargs):
        raise aiosmtplib.SMTPConnectError("refused")

    monkeypatch.setattr(notify.aiosmtplib, "send", failing_send)
    inquiry = make_inquiry()
    session.add(inquiry)
    await session.commit()

    await notify_inquiry(inquiry.id, session_factory=factory_for(session))  # must not raise

    await session.refresh(inquiry)
    assert inquiry.notified_at is None


async def test_missing_inquiry_is_ignored(session):
    await notify_inquiry(999_999, session_factory=factory_for(session))
