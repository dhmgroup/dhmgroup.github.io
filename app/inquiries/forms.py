"""Quote form parsing and validation.

A plain dataclass rather than a Pydantic model: the error messages are user-facing copy
keyed by field, which is simpler to express directly than to map from Pydantic errors.
"""

import re
from dataclasses import dataclass, field

SERVICES = ("Website", "Mobile app", "Email hosting", "Not sure yet")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
REQUIRED = "This field is required."


def _one_line(value: object) -> str:
    """Collapse all whitespace, including CR/LF, so values are safe in email headers."""
    return " ".join(str(value or "").split())


@dataclass
class QuoteForm:
    name: str = ""
    email: str = ""
    company: str = ""
    services: list[str] = field(default_factory=list)
    message: str = ""
    website: str = ""  # honeypot: humans never see or fill it

    @classmethod
    def from_form(cls, form) -> "QuoteForm":
        return cls(
            name=_one_line(form.get("name")),
            email=_one_line(form.get("email")),
            company=_one_line(form.get("company")),
            services=list(dict.fromkeys(str(s) for s in form.getlist("service"))),
            message=str(form.get("message") or "").strip(),
            website=_one_line(form.get("website")),
        )

    def errors(self) -> dict[str, str]:
        errors: dict[str, str] = {}
        if not self.name:
            errors["name"] = REQUIRED
        elif len(self.name) > 120:
            errors["name"] = "Keep your name under 120 characters."
        if not self.email:
            errors["email"] = REQUIRED
        # ASCII only: the notification's Reply-To header cannot encode an internationalised address.
        elif len(self.email) > 254 or not self.email.isascii() or not EMAIL_RE.match(self.email):
            errors["email"] = "Enter an email like name@company.com."
        if not self.message:
            errors["message"] = REQUIRED
        elif len(self.message) > 5000:
            errors["message"] = "Keep the project details under 5,000 characters."
        if len(self.company) > 160:
            errors["form"] = "Keep the company name under 160 characters."
        elif any(s not in SERVICES for s in self.services):
            errors["form"] = "Choose what you need from the listed services."
        return errors

    @property
    def first_name(self) -> str:
        return self.name.split(" ")[0]
