import pytest
from pydantic import BaseModel, ValidationError

from app.admin.forms import Email, OptionalHttps, Phone, field_errors


class Probe(BaseModel):
    link: OptionalHttps = None
    phone: Phone = "+260 770 005 939"
    email: Email = "a@b.co"


@pytest.mark.parametrize("value", ["", "   ", None])
def test_empty_links_become_none(value):
    assert Probe(link=value).link is None


def test_https_link_kept():
    assert Probe(link=" https://www.linkedin.com/company/dhmgroup ").link == (
        "https://www.linkedin.com/company/dhmgroup"
    )


@pytest.mark.parametrize(
    "value",
    ["http://dhmgroup.net", "javascript:alert(1)", "https://", "https://a b.co", "dhmgroup.net"],
)
def test_bad_links_rejected(value):
    with pytest.raises(ValidationError):
        Probe(link=value)


@pytest.mark.parametrize("value", ["+260 770 005 939", "+260-770-005-939", "+44 (20) 7946 0958"])
def test_international_phones(value):
    assert Probe(phone=value).phone == value


@pytest.mark.parametrize("value", ["0770 005 939", "+12", "+260 770 005 939 ext 12", ""])
def test_bad_phones(value):
    with pytest.raises(ValidationError):
        Probe(phone=value)


def test_email_is_lowercased():
    assert Probe(email=" Leads@DHMGroup.net ").email == "leads@dhmgroup.net"


def test_field_errors_uses_custom_messages():
    with pytest.raises(ValidationError) as info:
        Probe(link="http://x.co", email="nope")
    errors = field_errors(info.value, {"link": "Use a full https:// link, please."})
    assert errors["link"] == "Use a full https:// link, please."
    assert errors["email"] == "Enter an email like name@company.com."
