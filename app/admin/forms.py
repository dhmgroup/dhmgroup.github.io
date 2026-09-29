"""Shared Pydantic types and helpers for admin forms."""

import json
import re
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import AfterValidator, BeforeValidator, ValidationError

from app.inquiries.forms import EMAIL_PATTERN


def _strip(value: object) -> str:
    return str(value or "").strip()


def _https(value: object) -> str | None:
    text = _strip(value)
    if not text:
        return None
    parts = urlsplit(text)
    if parts.scheme != "https" or not parts.netloc or any(c.isspace() for c in text):
        raise ValueError("Use a full https:// link.")
    return text


def _phone(value: str) -> str:
    digits = sum(c.isdigit() for c in value)
    if not re.fullmatch(r"\+[0-9 ()\-]+", value) or not 9 <= digits <= 15:
        raise ValueError("Use the international format, for example +260 770 005 939.")
    return value


def _email(value: str) -> str:
    if len(value) > 254 or not re.fullmatch(EMAIL_PATTERN, value):
        raise ValueError("Enter an email like name@company.com.")
    return value.lower()


Stripped = Annotated[str, BeforeValidator(_strip)]
OptionalHttps = Annotated[str | None, BeforeValidator(_https)]
Phone = Annotated[str, BeforeValidator(_strip), AfterValidator(_phone)]
Email = Annotated[str, BeforeValidator(_strip), AfterValidator(_email)]


def field_errors(exc: ValidationError, messages: dict[str, str]) -> dict[str, str]:
    """First error per field, using the form's own copy where it has some."""
    errors: dict[str, str] = {}
    for error in exc.errors():
        field = str(error["loc"][0]) if error["loc"] else "form"
        fallback = str(error["msg"]).removeprefix("Value error, ")
        errors.setdefault(field, messages.get(field, fallback))
    return errors


def hx_toast(response, message: str, **events):
    response.headers["HX-Trigger"] = json.dumps({**events, "toast": message})
    return response
