import pytest
from sqlalchemy import func, select

from app.inquiries import routes
from app.inquiries.models import Inquiry

HX = {"HX-Request": "true"}
VALID = {
    "name": "Chanda Mulenga",
    "email": "chanda@company.co.zm",
    "company": "Acme",
    "service": ["Website", "Mobile app"],
    "message": "A booking site.",
}


@pytest.fixture
def notified(monkeypatch):
    calls = []

    async def record(inquiry_id):
        calls.append(inquiry_id)

    monkeypatch.setattr(routes, "notify_inquiry", record)
    return calls


async def count(session) -> int:
    return await session.scalar(select(func.count()).select_from(Inquiry))


async def test_htmx_submit_saves_and_confirms(client, session, notified):
    r = await client.post("/inquiries", data=VALID, headers=HX)
    assert r.status_code == 200
    assert 'id="form-done"' in r.text
    assert "Thanks, Chanda." in r.text
    assert "<html" not in r.text  # partial only
    inquiry = await session.scalar(select(Inquiry))
    assert inquiry.services == ["Website", "Mobile app"]
    assert inquiry.company == "Acme"
    assert notified == [inquiry.id]


async def test_plain_submit_redirects_to_confirmation(client, session, notified):
    r = await client.post("/inquiries", data=VALID)
    assert r.status_code == 303
    assert r.headers["location"] == "/?sent=1#quote"
    assert await count(session) == 1


async def test_htmx_invalid_returns_form_with_errors(client, session, notified):
    r = await client.post(
        "/inquiries", data={"name": "", "email": "nope", "message": "Hi <b>there</b>"}, headers=HX
    )
    assert r.status_code == 422
    assert "This field is required." in r.text
    assert "Enter an email like name@company.com." in r.text
    assert 'value="nope"' in r.text
    assert "Hi &lt;b&gt;there&lt;/b&gt;</textarea>" in r.text
    assert 'aria-invalid="true"' in r.text
    assert await count(session) == 0
    assert notified == []


async def test_plain_invalid_renders_full_page(client, session, notified):
    r = await client.post("/inquiries", data={**VALID, "email": ""})
    assert r.status_code == 422
    assert "<html" in r.text
    assert "This field is required." in r.text
    assert 'value="Chanda Mulenga"' in r.text
    assert await count(session) == 0


async def test_empty_company_stored_as_null(client, session, notified):
    await client.post("/inquiries", data={**VALID, "company": "  "}, headers=HX)
    assert (await session.scalar(select(Inquiry))).company is None


async def test_honeypot_fakes_success_and_saves_nothing(client, session, notified):
    r = await client.post("/inquiries", data={**VALID, "website": "http://spam.test"}, headers=HX)
    assert r.status_code == 200
    assert 'id="form-done"' in r.text
    assert await count(session) == 0
    assert notified == []


async def test_rate_limit(client, session, notified):
    for _ in range(5):
        assert (await client.post("/inquiries", data=VALID, headers=HX)).status_code == 200
    r = await client.post("/inquiries", data=VALID, headers=HX)
    assert r.status_code == 429
    assert "Too many requests" in r.text
    assert await count(session) == 5


async def test_header_injection_is_stored_on_one_line(client, session, notified):
    await client.post("/inquiries", data={**VALID, "name": "Eve\r\nBcc: x@y.co"}, headers=HX)
    assert (await session.scalar(select(Inquiry))).name == "Eve Bcc: x@y.co"


async def test_invalid_attempts_do_not_use_up_the_rate_limit(client, session, notified):
    for _ in range(5):
        r = await client.post("/inquiries", data={**VALID, "email": "typo"}, headers=HX)
        assert r.status_code == 422
    assert (await client.post("/inquiries", data=VALID, headers=HX)).status_code == 200
    assert await count(session) == 1
