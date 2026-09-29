# DHM Web Phase 2: Inquiries — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quote requests submitted on `/` are validated on the server, saved to Postgres, and emailed to the team, with htmx 4 swapping the form in place and a no-JS fallback that works the same way.

**Architecture:** A new `app/inquiries/` package holds the `Inquiry` model, a plain form parser/validator, the email notifier, and the `POST /inquiries` route. The quote form moves from `index.html` into a `_quote_form.html` partial that both the landing page and the route render. htmx 4.0.0 is vendored; `site.js` loses its client-side validation and mailto fallback. The FAQ JSON-LD moves server-side (deferred from Phase 1).

**Tech Stack:** as Phase 1, plus htmx 4.0.0 (vendored), aiosmtplib 5.1, Mailpit (dev SMTP).

**Spec:** `docs/superpowers/specs/2026-09-29-dhm-web-fullstack-design.md` (§4 inquiries, §6 Quote submission, §8 Configuration)

## Global Constraints

- Work on branch `fullstack`. Never push or merge to `main` (live GitHub Pages) before Phase 4.
- Migrations are generated with `uv run alembic revision --autogenerate`, never written or hand-edited. `uv run alembic check` must pass (the test suite enforces it).
- Async only in handlers: asyncpg, aiosmtplib. No `smtplib`, no `requests`.
- htmx is **4.0.0**: every response except 204/304 is swapped (422/429 swap by default); no implicit attribute inheritance; events are colon-separated (`htmx:after:settle`, `htmx:response:error`, `htmx:error`); `hx-disable` disables elements during a request.
- Public markup parity: the quote panel must look identical at rest (screenshot diff at 1440px and 390px against the Phase 1 page).
- Field limits (spec §4): name ≤ 120, email ≤ 254, company ≤ 160, message ≤ 5000; services ⊆ `Website`, `Mobile app`, `Email hosting`, `Not sure yet`.
- Spam guards (spec §6): honeypot field named `website`; 5 submissions per IP per 10 minutes → 429.
- Error copy reuses the Phase 1 strings: `This field is required.` and `Enter an email like name@company.com.`
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. JavaScript disabled or htmx failed to load → the form still posts; success lands on `/?sent=1#quote` with the confirmation, errors re-render the full page with inline messages (tests in Task 6).
2. A name or company containing CR/LF (email header injection) → collapsed to one line before saving and before building the email (tests in Tasks 3 and 4).
3. Double-clicking submit → the button is disabled for the duration of the request (browser check in Task 7).
4. Non-ASCII names and emoji (`Chánda 🚀`) → stored intact and encoded correctly in the email (test in Task 4).
5. Network failure or a 5xx during an htmx submit → the typed form stays in place and an error message appears (browser check in Task 7).

---

## File map

```
pyproject.toml, uv.lock          T1  + aiosmtplib
compose.yaml                     T1  + mailpit service
.env.example, app/config.py      T1  SMTP settings
app/inquiries/__init__.py        T1
app/inquiries/models.py          T1  Inquiry, InquiryStatus
app/models.py                    T1  import inquiries models
migrations/versions/*_inquiries  T1  generated
app/ratelimit.py                 T2  RateLimiter
app/inquiries/forms.py           T3  SERVICES, QuoteForm
app/inquiries/notify.py          T4  build_message, notify_inquiry
app/static/vendor/htmx/htmx.min.js  T5
app/templates/public/_quote_form.html  T5
app/templates/public/index.html  T5 (quote panel, scripts), T7 (FAQ loop, JSON-LD)
app/public/routes.py             T5 (home_context, sent flag), T7 (FAQS, faq_ld)
app/htmx.py                      T6  is_htmx
app/inquiries/routes.py          T6  POST /inquiries
app/main.py                      T6  register router
app/static/js/site.js            T7
README.md, CLAUDE.md             T7
tests/test_inquiry_model.py      T1
tests/test_ratelimit.py          T2
tests/test_quote_form.py         T3
tests/test_notify.py             T4
tests/test_home.py               T5, T7 (additions)
tests/test_inquiries.py          T6
tests/conftest.py                T6  reset limiter
```

---

### Task 1: Inquiry model, SMTP settings, Mailpit

**Files:**
- Create: `app/inquiries/__init__.py`, `app/inquiries/models.py`, `tests/test_inquiry_model.py`, `migrations/versions/<rev>_add_inquiries.py` (generated)
- Modify: `pyproject.toml`/`uv.lock` (via `uv add`), `compose.yaml`, `.env.example`, `app/config.py`, `app/models.py`

**Interfaces:**
- Produces: `app.inquiries.models.InquiryStatus` (`NEW="new"`, `READ="read"`, `ARCHIVED="archived"`); `Inquiry` (`id, name, email, company: str|None, services: list[str], message, status, created_at, notified_at: datetime|None`); settings `smtp_host, smtp_port, smtp_username, smtp_password, smtp_tls, smtp_starttls, smtp_from`.

- [ ] **Step 1: Write the failing test**

`tests/test_inquiry_model.py`:
```python
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
```

Run: `uv run pytest tests/test_inquiry_model.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'app.inquiries'`.

- [ ] **Step 2: Add the dependency, Mailpit and settings**

```bash
uv add "aiosmtplib>=5.1"
```

Append to `compose.yaml` under `services:` (before the top-level `volumes:`):
```yaml
  mail:
    image: axllent/mailpit:latest
    ports:
      - "1025:1025"   # SMTP
      - "8025:8025"   # web UI: http://localhost:8025
```

Append to `.env.example`:
```
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_TLS=false
SMTP_STARTTLS=false
SMTP_FROM=DHM Group <no-reply@dhmgroup.net>
```

Add to `Settings` in `app/config.py` after `base_url`:
```python
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False  # implicit TLS, usually port 465
    smtp_starttls: bool = False  # STARTTLS, usually port 587
    smtp_from: str = "DHM Group <no-reply@dhmgroup.net>"
```

Run: `docker compose up -d --wait`
Expected: `db` healthy, `mail` started; http://localhost:8025 shows the Mailpit inbox.

- [ ] **Step 3: Write the model**

`app/inquiries/__init__.py`: empty file.

`app/inquiries/models.py`:
```python
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class InquiryStatus(StrEnum):
    NEW = "new"
    READ = "read"
    ARCHIVED = "archived"


class Inquiry(Base):
    __tablename__ = "inquiries"
    __table_args__ = (
        CheckConstraint("status IN ('new', 'read', 'archived')", name="status_values"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    company: Mapped[str | None] = mapped_column(String(160))
    services: Mapped[list[str]] = mapped_column(JSONB, default=list)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[InquiryStatus] = mapped_column(
        Enum(
            InquiryStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=InquiryStatus.NEW,
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    notified_at: Mapped[datetime | None]
```

Add to `app/models.py`:
```python
from app.inquiries import models as inquiries  # noqa: F401
```

- [ ] **Step 4: Generate and apply the migration**

```bash
uv run alembic revision --autogenerate -m "add inquiries"
uv run alembic upgrade head
uv run alembic check
```
Expected: the revision creates only `inquiries` (JSONB `services`, `ck_inquiries_status_values`); `No new upgrade operations detected.` If the generated file is wrong, fix the model, delete the file and regenerate.

- [ ] **Step 5: Run the tests and commit**

Run: `uv run pytest -q`
Expected: all pass (including `test_models_match_generated_migrations`).

```bash
uv run ruff check . && uv run ruff format --check .
git add pyproject.toml uv.lock compose.yaml .env.example app migrations tests
git commit -m "feat: add Inquiry model, SMTP settings and Mailpit for dev

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: In-memory rate limiter

**Files:**
- Create: `app/ratelimit.py`, `tests/test_ratelimit.py`

**Interfaces:**
- Produces: `app.ratelimit.RateLimiter(limit: int, window: float, clock: Callable[[], float] = time.monotonic)` with `hit(key: str) -> bool` (True = allowed and recorded) and `clear() -> None`.

- [ ] **Step 1: Write the failing test**

`tests/test_ratelimit.py`:
```python
from app.ratelimit import RateLimiter


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_allows_up_to_limit_then_blocks():
    limiter = RateLimiter(limit=3, window=60, clock=Clock())
    assert [limiter.hit("ip") for _ in range(4)] == [True, True, True, False]


def test_keys_are_independent():
    limiter = RateLimiter(limit=1, window=60, clock=Clock())
    assert limiter.hit("a") is True
    assert limiter.hit("b") is True
    assert limiter.hit("a") is False


def test_window_expires():
    clock = Clock()
    limiter = RateLimiter(limit=1, window=60, clock=clock)
    assert limiter.hit("ip") is True
    clock.now = 59.9
    assert limiter.hit("ip") is False
    clock.now = 60.1
    assert limiter.hit("ip") is True


def test_clear_resets_everything():
    limiter = RateLimiter(limit=1, window=60, clock=Clock())
    limiter.hit("ip")
    limiter.clear()
    assert limiter.hit("ip") is True
```

Run: `uv run pytest tests/test_ratelimit.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'app.ratelimit'`.

- [ ] **Step 2: Implement**

`app/ratelimit.py`:
```python
import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    """Sliding-window counter per key.

    ponytail: in-process memory, correct for a single uvicorn process only;
    move to Redis if the app ever runs more than one replica.
    """

    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window
        self.clock = clock
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> bool:
        now = self.clock()
        hits = self._hits[key]
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def clear(self) -> None:
        self._hits.clear()
```

- [ ] **Step 3: Run tests and commit**

Run: `uv run pytest tests/test_ratelimit.py -q` → 4 passed; then `uv run pytest -q` → all pass.

```bash
uv run ruff check . && uv run ruff format --check .
git add app/ratelimit.py tests/test_ratelimit.py
git commit -m "feat: add in-memory sliding-window rate limiter

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Quote form parsing and validation

**Files:**
- Create: `app/inquiries/forms.py`, `tests/test_quote_form.py`

**Interfaces:**
- Produces: `app.inquiries.forms.SERVICES: tuple[str, ...]`; `QuoteForm` dataclass (`name, email, company, services: list[str], message, website`) with `QuoteForm.from_form(form: Mapping-with-getlist) -> QuoteForm`, `errors() -> dict[str, str]` (keys `name`, `email`, `message`, `form`), property `first_name: str`.

- [ ] **Step 1: Write the failing test**

`tests/test_quote_form.py`:
```python
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
```

Run: `uv run pytest tests/test_quote_form.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'app.inquiries.forms'`.

- [ ] **Step 2: Implement**

`app/inquiries/forms.py`:
```python
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
        elif len(self.email) > 254 or not EMAIL_RE.match(self.email):
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
```

- [ ] **Step 3: Run tests and commit**

Run: `uv run pytest tests/test_quote_form.py -q` → 10 passed; `uv run pytest -q` → all pass.

```bash
uv run ruff check . && uv run ruff format --check .
git add app/inquiries/forms.py tests/test_quote_form.py
git commit -m "feat: parse and validate quote form submissions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Email notification

**Files:**
- Create: `app/inquiries/notify.py`, `tests/test_notify.py`

**Interfaces:**
- Consumes: `Inquiry`, `get_site_settings`, `settings.smtp_*`, `app.db.SessionLocal`, `utcnow`.
- Produces: `build_message(inquiry: Inquiry, to: str) -> email.message.EmailMessage`; `async notify_inquiry(inquiry_id: int, session_factory=SessionLocal) -> None` (never raises on SMTP failure; sets `notified_at` only on success).

- [ ] **Step 1: Write the failing test**

`tests/test_notify.py`:
```python
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
```

Run: `uv run pytest tests/test_notify.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'app.inquiries.notify'`.

- [ ] **Step 2: Implement**

`app/inquiries/notify.py`:
```python
import logging
from email.message import EmailMessage
from email.utils import formataddr

import aiosmtplib

from app.config import settings
from app.db import SessionLocal, utcnow
from app.inquiries.models import Inquiry
from app.site.models import get_site_settings

logger = logging.getLogger("app.inquiries")


def build_message(inquiry: Inquiry, to: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Quote request from {inquiry.name}"
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Reply-To"] = formataddr((inquiry.name, inquiry.email))
    services = ", ".join(inquiry.services) or "Not specified"
    msg.set_content(
        f"Name: {inquiry.name}\n"
        f"Email: {inquiry.email}\n"
        f"Company: {inquiry.company or '-'}\n"
        f"Services: {services}\n\n"
        f"{inquiry.message}\n"
    )
    return msg


async def notify_inquiry(inquiry_id: int, session_factory=SessionLocal) -> None:
    """Email the team about a saved inquiry. Runs as a background task after the commit."""
    async with session_factory() as session:
        inquiry = await session.get(Inquiry, inquiry_id)
        if inquiry is None:
            return
        site = await get_site_settings(session)
        try:
            await aiosmtplib.send(
                build_message(inquiry, site.notify_email),
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username or None,
                password=settings.smtp_password or None,
                use_tls=settings.smtp_tls,
                start_tls=settings.smtp_starttls,
            )
        except (aiosmtplib.SMTPException, OSError):
            logger.exception("Could not send the notification for inquiry %s", inquiry_id)
            return
        inquiry.notified_at = utcnow()
        await session.commit()
```

- [ ] **Step 3: Run tests and commit**

Run: `uv run pytest tests/test_notify.py -q` → 4 passed; `uv run pytest -q` → all pass.

```bash
uv run ruff check . && uv run ruff format --check .
git add app/inquiries/notify.py tests/test_notify.py
git commit -m "feat: email the team when an inquiry is saved

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Quote form partial, htmx vendoring, confirmation state

**Files:**
- Create: `app/templates/public/_quote_form.html`, `app/static/vendor/htmx/htmx.min.js`
- Modify: `app/templates/public/index.html`, `app/public/routes.py`, `tests/test_home.py`

**Interfaces:**
- Consumes: `SERVICES`, `QuoteForm`.
- Produces: `app.public.routes.home_context(session: AsyncSession) -> dict` (keys `site, projects, legal_pages, org_ld, quote_services, form=None, errors={}, done=False`); `GET /?sent=1` renders the confirmation; partial `public/_quote_form.html` expecting `form: QuoteForm | None`, `errors: dict`, `done: bool`, `quote_services`.

- [ ] **Step 1: Capture the parity baseline**

Before touching templates, with the dev DB seeded, run the app (`uv run dhm css && uv run uvicorn app.main:app --port 8000`) and save full-page screenshots at 1440×900 and 390×844 with reduced motion to the session scratchpad as `phase1-desktop.png` / `phase1-mobile.png` (reuse Phase 1's `parity.py` approach: Playwright via `uv run --with playwright --with pillow python`). Stop the server.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_home.py`:
```python
async def test_quote_form_is_htmx_and_has_fallback(client):
    t = (await client.get("/")).text
    assert 'hx-post="/inquiries"' in t
    assert 'method="post"' in t and 'action="/inquiries"' in t
    assert 'hx-target="#quote-panel"' in t
    assert 'name="website"' in t  # honeypot
    assert "/static/vendor/htmx/htmx.min.js" in t
    assert 'id="form-done"' not in t


async def test_sent_flag_shows_confirmation(client):
    t = (await client.get("/?sent=1")).text
    assert 'id="form-done"' in t
    assert "Request received." in t
    assert 'id="quote-form"' not in t
```

Run: `uv run pytest tests/test_home.py -q`
Expected: the two new tests FAIL.

- [ ] **Step 3: Vendor htmx 4.0.0**

```bash
mkdir -p app/static/vendor/htmx
curl -sL https://registry.npmjs.org/htmx.org/-/htmx.org-4.0.0.tgz | tar -xzO package/dist/htmx.min.js > app/static/vendor/htmx/htmx.min.js
head -c 200 app/static/vendor/htmx/htmx.min.js
```
Expected: minified JS (~36 KB).

- [ ] **Step 4: Write the partial**

`app/templates/public/_quote_form.html` (markup and classes from the Phase 1 form; adds `method/action`, htmx attributes, honeypot, `maxlength`, server-rendered values and errors):
```html
{#- Quote panel body. Context: form (QuoteForm or None), errors (dict), done (bool), quote_services. -#}
{% if done %}
            <div id="form-done" class="flex flex-col items-start gap-4" tabindex="-1">
              <span class="grid size-12 place-items-center rounded-full bg-brand text-2xl text-black"><i class="ph ph-check" aria-hidden="true"></i></span>
              <h3 class="text-2xl font-semibold tracking-tight">Request received.</h3>
              <p class="text-muted">{% if form and form.name %}Thanks, {{ form.first_name }}. We will reply to <span class="text-white">{{ form.email }}</span> with next steps.{% else %}Thanks. We will reply with next steps.{% endif %}</p>
            </div>
{% else %}
            <form id="quote-form"
                  method="post"
                  action="/inquiries"
                  novalidate
                  class="flex flex-col gap-4"
                  hx-post="/inquiries"
                  hx-target="#quote-panel"
                  hx-swap="innerHTML"
                  hx-disable="find button"
                  hx-status:5xx="swap:none">
              <div class="hidden" aria-hidden="true">
                <label>Leave this empty <input name="website" tabindex="-1" autocomplete="off"></label>
              </div>
              <div class="grid gap-4 sm:grid-cols-2">
                <label class="flex flex-col gap-2 text-sm font-medium">
                  Your name
                  <input name="name"
                         autocomplete="name"
                         required
                         maxlength="120"
                         value="{{ form.name if form }}"
                         {% if errors.name %}aria-invalid="true"{% endif %}
                         class="field{% if errors.name %} !border-brand{% endif %}"
                         placeholder="Chanda Mulenga">
                  <span class="err{% if not errors.name %} hidden{% endif %} text-sm font-normal text-brand" role="alert">{{ errors.name }}</span>
                </label>
                <label class="flex flex-col gap-2 text-sm font-medium">
                  Work email
                  <input name="email"
                         type="email"
                         autocomplete="email"
                         required
                         maxlength="254"
                         value="{{ form.email if form }}"
                         {% if errors.email %}aria-invalid="true"{% endif %}
                         class="field{% if errors.email %} !border-brand{% endif %}"
                         placeholder="chanda@company.co.zm">
                  <span class="err{% if not errors.email %} hidden{% endif %} text-sm font-normal text-brand" role="alert">{{ errors.email }}</span>
                </label>
              </div>
              <label class="flex flex-col gap-2 text-sm font-medium">
                Company <span class="sr-only">(optional)</span>
                <input name="company"
                       autocomplete="organization"
                       maxlength="160"
                       value="{{ form.company if form }}"
                       class="field"
                       placeholder="Optional">
              </label>
              <fieldset class="flex flex-col gap-2">
                <legend class="mb-2 text-sm font-medium">What do you need?</legend>
                <div class="flex flex-wrap gap-2">
                  {% for service in quote_services %}
                  <label class="cursor-pointer">
                    <input type="checkbox"
                           name="service"
                           value="{{ service }}"
                           {% if form and service in form.services %}checked{% endif %}
                           class="peer sr-only"><span class="block rounded-full border border-line px-3 py-2 text-sm transition-all duration-700 ease-fluid hover:border-white/40 peer-checked:border-brand peer-checked:bg-brand peer-checked:text-black peer-focus-visible:outline-2 peer-focus-visible:outline-brand">{{ service }}</span>
                  </label>
                  {% endfor %}
                </div>
              </fieldset>
              <label class="flex flex-col gap-2 text-sm font-medium">
                Tell us about the project
                <textarea name="message"
                          rows="4"
                          required
                          maxlength="5000"
                          {% if errors.message %}aria-invalid="true"{% endif %}
                          class="field resize-y{% if errors.message %} !border-brand{% endif %}"
                          placeholder="What you want built, who it is for, and any deadline.">{{ form.message if form }}</textarea>
                <span class="err{% if not errors.message %} hidden{% endif %} text-sm font-normal text-brand" role="alert">{{ errors.message }}</span>
              </label>
              <p id="form-error"
                 class="{% if not errors.form %}hidden {% endif %}rounded-xl border border-brand/60 px-3 py-3 text-sm"
                 role="alert">{{ errors.form }}</p>
              <button type="submit"
                      class="btn btn-primary mt-2 self-start text-base disabled:animate-pulse disabled:bg-brand/60">Request a quote <i class="ph ph-arrow-right" aria-hidden="true"></i></button>
            </form>
{% endif %}
```

- [ ] **Step 5: Use the partial in `index.html`**

In `app/templates/public/index.html`:

a. Replace the quote panel's right column — from `<div class="reveal [--d:120ms]">` directly above `<form id="quote-form" ...>` through the closing `</div>` of that column (it ends right after the `<div id="form-done">…</div>` block) — with:
```html
          <div id="quote-panel" class="reveal [--d:120ms]">
{% include "public/_quote_form.html" %}
          </div>
```

b. Before `<script src="/static/js/site.js" defer></script>` add:
```html
    <script src="/static/vendor/htmx/htmx.min.js" defer></script>
```

- [ ] **Step 6: Share the page context and read the `sent` flag**

In `app/public/routes.py`, add the import `from app.inquiries.forms import SERVICES` and replace the `home` route with:
```python
async def home_context(session: AsyncSession) -> dict:
    """Everything the landing page template needs; the inquiries route reuses it."""
    site = await get_site_settings(session)
    projects = (
        await session.scalars(
            select(Project)
            .where(Project.is_published, Project.status != ProjectStatus.RETIRED)
            .order_by(Project.sort_order, Project.id)
        )
    ).all()
    return {
        "site": site,
        "projects": projects,
        "legal_pages": await published_pages(session),
        "org_ld": organization_ld(site),
        "quote_services": SERVICES,
        "form": None,
        "errors": {},
        "done": False,
    }


@router.get("/")
async def home(request: Request, sent: bool = False, session: AsyncSession = Depends(get_session)):
    context = await home_context(session)
    context["done"] = sent
    return templates.TemplateResponse(request, "public/index.html", context)
```

- [ ] **Step 7: Run tests and commit**

Run: `uv run pytest -q`
Expected: all pass.

```bash
uv run ruff check . && uv run ruff format --check .
git add app tests
git commit -m "feat: render the quote form from a partial and vendor htmx 4

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `POST /inquiries`

**Files:**
- Create: `app/htmx.py`, `app/inquiries/routes.py`, `tests/test_inquiries.py`
- Modify: `app/main.py`, `tests/conftest.py`

**Interfaces:**
- Consumes: `QuoteForm`, `Inquiry`, `notify_inquiry`, `RateLimiter`, `home_context`, `templates`.
- Produces: `app.htmx.is_htmx(request: Request) -> bool`; `app.inquiries.routes.router`; `app.inquiries.routes.quote_limiter: RateLimiter` (5 per 600 s).

- [ ] **Step 1: Write the failing tests**

`tests/test_inquiries.py`:
```python
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
```

Add to `tests/conftest.py` (import at the top with the other `app` imports: `from app.inquiries.routes import quote_limiter  # noqa: E402`):
```python
@pytest.fixture(autouse=True)
def _reset_rate_limits():
    quote_limiter.clear()
```

Run: `uv run pytest tests/test_inquiries.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'app.inquiries.routes'` (conftest import).

- [ ] **Step 2: Implement**

`app/htmx.py`:
```python
from fastapi import Request


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"
```

`app/inquiries/routes.py`:
```python
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.htmx import is_htmx
from app.inquiries.forms import SERVICES, QuoteForm
from app.inquiries.models import Inquiry
from app.inquiries.notify import notify_inquiry
from app.public.routes import home_context
from app.ratelimit import RateLimiter
from app.templating import templates

router = APIRouter()
quote_limiter = RateLimiter(limit=5, window=600)
TOO_MANY = "Too many requests from your connection. Please try again in a few minutes."


async def _form_response(request, session, form, errors, status_code):
    if is_htmx(request):
        context = {"form": form, "errors": errors, "done": False, "quote_services": SERVICES}
        return templates.TemplateResponse(
            request, "public/_quote_form.html", context, status_code=status_code
        )
    context = await home_context(session)
    context.update(form=form, errors=errors)
    return templates.TemplateResponse(
        request, "public/index.html", context, status_code=status_code
    )


def _done_response(request, form):
    if is_htmx(request):
        context = {"form": form, "errors": {}, "done": True, "quote_services": SERVICES}
        return templates.TemplateResponse(request, "public/_quote_form.html", context)
    return RedirectResponse("/?sent=1#quote", status_code=303)


@router.post("/inquiries")
async def submit_quote(
    request: Request, background: BackgroundTasks, session: AsyncSession = Depends(get_session)
):
    form = QuoteForm.from_form(await request.form())
    if form.website:  # honeypot filled: pretend it worked, keep nothing
        return _done_response(request, form)

    client_ip = request.client.host if request.client else "unknown"
    if not quote_limiter.hit(client_ip):
        return await _form_response(request, session, form, {"form": TOO_MANY}, 429)

    if errors := form.errors():
        return await _form_response(request, session, form, errors, 422)

    inquiry = Inquiry(
        name=form.name,
        email=form.email,
        company=form.company or None,
        services=form.services,
        message=form.message,
    )
    session.add(inquiry)
    await session.commit()
    background.add_task(notify_inquiry, inquiry.id)
    return _done_response(request, form)
```

In `app/main.py`, import `from app.inquiries.routes import router as inquiries_router` and add `app.include_router(inquiries_router)` after the public router.

- [ ] **Step 3: Run tests and commit**

Run: `uv run pytest -q`
Expected: all pass.

```bash
uv run ruff check . && uv run ruff format --check .
git add app tests
git commit -m "feat: accept quote requests at POST /inquiries

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Client script, server-side FAQ JSON-LD, browser check, docs

**Files:**
- Modify: `app/static/js/site.js`, `app/public/routes.py`, `app/templates/public/index.html`, `tests/test_home.py`, `README.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: `home_context`.
- Produces: `app.public.routes.FAQS: list[tuple[str, str]]`, context keys `faqs`, `faq_ld`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_home.py`:
```python
async def test_faq_is_rendered_with_server_side_schema(client):
    t = (await client.get("/")).text
    assert t.count("<details ") == 7
    assert "FAQPage" in t
    assert "How much does a website or app cost?" in t
```

Run: `uv run pytest tests/test_home.py -q -k faq`
Expected: FAIL (`FAQPage` is built by JavaScript today).

- [ ] **Step 2: Move the FAQ into the route**

In `app/public/routes.py` add, above `organization_ld`:
```python
FAQS = [
    (
        "How much does a website or app cost?",
        "Every project is priced on its scope: the number of pages or screens, the features, "
        "and anything it connects to. Send the quote form and we reply with a written quote "
        "before any work starts.",
    ),
    (
        "How long does a project take?",
        "It depends on scope. A company website moves much faster than an app with accounts "
        "and payments on two platforms. Your quote includes a timeline with clear milestones.",
    ),
    (
        "Do you build for both iOS and Android?",
        "Yes. Our own apps, Pepaala News and Nchito, are live on the App Store and Google Play, "
        "and we take client apps through the same store review process.",
    ),
    (
        "Can I get email on my own domain?",
        "Yes. We set up business email on your domain so your team sends from name@yourcompany "
        "instead of a free address, and we manage the mailboxes for you.",
    ),
    (
        "Do you work with small businesses?",
        "Yes. We work with sole traders, growing companies, startups and larger organisations. "
        "Tell us what you need and we will scope something that fits your budget.",
    ),
    (
        "What happens after launch?",
        "We can host, monitor and update your website or app, the same way we look after our "
        "own products. Ongoing support is agreed as part of your quote.",
    ),
    (
        "What should I prepare before asking for a quote?",
        "A short description of what you want, who it is for, and any deadline. Links to sites "
        "or apps you like help too. You do not need a technical specification.",
    ),
]

FAQ_LD = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
        for q, a in FAQS
    ],
}
```

In `home_context`'s returned dict add `"faqs": FAQS, "faq_ld": FAQ_LD,`.

- [ ] **Step 3: Loop the FAQ in `index.html`**

Replace the seven `<details …>…</details>` blocks inside `<div id="faq-list" …>` with:
```html
            {% for question, answer in faqs %}
            <details class="group rounded-2xl border border-line bg-panel transition-all duration-700 ease-fluid hover:border-white/20">
              <summary class="flex cursor-pointer items-center justify-between gap-4 rounded-2xl px-6 py-4 text-lg font-medium">{{ question }}<i class="faq-icon ph ph-plus shrink-0 text-muted transition-transform duration-700 ease-fluid"
   aria-hidden="true"></i></summary>
              <p class="px-6 pb-6 text-muted">{{ answer }}</p>
            </details>
            {% endfor %}
```

In the `meta` block, after the Organization JSON-LD script, add:
```html
    <script type="application/ld+json">{{ faq_ld | tojson }}</script>
```

- [ ] **Step 4: Rewrite the form part of `site.js`**

In `app/static/js/site.js`:
- Delete the `CONFIG` line near the top (the one reading `dataset.contactEmail`).
- Delete everything from the `// Quote form` comment to the end of the file (this removes client-side validation, the mailto fallback and the JS-built FAQ schema).
- Append:
```js
// Quote form: htmx posts it and swaps the server-rendered form or confirmation into #quote-panel.
const panel = document.getElementById('quote-panel');
const showFormError = msg => {
  const el = panel.querySelector('#form-error');
  if (el) { el.textContent = msg; el.classList.remove('hidden'); }
};
panel.addEventListener('htmx:after:settle', () => {
  (panel.querySelector('#form-done') || panel.querySelector('[aria-invalid="true"]'))?.focus();
});
panel.addEventListener('htmx:response:error', e => {
  if (e.detail.ctx.response.status >= 500) showFormError('We could not send your request. Please try again in a minute.');
});
panel.addEventListener('htmx:error', () => showFormError('We could not send your request. Check your connection and try again.'));
```

Run: `uv run pytest -q` → all pass. Run `uv run dhm css`.

- [ ] **Step 5: Browser check**

Start Mailpit and the app (`docker compose up -d --wait`, `uv run dhm seed`, `uv run uvicorn app.main:app --port 8000`). With Playwright (`uv run --with playwright --with pillow python <scratchpad script>`), verify and print each result:
1. Submit the empty form → the three inline errors appear, focus lands on the name field, no page navigation.
2. Fill valid values and click submit twice quickly → exactly one new row (`SELECT count(*) FROM inquiries` via `docker exec … psql`), the confirmation panel shows "Thanks, <first name>.", and Mailpit's API (`GET http://localhost:8025/api/v1/messages`) has a message with subject `Quote request from <name>`.
3. `page.route("**/inquiries", lambda r: r.abort())` then submit → the typed values stay and `#form-error` reads "Check your connection".
4. `page.route("**/inquiries", lambda r: r.fulfill(status=500, body="x"))` then submit → values stay and `#form-error` reads "Please try again in a minute".
5. With JavaScript disabled (`browser.new_context(java_script_enabled=False)`), submit valid values → lands on `/?sent=1#quote` showing "Request received.".
6. No console errors on `/`.

Then take reduced-motion full-page screenshots at 1440×900 and 390×844 and diff against the Step 1 baseline of Task 5. Expected: same heights, changed pixels under 1%. Stop the server.

- [ ] **Step 6: Docs**

`README.md`: in Quick start change `docker compose up -d --wait db` to `docker compose up -d --wait     # Postgres on :5433, Mailpit on :1025 (UI http://localhost:8025)`; add these rows to the Configuration table and remove the sentence "SMTP (Phase 2) and S3 and session secrets (Phase 3) are documented here as those phases land." replacing it with "S3 and session secrets (Phase 3) are documented here when that phase lands.":

| Variable | Default | Purpose |
|---|---|---|
| `SMTP_HOST` | `localhost` | Mail server for inquiry notifications |
| `SMTP_PORT` | `1025` | 587 for STARTTLS, 465 for implicit TLS |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | empty | Leave empty for servers without auth (Mailpit) |
| `SMTP_TLS` | `false` | `true` for implicit TLS (port 465) |
| `SMTP_STARTTLS` | `false` | `true` for STARTTLS (port 587) |
| `SMTP_FROM` | `DHM Group <no-reply@dhmgroup.net>` | Sender of notification emails |

In the Coolify steps, step 3, add the SMTP variables to the list of env vars to set.

`CLAUDE.md`: change the compose command line to `docker compose up -d --wait            # Postgres on localhost:5433, Mailpit SMTP :1025 / UI :8025`; set Phase 2 to `done` and Phase 3 to `next`; add `inquiries/     Inquiry, quote form validation, email notification, POST /inquiries` to the Layout block after `projects/`, and `htmx.py       is_htmx(request)` and `ratelimit.py  in-memory RateLimiter` after `templating.py`.

- [ ] **Step 7: Final checks and commit**

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run alembic check
docker build -t dhm-web .
git add app tests README.md CLAUDE.md
git commit -m "feat: submit quotes with htmx, render FAQ schema server-side; phase 2 complete

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
