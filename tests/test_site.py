from app.site.models import DEFAULTS, SiteSettings, get_site_settings


def make(**overrides) -> SiteSettings:
    return SiteSettings(id=1, **{**DEFAULTS, **overrides})


def test_tel_href_keeps_digits_only():
    assert make(phone="+260 (770) 005-939").tel_href == "tel:+260770005939"


def test_address_lines_and_one_line():
    s = make(address="Plot 4280 Chikola Loop Area\n\n  Chingola, Zambia  ")
    assert s.address_lines == ["Plot 4280 Chikola Loop Area", "Chingola, Zambia"]
    assert s.address_one_line == "Plot 4280 Chikola Loop Area, Chingola, Zambia"


def test_empty_socials_are_hidden():
    s = make(instagram_url="", x_url=None)
    labels = [label for label, _, _ in s.socials]
    assert labels == ["LinkedIn", "Facebook", "TikTok", "YouTube"]


async def test_get_site_settings_falls_back_to_defaults(session):
    s = await get_site_settings(session)
    assert s.contact_email == "contact@dhmgroup.net"
    assert s.phone == "+260 770 005 939"
