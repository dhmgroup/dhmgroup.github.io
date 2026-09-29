from starlette.datastructures import FormData

from app.inquiries.forms import SERVICES, QuoteForm


def parse(**fields) -> QuoteForm:
    items = []
    for key, value in fields.items():
        for v in value if isinstance(value, list) else [value]:
            items.append((key, v))
    return QuoteForm.from_form(FormData(items))


VALID = {"name": "Chanda Mulenga", "email": "chanda@company.co.zm", "message": "A booking site."}


def test_valid_form_has_no_errors():
    form = parse(**VALID, company="Acme", service=["Website", "Mobile app"])
    assert form.errors() == {}
    assert form.services == ["Website", "Mobile app"]
    assert form.first_name == "Chanda"


def test_required_fields():
    assert parse().errors() == {
        "name": "This field is required.",
        "email": "This field is required.",
        "message": "This field is required.",
    }


def test_bad_email():
    assert parse(**{**VALID, "email": "chanda@company"}).errors() == {
        "email": "Enter an email like name@company.com."
    }


def test_unknown_service_rejected():
    assert "form" in parse(**VALID, service="Crypto").errors()


def test_duplicate_services_collapse():
    assert parse(**VALID, service=["Website", "Website"]).services == ["Website"]


def test_length_limits():
    assert parse(**{**VALID, "name": "x" * 120}).errors() == {}
    assert "name" in parse(**{**VALID, "name": "x" * 121}).errors()
    assert "message" in parse(**{**VALID, "message": "x" * 5001}).errors()
    assert "form" in parse(**VALID, company="x" * 161).errors()


def test_header_injection_is_collapsed_to_one_line():
    form = parse(**{**VALID, "name": "Eve\r\nBcc: victim@example.com", "company": "A\nB"})
    assert form.name == "Eve Bcc: victim@example.com"
    assert form.company == "A B"


def test_message_keeps_line_breaks():
    assert parse(**{**VALID, "message": " line one\nline two "}).message == "line one\nline two"


def test_honeypot_is_captured():
    assert parse(**VALID, website="http://spam.test").website == "http://spam.test"


def test_services_constant_matches_form_chips():
    assert SERVICES == ("Website", "Mobile app", "Email hosting", "Not sure yet")
