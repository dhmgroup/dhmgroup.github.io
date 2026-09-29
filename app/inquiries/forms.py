"""Quote form parsing and validation with Pydantic v2.

`QuoteForm` normalises raw form input and never fails, so the page can always re-render what
the visitor typed. `QuoteRules` holds the constraints; `QuoteForm.errors()` runs it and maps
Pydantic's error types to the user-facing messages shown under each field.
"""

from typing import Annotated, Literal, get_args

from pydantic import BaseModel, BeforeValidator, Field, ValidationError

Service = Literal["Website", "Mobile app", "Email hosting", "Not sure yet"]
SERVICES: tuple[str, ...] = get_args(Service)

# Printable ASCII without spaces or a second "@": the notification's Reply-To header cannot
# encode an internationalised address.
EMAIL_PATTERN = r"^[!-?A-~]+@[!-?A-~]+\.[!-?A-~]{2,}$"
REQUIRED = "This field is required."


def _one_line(value: object) -> str:
    """Collapse all whitespace, including CR/LF, so values are safe in email headers."""
    return " ".join(str(value or "").split())


OneLine = Annotated[str, BeforeValidator(_one_line)]


class QuoteRules(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=1, max_length=254, pattern=EMAIL_PATTERN)
    company: str = Field(max_length=160)
    services: list[Service]
    message: str = Field(min_length=1, max_length=5000)


# (field, pydantic error type) -> message; a None type is the field's fallback.
MESSAGES = {
    ("name", "string_too_short"): REQUIRED,
    ("name", None): "Keep your name under 120 characters.",
    ("email", "string_too_short"): REQUIRED,
    ("email", None): "Enter an email like name@company.com.",
    ("message", "string_too_short"): REQUIRED,
    ("message", None): "Keep the project details under 5,000 characters.",
    ("company", None): "Keep the company name under 160 characters.",
    ("services", None): "Choose what you need from the listed services.",
}
FORM_LEVEL = {"company", "services"}  # shown in the form-wide error box, not under a field


class QuoteForm(BaseModel):
    name: OneLine = ""
    email: OneLine = ""
    company: OneLine = ""
    services: list[str] = []
    message: Annotated[str, BeforeValidator(lambda v: str(v or "").strip())] = ""
    website: OneLine = ""  # honeypot: humans never see or fill it

    @classmethod
    def from_form(cls, form) -> "QuoteForm":
        return cls.model_validate(
            {
                "name": form.get("name"),
                "email": form.get("email"),
                "company": form.get("company"),
                "services": list(dict.fromkeys(str(s) for s in form.getlist("service"))),
                "message": form.get("message"),
                "website": form.get("website"),
            }
        )

    def errors(self) -> dict[str, str]:
        try:
            QuoteRules.model_validate(self.model_dump(exclude={"website"}))
        except ValidationError as exc:
            errors: dict[str, str] = {}
            for error in exc.errors():
                field = str(error["loc"][0])
                message = MESSAGES.get((field, error["type"])) or MESSAGES[(field, None)]
                errors.setdefault("form" if field in FORM_LEVEL else field, message)
            return errors
        return {}

    @property
    def first_name(self) -> str:
        return self.name.split(" ")[0]
