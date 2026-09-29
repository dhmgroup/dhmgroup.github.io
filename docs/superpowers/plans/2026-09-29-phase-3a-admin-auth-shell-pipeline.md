# DHM Web Phase 3a: Admin Auth, Shell and Inquiry Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admins sign in at `/admin`, see an overview of leads that need them, and run each inquiry through the pipeline (New → Contacted → Quoted → Won/Lost, or Archived) with an activity timeline, in the Ledger shell that works on a phone and a laptop.

**Architecture:** `app/auth/` owns the `User` model, argon2 hashing, the session, CSRF and the login routes. `app/admin/` owns the shell (layout, macros, overview, shared context). The pipeline lives with inquiries: `Inquiry` gains `stage`, `archived`, `read_at`, and a new `InquiryEvent` table records notes and changes; `app/inquiries/admin.py` serves the list and record. htmx 4 swaps the list and the record panel; a `HX-Trigger` JSON header refreshes the list and raises toasts.

**Tech Stack:** as Phase 2, plus argon2-cffi 25.1, itsdangerous 2.2 (Starlette `SessionMiddleware`), tzdata (Africa/Lusaka display times on Windows and slim images).

**Spec:** `docs/superpowers/specs/2026-09-29-dhm-web-fullstack-design.md` (§4 users, inquiries, inquiry_events; §5 admin routes and "Admin design"; §6 Admin authentication)
**Design brief (binding for all admin UI):** `.impeccable/surfaces/app-templates-admin-layout-html.md` (The Ledger)

## Global Constraints

- Branch `fullstack`; never push or merge to `main` before Phase 4.
- Migrations are generated with `uv run alembic revision --autogenerate`, never written or hand-edited; `uv run alembic check` must pass (the suite enforces it). New NOT NULL columns on existing tables get a `server_default` in the model so autogenerate emits it.
- If a `dhm dev` process is running, use `uv add --no-sync`, `uv pip install <pkg>==<locked>` and `uv run --no-sync` (it locks `dhm.exe` on Windows).
- Async in handlers: argon2 hashing/verification runs in `starlette.concurrency.run_in_threadpool`.
- Admin forms are validated with Pydantic v2 models.
- Every non-GET `/admin/*` request except `POST /admin/login` is CSRF-checked (header `X-CSRF-Token` or form field `csrf_token`).
- Session cookie: name `dhm_admin`, signed with `SECRET_KEY`, `HttpOnly`, `SameSite=Lax`, `Secure` when `ENV=production`, max age 8 hours. Startup fails in production if `SECRET_KEY` is left at the development default.
- Login rate limit: 5 attempts per 15 minutes per IP + email, via the existing `RateLimiter`.
- htmx 4: `hx-headers:inherited` carries the CSRF header; `HX-Trigger` JSON events are dispatched on the source element or, if it was swapped out, on `document`, so listeners and `from:` triggers use `document`.
- **Design (The Ledger):** DESIGN.md tokens only; no reveals, gradients or display type (largest heading is 24px); transitions 150–250 ms (`duration-200`); orange (`brand`) only for the primary action, selected tab/nav/stage, the unread dot and badge, focus, errors. Stages are neutral chips with text and icon. Nav: labelled rail ≥1024px (`lg`), icon rail 640–1023px (`sm`), bottom tab bar <640px. Record panel right of the list at `lg`, full-screen overlay below `lg`.
- Before editing any admin template, read `C:/Users/50018101/.claude/plugins/cache/impeccable/impeccable/4.3.1/skills/impeccable/reference/craft-floor.md`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. A phone at 390px can do the core flow: sign in, open the inbox, open a lead, Reply by email, move it to Contacted with a note, then get back to the list (browser check in Task 7).
2. An expired or missing session during an htmx request → the browser lands on the sign-in page (via `HX-Redirect`), not a sign-in form swapped into the record panel (test in Task 2).
3. `next=` pointing off-site (`//evil.test`, `https://evil.test`, `/\evil.test`) → ignored, redirect to `/admin` (test in Task 2).
4. Search text containing `%` or `_` → matched literally, not as wildcards (test in Task 5).
5. Two admins changing the same lead: each stage change and note is its own timeline row with its author, so neither silently overwrites the other's history (test in Task 6).

---

## File map

```
pyproject.toml, uv.lock               T1  + argon2-cffi, itsdangerous, tzdata
.env.example, app/config.py           T1  SECRET_KEY, TIMEZONE, production guard
app/auth/__init__.py                  T1
app/auth/models.py                    T1  User
app/auth/users.py                     T1  hash_password, verify_password, create_admin, set_password
app/cli.py                            T1  dhm create-admin | set-password
app/models.py                         T1, T3
migrations/versions/*                 T1 (users), T3 (pipeline) — generated
app/auth/deps.py                      T2  NotAuthenticated, require_admin, verify_csrf, safe_next
app/auth/routes.py                    T2  GET/POST /admin/login, POST /admin/logout
app/templates/admin/login.html        T2
app/main.py                           T2 (middleware, handler, router), T4, T5 (routers)
app/inquiries/models.py               T3  InquiryStage, STAGES, InquiryEvent, EventKind
app/templating.py                     T4  local_time filter
app/admin/__init__.py                 T4
app/admin/context.py                  T4  admin_context
app/admin/routes.py                   T4  GET /admin overview
app/templates/admin/layout.html       T4
app/templates/admin/_macros.html      T4
app/templates/admin/overview.html     T4
app/static/js/admin.js                T4  toasts, focus after swap
app/inquiries/admin.py                T5 (list), T6 (record + actions)
app/templates/admin/inquiries.html    T5
app/templates/admin/_inquiry_list.html   T5
app/templates/admin/_inquiry_panel.html  T6
tests/conftest.py                     T2  admin, admin_client fixtures
tests/test_auth.py                    T1, T2
tests/test_inquiry_model.py           T3
tests/test_admin_shell.py             T4
tests/test_admin_inquiries.py         T5, T6
README.md, CLAUDE.md                  T7
```

---

### Task 1: Users, password hashing, CLI, secret key

**Files:**
- Create: `app/auth/__init__.py`, `app/auth/models.py`, `app/auth/users.py`, `tests/test_auth.py`, `migrations/versions/<rev>_add_users.py` (generated)
- Modify: `pyproject.toml`/`uv.lock`, `.env.example`, `app/config.py`, `app/models.py`, `app/cli.py`

**Interfaces:**
- Produces: `settings.secret_key: str`, `settings.timezone: str`, `DEV_SECRET_KEY`; `app.auth.models.User` (`id, email, password_hash, is_active, created_at, last_login_at`); `app.auth.users`: `hash_password(pw) -> str`, `verify_password(hash, pw) -> bool`, `async create_admin(session, email, password) -> User`, `async set_password(session, email, password) -> bool`; `dhm create-admin EMAIL`, `dhm set-password EMAIL`.

- [ ] **Step 1: Write the failing tests**

`tests/test_auth.py`:
```python
import pytest
from pydantic import ValidationError

from app.auth.users import create_admin, hash_password, set_password, verify_password
from app.config import DEV_SECRET_KEY, Settings


def test_hash_and_verify():
    h = hash_password("correct horse")
    assert h.startswith("$argon2")
    assert verify_password(h, "correct horse") is True
    assert verify_password(h, "wrong") is False


async def test_create_admin_lowercases_email(session):
    user = await create_admin(session, "  Douglas@DHMGroup.net ", "pw-123456")
    assert user.email == "douglas@dhmgroup.net"
    assert user.is_active is True
    assert verify_password(user.password_hash, "pw-123456")


async def test_create_admin_rejects_duplicate(session):
    await create_admin(session, "a@dhmgroup.net", "pw-123456")
    with pytest.raises(ValueError, match="already exists"):
        await create_admin(session, "A@dhmgroup.net", "pw-654321")


async def test_create_admin_rejects_short_password(session):
    with pytest.raises(ValueError, match="at least 10"):
        await create_admin(session, "b@dhmgroup.net", "short")


async def test_set_password(session):
    user = await create_admin(session, "c@dhmgroup.net", "pw-123456")
    assert await set_password(session, "C@dhmgroup.net", "new-password-1") is True
    await session.refresh(user)
    assert verify_password(user.password_hash, "new-password-1")
    assert await set_password(session, "nobody@dhmgroup.net", "new-password-1") is False


def test_production_requires_a_real_secret_key():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(env="production", secret_key=DEV_SECRET_KEY)
    assert Settings(env="production", secret_key="x" * 40).env == "production"
```

Run: `uv run --no-sync pytest tests/test_auth.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'app.auth'`.

- [ ] **Step 2: Dependencies and settings**

```bash
uv add --no-sync "argon2-cffi>=25.1" "itsdangerous>=2.2" "tzdata>=2025.2"
# then, for each: uv pip install "<name>==<version from uv.lock>"   (or plain `uv sync` if no dev server runs)
```

Append to `.env.example`:
```
SECRET_KEY=change-me-to-64-random-characters
TIMEZONE=Africa/Lusaka
```

In `app/config.py`: add `from pydantic import model_validator` and, above the class, `DEV_SECRET_KEY = "dev-insecure-secret-key-change-me"`. Add fields after `base_url`:
```python
    secret_key: str = DEV_SECRET_KEY
    timezone: str = "Africa/Lusaka"
```
and at the end of the class:
```python
    @model_validator(mode="after")
    def _real_secret_in_production(self):
        if self.env == "production" and self.secret_key == DEV_SECRET_KEY:
            raise ValueError("SECRET_KEY must be set in production")
        return self
```

- [ ] **Step 3: Model and user functions**

`app/auth/__init__.py`: empty.

`app/auth/models.py`:
```python
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_login_at: Mapped[datetime | None]
```

`app/auth/users.py`:
```python
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User

_hasher = PasswordHasher()
MIN_PASSWORD = 10


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _clean(email: str) -> str:
    return email.strip().lower()


def _check(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"Password must be at least {MIN_PASSWORD} characters.")


async def create_admin(session: AsyncSession, email: str, password: str) -> User:
    email = _clean(email)
    _check(password)
    if await session.scalar(select(User).where(User.email == email)):
        raise ValueError(f"An admin with {email} already exists.")
    user = User(email=email, password_hash=hash_password(password))
    session.add(user)
    await session.commit()
    return user


async def set_password(session: AsyncSession, email: str, password: str) -> bool:
    _check(password)
    user = await session.scalar(select(User).where(User.email == _clean(email)))
    if user is None:
        return False
    user.password_hash = hash_password(password)
    await session.commit()
    return True
```

Add to `app/models.py`: `from app.auth import models as auth  # noqa: F401` (first import, alphabetical).

- [ ] **Step 4: CLI commands**

In `app/cli.py`, add `import getpass` and:
```python
def _prompt_password() -> str:
    first = getpass.getpass("Password (10+ characters): ")
    if first != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match.")
    return first


async def _with_session(fn, *args):
    from app.db import SessionLocal, engine

    try:
        async with SessionLocal() as session:
            return await fn(session, *args)
    finally:
        await engine.dispose()
```
Register subparsers after `seed`:
```python
    for name, help_text in (("create-admin", "add an admin user"), ("set-password", "reset an admin's password")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("email")
```
Dispatch:
```python
    elif args.command in ("create-admin", "set-password"):
        from app.auth.users import create_admin, set_password

        password = _prompt_password()
        try:
            if args.command == "create-admin":
                asyncio.run(_with_session(create_admin, args.email, password))
                print(f"Created admin {args.email.strip().lower()}.")
            elif asyncio.run(_with_session(set_password, args.email, password)):
                print("Password updated.")
            else:
                sys.exit(f"No admin with email {args.email}.")
        except ValueError as exc:
            sys.exit(str(exc))
```
Update the module docstring to list `{css,dev,seed,create-admin,set-password}`.

- [ ] **Step 5: Generate the migration**

```bash
uv run --no-sync alembic revision --autogenerate -m "add users"
uv run --no-sync alembic upgrade head
uv run --no-sync alembic check
```
Expected: creates only `users` with `uq_users_email`.

- [ ] **Step 6: Run tests and commit**

Run: `uv run --no-sync pytest -q` → all pass.
```bash
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
git add pyproject.toml uv.lock .env.example app migrations tests
git commit -m "feat: add admin users with argon2 passwords and CLI commands

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Session, sign-in, CSRF, admin guard

**Files:**
- Create: `app/auth/deps.py`, `app/auth/routes.py`, `app/templates/admin/login.html`
- Modify: `app/main.py`, `tests/conftest.py`, `tests/test_auth.py`

**Interfaces:**
- Consumes: `User`, `verify_password`, `RateLimiter`, `settings.secret_key`.
- Produces: `app.auth.deps`: `class NotAuthenticated(Exception)`, `async require_admin(request, session) -> User`, `async verify_csrf(request) -> None`, `safe_next(value: str | None) -> str`; session keys `uid: int`, `csrf: str`; `app.auth.routes.router`, `login_limiter`; test fixtures `admin` (User, password `admin-password-1`) and `admin_client` (logged-in `AsyncClient` with `X-CSRF-Token` set).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_auth.py`:
```python
from app.auth.deps import safe_next


@pytest.mark.parametrize(
    "value",
    [None, "", "https://evil.test", "//evil.test", "/\\evil.test", "admin", "/public"],
)
def test_safe_next_rejects_everything_but_admin_paths(value):
    assert safe_next(value) == "/admin"


def test_safe_next_keeps_admin_paths():
    assert safe_next("/admin/inquiries?stage=won") == "/admin/inquiries?stage=won"


async def test_login_page_renders(client):
    r = await client.get("/admin/login")
    assert r.status_code == 200
    assert 'name="password"' in r.text


async def test_login_success_redirects_to_next(client, admin):
    r = await client.post(
        "/admin/login",
        data={"email": "ADMIN@dhmgroup.net", "password": "admin-password-1", "next": "/admin/inquiries"},
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/inquiries"
    assert "dhm_admin=" in r.headers["set-cookie"]


async def test_login_failure_is_generic(client, admin):
    for email, pw in [("admin@dhmgroup.net", "wrong-password"), ("nobody@dhmgroup.net", "x")]:
        r = await client.post("/admin/login", data={"email": email, "password": pw})
        assert r.status_code == 401
        assert "Email or password is incorrect." in r.text


async def test_login_rate_limited(client, admin):
    for _ in range(5):
        await client.post("/admin/login", data={"email": "admin@dhmgroup.net", "password": "nope-nope"})
    r = await client.post(
        "/admin/login", data={"email": "admin@dhmgroup.net", "password": "admin-password-1"}
    )
    assert r.status_code == 429


async def test_inactive_user_cannot_log_in(client, admin, session):
    admin.is_active = False
    await session.commit()
    r = await client.post(
        "/admin/login", data={"email": "admin@dhmgroup.net", "password": "admin-password-1"}
    )
    assert r.status_code == 401


async def test_admin_requires_login(client):
    r = await client.get("/admin")
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login?next=/admin"


async def test_htmx_request_without_session_gets_hx_redirect(client):
    r = await client.get("/admin/inquiries?stage=new", headers={"HX-Request": "true"})
    assert r.status_code == 204
    assert r.headers["HX-Redirect"].startswith("/admin/login?next=")


async def test_csrf_required_on_admin_posts(admin_client):
    ok = await admin_client.post("/admin/logout")
    assert ok.status_code == 303
    admin_client.headers.pop("X-CSRF-Token")
    r = await admin_client.post("/admin/logout")
    assert r.status_code == 403


async def test_logout_clears_session(admin_client):
    await admin_client.post("/admin/logout")
    assert (await admin_client.get("/admin")).status_code == 303
```

Add fixtures to `tests/conftest.py` (with `import re` at the top and `from app.auth.routes import login_limiter  # noqa: E402`, `from app.auth.users import create_admin  # noqa: E402` among the app imports; extend `_reset_rate_limits` to also call `login_limiter.clear()`):
```python
@pytest.fixture
async def admin(session):
    return await create_admin(session, "admin@dhmgroup.net", "admin-password-1")


@pytest.fixture
async def admin_client(client, admin):
    r = await client.post(
        "/admin/login", data={"email": "admin@dhmgroup.net", "password": "admin-password-1"}
    )
    assert r.status_code == 303, r.text
    page = await client.get("/admin/login")  # any page that renders the token meta tag
    token = re.search(r'name="csrf-token" content="([^"]+)"', page.text).group(1)
    client.headers["X-CSRF-Token"] = token
    return client
```

Run: `uv run --no-sync pytest tests/test_auth.py -q`
Expected: new tests FAIL (`/admin/login` is 404; `app.auth.deps` missing → collection error first).

- [ ] **Step 2: Guard, CSRF and safe redirects**

`app/auth/deps.py`:
```python
import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db import get_session


class NotAuthenticated(Exception):
    """Raised by require_admin; app.main turns it into a redirect to the sign-in page."""


def safe_next(value: str | None) -> str:
    """Only same-site admin paths; anything else falls back to the overview."""
    if value and value.startswith("/admin") and "\\" not in value and not value.startswith("//"):
        return value
    return "/admin"


async def require_admin(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    uid = request.session.get("uid")
    user = await session.get(User, uid) if isinstance(uid, int) else None
    if user is None or not user.is_active:
        raise NotAuthenticated
    return user


async def verify_csrf(request: Request) -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    expected = request.session.get("csrf")
    sent = request.headers.get("X-CSRF-Token")
    if sent is None and request.headers.get("content-type", "").startswith(
        ("application/x-www-form-urlencoded", "multipart/form-data")
    ):
        sent = (await request.form()).get("csrf_token")
    if not expected or not secrets.compare_digest(str(sent or ""), expected):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
```
(`request.form()` is cached by Starlette, so handlers can read the form again.)

- [ ] **Step 3: Sign-in routes**

`app/auth/routes.py`:
```python
import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.deps import safe_next, verify_csrf
from app.auth.models import User
from app.auth.users import hash_password, verify_password
from app.db import get_session, utcnow
from app.ratelimit import RateLimiter
from app.templating import templates

router = APIRouter(prefix="/admin")
login_limiter = RateLimiter(limit=5, window=900)
_DUMMY_HASH = hash_password("timing-equaliser-not-a-password")


def _render(request, *, email="", next_path="/admin", error="", status_code=200):
    request.session.setdefault("csrf", secrets.token_urlsafe(32))
    context = {"email": email, "next": next_path, "error": error, "csrf_token": request.session["csrf"]}
    return templates.TemplateResponse(request, "admin/login.html", context, status_code=status_code)


@router.get("/login")
async def login_page(request: Request, next: str | None = None):
    return _render(request, next_path=safe_next(next))


@router.post("/login")
async def login(request: Request, session: AsyncSession = Depends(get_session)):
    form = await request.form()
    email = str(form.get("email") or "").strip().lower()
    password = str(form.get("password") or "")
    next_path = safe_next(str(form.get("next") or ""))
    ip = request.client.host if request.client else "unknown"

    if not login_limiter.hit(f"{ip}|{email}"):
        return _render(
            request, email=email, next_path=next_path, status_code=429,
            error="Too many attempts. Wait 15 minutes and try again.",
        )

    user = await session.scalar(select(User).where(User.email == email))
    ok = await run_in_threadpool(
        verify_password, user.password_hash if user else _DUMMY_HASH, password
    )
    if not (user and ok and user.is_active):
        return _render(
            request, email=email, next_path=next_path, status_code=401,
            error="Email or password is incorrect.",
        )

    user.last_login_at = utcnow()
    await session.commit()
    request.session.clear()
    request.session.update(uid=user.id, csrf=secrets.token_urlsafe(32))
    return RedirectResponse(next_path, status_code=303)


@router.post("/logout", dependencies=[Depends(verify_csrf)])
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)
```

- [ ] **Step 4: Sign-in template**

Read `craft-floor.md` (path in Global Constraints) before writing templates.

`app/templates/admin/login.html`:
```html
{% extends "base.html" %}
{% block title %}Sign in | DHM admin{% endblock %}
{% block meta %}<meta name="robots" content="noindex"><meta name="csrf-token" content="{{ csrf_token }}">{% endblock %}
{% block body_class %}grid min-h-dvh place-items-center px-4{% endblock %}
{% block body %}
  <main class="flex w-full max-w-sm flex-col gap-8">
    <img src="/static/img/logo-light.png" alt="DHM Group" width="640" height="314" class="h-8 w-auto self-start">
    <div class="flex flex-col gap-2">
      <h1 class="text-2xl font-semibold tracking-tight">Sign in</h1>
      <p class="text-sm text-muted">Admin access for the DHM Group team.</p>
    </div>
    <form method="post" action="/admin/login" class="flex flex-col gap-4">
      <input type="hidden" name="next" value="{{ next }}">
      <label class="flex flex-col gap-2 text-sm font-medium">
        Email
        <input name="email" type="email" autocomplete="username" required value="{{ email }}" class="field" autofocus>
      </label>
      <label class="flex flex-col gap-2 text-sm font-medium">
        Password
        <input name="password" type="password" autocomplete="current-password" required class="field">
      </label>
      {% if error %}
      <p class="rounded-xl border border-brand/60 px-3 py-3 text-sm" role="alert">{{ error }}</p>
      {% endif %}
      <button type="submit" class="btn btn-primary mt-2 self-start">Sign in <i class="ph ph-arrow-right" aria-hidden="true"></i></button>
    </form>
  </main>
{% endblock %}
```

- [ ] **Step 5: Wire into `app/main.py`**

Imports: `from fastapi.responses import RedirectResponse, Response`, `from starlette.middleware.sessions import SessionMiddleware`, `from app.auth.deps import NotAuthenticated`, `from app.auth.routes import router as auth_router`, `from app.config import settings`, `from app.htmx import is_htmx`, `from urllib.parse import quote`.

After `app = FastAPI(...)`:
```python
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="dhm_admin",
    max_age=8 * 60 * 60,
    same_site="lax",
    https_only=settings.env == "production",
)
```
Register `app.include_router(auth_router)` with the other routers, and add the handler:
```python
@app.exception_handler(NotAuthenticated)
async def not_authenticated(request: Request, exc: NotAuthenticated):
    target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    login = f"/admin/login?next={quote(target, safe='/?=&')}"
    if is_htmx(request):
        return Response(status_code=204, headers={"HX-Redirect": login})
    return RedirectResponse(login, status_code=303)
```

- [ ] **Step 6: Run tests, commit**

Several tests need `/admin` and `/admin/inquiries` to exist (Tasks 4–5). Until then, `test_admin_requires_login`, `test_htmx_request_without_session_gets_hx_redirect` and `test_logout_clears_session` fail with 404: mark them `@pytest.mark.xfail(reason="admin routes land in Tasks 4-5", strict=True)` now and remove the marks in Task 5.

Run: `uv run --no-sync pytest -q` → all pass (3 xfailed).
```bash
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
git add app tests
git commit -m "feat: admin sign-in with signed sessions, CSRF and a login rate limit

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Pipeline model

**Files:**
- Modify: `app/inquiries/models.py`, `tests/test_inquiry_model.py`
- Create: `migrations/versions/<rev>_inquiry_pipeline.py` (generated)

**Interfaces:**
- Produces: `InquiryStage` (`NEW, CONTACTED, QUOTED, WON, LOST`, values lowercase), `STAGES: dict[str, tuple[str, str]]` (value → (label, Phosphor icon)), `Inquiry.stage`, `Inquiry.archived`, `Inquiry.read_at`, `Inquiry.events` (newest first), `EventKind` (`NOTE, STAGE, SYSTEM`), `InquiryEvent` (`id, inquiry_id, author_id, kind, body, created_at`, relationship `author`). `InquiryStatus` and `Inquiry.status` are removed.

- [ ] **Step 1: Rewrite the model test**

Replace `tests/test_inquiry_model.py` with:
```python
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.inquiries.models import EventKind, Inquiry, InquiryEvent, InquiryStage


def make() -> Inquiry:
    return Inquiry(
        name="Chanda Mulenga",
        email="chanda@company.co.zm",
        services=["Website", "Mobile app"],
        message="A booking site.",
    )


async def test_inquiry_defaults(session):
    inquiry = make()
    session.add(inquiry)
    await session.commit()
    await session.refresh(inquiry)
    assert inquiry.services == ["Website", "Mobile app"]
    assert inquiry.stage is InquiryStage.NEW
    assert inquiry.archived is False
    assert inquiry.read_at is None
    assert inquiry.notified_at is None


async def test_unknown_stage_rejected_by_database(session):
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text(
                    "INSERT INTO inquiries (name, email, services, message, stage, archived, created_at) "
                    "VALUES ('a', 'a@b.co', '[]', 'm', 'bogus', false, now())"
                )
            )


async def test_events_cascade_and_order(session, admin):
    inquiry = make()
    session.add(inquiry)
    await session.flush()
    session.add_all(
        [
            InquiryEvent(inquiry_id=inquiry.id, author_id=admin.id, kind=EventKind.NOTE, body="first"),
            InquiryEvent(inquiry_id=inquiry.id, kind=EventKind.SYSTEM, body="second"),
        ]
    )
    await session.commit()
    await session.refresh(inquiry, ["events"])
    assert [e.body for e in inquiry.events] == ["second", "first"]
    await session.delete(inquiry)
    await session.commit()
    assert (await session.scalars(select(InquiryEvent))).all() == []
```

Run: `uv run --no-sync pytest tests/test_inquiry_model.py -q` → collection error (`EventKind` missing).

- [ ] **Step 2: Update the model**

Replace `app/inquiries/models.py` with:
```python
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String, Text, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import User
from app.db import Base, utcnow


def _enum(cls):
    return Enum(cls, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])


class InquiryStage(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    QUOTED = "quoted"
    WON = "won"
    LOST = "lost"


# stage -> (label, Phosphor icon), in pipeline order
STAGES = {
    "new": ("New", "ph-sparkle"),
    "contacted": ("Contacted", "ph-chat-circle-text"),
    "quoted": ("Quoted", "ph-file-text"),
    "won": ("Won", "ph-check-circle"),
    "lost": ("Lost", "ph-x-circle"),
}


class EventKind(StrEnum):
    NOTE = "note"
    STAGE = "stage"
    SYSTEM = "system"


class Inquiry(Base):
    __tablename__ = "inquiries"
    __table_args__ = (
        CheckConstraint(
            "stage IN ('new', 'contacted', 'quoted', 'won', 'lost')", name="stage_values"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    company: Mapped[str | None] = mapped_column(String(160))
    services: Mapped[list[str]] = mapped_column(JSONB, default=list)
    message: Mapped[str] = mapped_column(Text)
    stage: Mapped[InquiryStage] = mapped_column(
        _enum(InquiryStage), default=InquiryStage.NEW, server_default="new"
    )
    archived: Mapped[bool] = mapped_column(default=False, server_default=false())
    read_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    notified_at: Mapped[datetime | None]

    events: Mapped[list["InquiryEvent"]] = relationship(
        back_populates="inquiry",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="desc(InquiryEvent.created_at), desc(InquiryEvent.id)",
    )


class InquiryEvent(Base):
    __tablename__ = "inquiry_events"
    __table_args__ = (
        CheckConstraint("kind IN ('note', 'stage', 'system')", name="kind_values"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    inquiry_id: Mapped[int] = mapped_column(ForeignKey("inquiries.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[EventKind] = mapped_column(_enum(EventKind))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    inquiry: Mapped[Inquiry] = relationship(back_populates="events")
    author: Mapped[User | None] = relationship(lazy="joined")
```

- [ ] **Step 3: Generate the migration**

```bash
uv run --no-sync alembic revision --autogenerate -m "inquiry pipeline"
```
Open the file and check it: adds `stage` (server default `'new'`), `archived` (server default `false`), `read_at`; drops `status` and `ck_inquiries_status_values`; adds `ck_inquiries_stage_values`; creates `inquiry_events` with both foreign keys, `ck_inquiry_events_kind_values` and `ix_inquiry_events_inquiry_id`. If anything is missing or wrong, fix the model, delete the file and regenerate. Then:
```bash
uv run --no-sync alembic upgrade head
uv run --no-sync alembic check
```

- [ ] **Step 4: Run tests and commit**

Run: `uv run --no-sync pytest -q` → all pass (Phase 2 code never referenced `status`; `grep -rn "InquiryStatus\|\.status" app tests` must find nothing).
```bash
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
git add app migrations tests
git commit -m "feat: inquiry pipeline stages, archive flag, read time and activity events

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Admin shell and overview

**Files:**
- Create: `app/admin/__init__.py`, `app/admin/context.py`, `app/admin/routes.py`, `app/templates/admin/layout.html`, `app/templates/admin/_macros.html`, `app/templates/admin/overview.html`, `app/static/js/admin.js`, `tests/test_admin_shell.py`
- Modify: `app/templating.py`, `app/main.py`

**Interfaces:**
- Consumes: `require_admin`, `verify_csrf`, `Inquiry`, `STAGES`.
- Produces: `app.admin.context.admin_context(request, session, user, section: str, title: str, **extra) -> dict` (adds `csrf_token`, `unread_count`, `user`, `section`, `title`, `stages`); `app.admin.routes.router` (`prefix="/admin"`, dependencies `verify_csrf`, `require_admin`); Jinja filter `local_time(dt, fmt="short")` (`short`: `14:05` today, `29 Sep` this year, `29 Sep 2025` older; `long`: `29 Sep 2026, 14:05`) in `settings.timezone`; macros `nav_item`, `page_header`, `stage_chip`, `empty_state`, `unread_dot`.

- [ ] **Step 1: Write the failing tests**

`tests/test_admin_shell.py`:
```python
from datetime import UTC, datetime

from app.inquiries.models import Inquiry, InquiryStage
from app.templating import local_time


def lead(**kw) -> Inquiry:
    return Inquiry(**{"name": "Chanda", "email": "c@x.co", "message": "m", **kw})


async def test_overview_lists_unread_and_needs_reply(admin_client, session):
    session.add_all(
        [
            lead(name="Unread New"),
            lead(name="Read New", read_at=datetime.now(UTC)),
            lead(name="Quoted Lead", stage=InquiryStage.QUOTED, read_at=datetime.now(UTC)),
            lead(name="Spam", archived=True),
        ]
    )
    await session.commit()
    r = await admin_client.get("/admin")
    assert r.status_code == 200
    t = r.text
    assert "Unread New" in t and "Read New" in t  # both are stage New = needs a reply
    assert "Spam" not in t
    assert 'data-unread-count="1"' in t  # nav badge counts unread, non-archived
    assert 'name="csrf-token"' in t
    assert 'hx-headers:inherited=' in t


async def test_overview_empty_state(admin_client):
    t = (await admin_client.get("/admin")).text
    assert "No leads waiting" in t


def test_local_time_formats_in_lusaka():
    now = datetime(2026, 9, 29, 12, 5, tzinfo=UTC)
    assert local_time(datetime(2026, 9, 29, 9, 30, tzinfo=UTC), now=now) == "11:30"
    assert local_time(datetime(2026, 3, 1, 9, 0, tzinfo=UTC), now=now) == "1 Mar"
    assert local_time(datetime(2025, 3, 1, 9, 0, tzinfo=UTC), now=now) == "1 Mar 2025"
    assert local_time(datetime(2026, 9, 29, 9, 30, tzinfo=UTC), "long", now=now) == "29 Sep 2026, 11:30"
```

Run: `uv run --no-sync pytest tests/test_admin_shell.py -q` → collection error (`local_time` missing).

- [ ] **Step 2: Time filter**

Add to `app/templating.py`:
```python
from datetime import datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo(settings.timezone)


def local_time(value: datetime | None, fmt: str = "short", now: datetime | None = None) -> str:
    """Admin display times in the team's timezone. `now` exists for tests."""
    if value is None:
        return ""
    local = value.astimezone(LOCAL_TZ)
    today = (now or datetime.now(LOCAL_TZ)).astimezone(LOCAL_TZ)
    if fmt == "long":
        return f"{local.day} {local:%b %Y, %H:%M}"
    if local.date() == today.date():
        return f"{local:%H:%M}"
    if local.year == today.year:
        return f"{local.day} {local:%b}"
    return f"{local.day} {local:%b %Y}"


templates.env.filters["local_time"] = local_time
```
(Merge the imports into the top of the file.)

- [ ] **Step 3: Shared admin context and overview route**

`app/admin/__init__.py`: empty.

`app/admin/context.py`:
```python
from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.inquiries.models import STAGES, Inquiry


async def admin_context(
    request: Request, session: AsyncSession, user: User, section: str, title: str, **extra
) -> dict:
    unread = await session.scalar(
        select(func.count()).select_from(Inquiry).where(Inquiry.read_at.is_(None), ~Inquiry.archived)
    )
    return {
        "csrf_token": request.session["csrf"],
        "unread_count": unread,
        "user": user,
        "section": section,
        "title": title,
        "stages": STAGES,
        **extra,
    }
```

`app/admin/routes.py`:
```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.context import admin_context
from app.auth.deps import require_admin, verify_csrf
from app.auth.models import User
from app.db import get_session
from app.inquiries.models import Inquiry, InquiryStage
from app.templating import templates

router = APIRouter(prefix="/admin", dependencies=[Depends(verify_csrf), Depends(require_admin)])


@router.get("")
async def overview(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    needs_reply = (
        await session.scalars(
            select(Inquiry)
            .where(Inquiry.stage == InquiryStage.NEW, ~Inquiry.archived)
            .order_by(Inquiry.created_at.desc())
            .limit(10)
        )
    ).all()
    in_progress = (
        await session.scalars(
            select(Inquiry)
            .where(Inquiry.stage.in_([InquiryStage.CONTACTED, InquiryStage.QUOTED]), ~Inquiry.archived)
            .order_by(Inquiry.created_at.desc())
            .limit(10)
        )
    ).all()
    context = await admin_context(
        request, session, user, "overview", "Overview",
        needs_reply=needs_reply, in_progress=in_progress,
    )
    return templates.TemplateResponse(request, "admin/overview.html", context)
```

Register in `app/main.py`: `from app.admin.routes import router as admin_router` and `app.include_router(admin_router)` (after `auth_router`).

- [ ] **Step 4: Layout, macros, overview template, admin.js**

Read `craft-floor.md` first.

`app/templates/admin/_macros.html`:
```html
{% macro nav_item(href, icon, label, current, badge=0) -%}
<li class="flex-1 sm:flex-none">
  <a href="{{ href }}" {% if current %}aria-current="page"{% endif %}
     class="group relative flex flex-col items-center gap-1 rounded-lg px-2 py-2 text-xs text-muted transition-colors duration-200 hover:text-white aria-[current=page]:text-white sm:justify-center lg:flex-row lg:justify-start lg:gap-3 lg:px-3 lg:text-sm lg:aria-[current=page]:bg-raised">
    <i class="ph {{ icon }} text-xl transition-colors duration-200 group-aria-[current=page]:text-brand" aria-hidden="true"></i>
    <span class="sm:sr-only lg:not-sr-only">{{ label }}</span>
    {% if badge %}
    <span class="absolute right-1 top-1 min-w-5 rounded-full bg-brand px-1.5 text-center font-mono text-xs leading-5 text-black lg:static lg:ml-auto" aria-label="{{ badge }} unread">{{ badge }}</span>
    {% endif %}
  </a>
</li>
{%- endmacro %}

{% macro page_header(title, count=None) -%}
<header class="flex min-h-16 items-center justify-between gap-4 border-b border-line px-4 sm:px-6">
  <h1 class="text-xl font-semibold tracking-tight">{{ title }}{% if count is not none %} <span class="font-mono text-sm font-medium text-muted">{{ count }}</span>{% endif %}</h1>
  {% if caller %}<div class="flex items-center gap-2">{{ caller() }}</div>{% endif %}
</header>
{%- endmacro %}

{% macro stage_chip(stages, stage) -%}
{% set label, icon = stages[stage] %}
<span class="inline-flex items-center gap-1 rounded-full border border-line bg-raised px-2 py-0.5 text-xs text-white"><i class="ph {{ icon }}" aria-hidden="true"></i>{{ label }}</span>
{%- endmacro %}

{% macro unread_dot(inquiry) -%}
{% if not inquiry.read_at %}<span class="size-2 shrink-0 rounded-full bg-brand" aria-label="Unread"></span>{% else %}<span class="size-2 shrink-0" aria-hidden="true"></span>{% endif %}
{%- endmacro %}

{% macro empty_state(icon, title, body) -%}
<div class="flex flex-col items-start gap-2 px-4 py-12 sm:px-6">
  <i class="ph {{ icon }} text-2xl text-muted" aria-hidden="true"></i>
  <p class="font-medium">{{ title }}</p>
  <p class="max-w-sm text-sm text-muted">{{ body }}</p>
</div>
{%- endmacro %}
```

`app/templates/admin/layout.html`:
```html
{% extends "base.html" %}
{% from "admin/_macros.html" import nav_item %}
{% block title %}{{ title }} | DHM admin{% endblock %}
{% block meta %}<meta name="robots" content="noindex"><meta name="csrf-token" content="{{ csrf_token }}">{% endblock %}
{% block body_class %}min-h-dvh{% endblock %}
{% block body %}
<div class="flex min-h-dvh" hx-headers:inherited='{"X-CSRF-Token": "{{ csrf_token }}"}'>
  <nav aria-label="Admin"
       class="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-panel sm:sticky sm:top-0 sm:h-dvh sm:w-16 sm:shrink-0 sm:border-r sm:border-t-0 lg:w-56">
    <div class="flex h-full sm:flex-col">
      <a href="/admin" class="hidden h-16 items-center justify-center px-4 sm:flex lg:justify-start">
        <img src="/static/img/logo-light.png" alt="DHM Group admin" width="640" height="314" class="h-6 w-auto">
      </a>
      <ul class="flex flex-1 px-1 sm:flex-col sm:gap-1 sm:px-2" data-unread-count="{{ unread_count }}">
        {{ nav_item("/admin", "ph-squares-four", "Overview", section == "overview") }}
        {{ nav_item("/admin/inquiries", "ph-tray", "Inquiries", section == "inquiries", badge=unread_count) }}
      </ul>
      <form method="post" action="/admin/logout" class="hidden p-2 sm:block">
        <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
        <button type="submit" class="flex w-full items-center justify-center gap-3 rounded-lg px-3 py-2 text-sm text-muted transition-colors duration-200 hover:text-white lg:justify-start" title="Sign out {{ user.email }}">
          <i class="ph ph-sign-out text-xl" aria-hidden="true"></i><span class="sr-only lg:not-sr-only">Sign out</span>
        </button>
      </form>
    </div>
  </nav>
  <main id="main" class="min-w-0 flex-1 pb-20 sm:pb-0">
    {% block content %}{% endblock %}
  </main>
</div>
<div id="toasts" class="pointer-events-none fixed inset-x-4 bottom-20 z-50 flex flex-col items-end gap-2 sm:bottom-4 sm:left-auto" aria-live="polite"></div>
<script src="/static/vendor/htmx/htmx.min.js" defer></script>
<script src="/static/js/admin.js" defer></script>
{% endblock %}
```
(Phones reach "Sign out" from the Overview header, below.)

`app/templates/admin/overview.html`:
```html
{% extends "admin/layout.html" %}
{% from "admin/_macros.html" import page_header, stage_chip, unread_dot, empty_state %}
{% macro lead_rows(items) -%}
<ul class="divide-y divide-line border-y border-line">
  {% for i in items %}
  <li>
    <a href="/admin/inquiries/{{ i.id }}" class="flex items-center gap-3 px-4 py-3 transition-colors duration-200 hover:bg-panel sm:px-6">
      {{ unread_dot(i) }}
      <span class="min-w-0 flex-1">
        <span class="block truncate font-medium">{{ i.name }}</span>
        <span class="block truncate text-sm text-muted">{{ i.company or i.email }}</span>
      </span>
      {{ stage_chip(stages, i.stage) }}
      <span class="w-14 shrink-0 text-right font-mono text-xs text-muted">{{ i.created_at | local_time }}</span>
    </a>
  </li>
  {% endfor %}
</ul>
{%- endmacro %}
{% block content %}
  {% call page_header("Overview") %}
    <form method="post" action="/admin/logout" class="sm:hidden">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
      <button type="submit" class="btn btn-ghost text-sm">Sign out</button>
    </form>
  {% endcall %}
  <section class="pt-6" aria-labelledby="needs-reply">
    <h2 id="needs-reply" class="px-4 pb-3 text-sm font-medium text-muted sm:px-6">Needs a reply <span class="font-mono">{{ needs_reply | length }}</span></h2>
    {% if needs_reply %}{{ lead_rows(needs_reply) }}{% else %}
    {{ empty_state("ph-check", "No leads waiting", "New quote requests from dhmgroup.net land here until someone moves them to Contacted.") }}
    {% endif %}
  </section>
  <section class="pt-8" aria-labelledby="in-progress">
    <h2 id="in-progress" class="px-4 pb-3 text-sm font-medium text-muted sm:px-6">In progress <span class="font-mono">{{ in_progress | length }}</span></h2>
    {% if in_progress %}{{ lead_rows(in_progress) }}{% else %}
    {{ empty_state("ph-hourglass", "Nothing in progress", "Leads you have contacted or quoted appear here so follow-ups do not slip.") }}
    {% endif %}
  </section>
{% endblock %}
```

`app/static/js/admin.js`:
```js
// Admin behaviour: toasts raised by HX-Trigger {"toast": "..."} and focus after htmx swaps.
const toasts = document.getElementById('toasts');
document.addEventListener('toast', e => {
  const el = document.createElement('p');
  el.className = 'pointer-events-auto rounded-xl border border-line bg-raised px-4 py-3 text-sm shadow-lg transition-opacity duration-200';
  el.textContent = e.detail.value;
  toasts.append(el);
  setTimeout(() => { el.classList.add('opacity-0'); setTimeout(() => el.remove(), 200); }, 4000);
});
document.addEventListener('htmx:after:settle', e => {
  e.target.querySelector?.('[data-autofocus]')?.focus();
});
document.addEventListener('htmx:error', () => {
  document.dispatchEvent(new CustomEvent('toast', { detail: { value: 'Something went wrong. Check your connection and try again.' } }));
});
```

- [ ] **Step 5: Run tests, detector, commit**

Run: `uv run --no-sync pytest -q` → all pass (Task 2's xfails for `/admin` may now XPASS: strict xfail fails them, so remove the xfail mark from `test_admin_requires_login` and `test_logout_clears_session` now).
Run: `uv run --no-sync dhm css` and the impeccable detector once: `"C:/Users/50018101/.claude/plugins/cache/impeccable/impeccable/4.3.1/skills/impeccable/scripts/impeccable" detect --json app/templates/admin`; fix real findings.
```bash
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
git add app tests
git commit -m "feat: admin shell with nav rail and overview of leads

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Inquiry list

**Files:**
- Create: `app/inquiries/admin.py`, `app/templates/admin/inquiries.html`, `app/templates/admin/_inquiry_list.html`, `tests/test_admin_inquiries.py`
- Modify: `app/main.py`, `tests/test_auth.py` (remove last xfail)

**Interfaces:**
- Consumes: `admin_context`, `STAGES`, `Inquiry`, `is_htmx`.
- Produces: `app.inquiries.admin.router`; `GET /admin/inquiries?stage=<new|contacted|quoted|won|lost|archived>&q=&page=` (full page, or `_inquiry_list.html` partial for htmx); helpers `list_state(stage, q, page)`, `async load_list(session, stage, q, page) -> dict` (keys `items, counts, stage, q, page, has_next, list_url`), `PAGE_SIZE = 50`. The list root is `<section id="inquiry-list">` and reloads itself on the `inquiry-changed` event from `document`.

- [ ] **Step 1: Write the failing tests**

`tests/test_admin_inquiries.py`:
```python
from datetime import UTC, datetime

from app.inquiries.models import Inquiry, InquiryStage

HX = {"HX-Request": "true"}


def lead(**kw) -> Inquiry:
    return Inquiry(**{"name": "Chanda", "email": "c@x.co", "message": "m", **kw})


async def test_list_defaults_to_new_with_counts(admin_client, session):
    session.add_all(
        [
            lead(name="Alpha"),
            lead(name="Bravo", stage=InquiryStage.QUOTED),
            lead(name="Charlie", archived=True),
        ]
    )
    await session.commit()
    t = (await admin_client.get("/admin/inquiries")).text
    assert "Alpha" in t and "Bravo" not in t and "Charlie" not in t
    assert 'data-count-new="1"' in t and 'data-count-quoted="1"' in t
    assert 'data-count-archived="1"' in t


async def test_stage_tab_and_archived(admin_client, session):
    session.add_all([lead(name="Bravo", stage=InquiryStage.QUOTED), lead(name="Charlie", archived=True)])
    await session.commit()
    assert "Bravo" in (await admin_client.get("/admin/inquiries?stage=quoted")).text
    assert "Charlie" in (await admin_client.get("/admin/inquiries?stage=archived")).text


async def test_unknown_stage_falls_back_to_new(admin_client):
    assert (await admin_client.get("/admin/inquiries?stage=bogus")).status_code == 200


async def test_search_matches_name_email_company_literally(admin_client, session):
    session.add_all(
        [
            lead(name="Mwansa", company="100% Foods"),
            lead(name="Other", company="1000 Foods"),
            lead(name="Mail Match", email="boss@acme.zm"),
        ]
    )
    await session.commit()
    t = (await admin_client.get("/admin/inquiries?q=100%25")).text
    assert "Mwansa" in t and "Other" not in t
    assert "Mail Match" in (await admin_client.get("/admin/inquiries?q=acme")).text


async def test_htmx_returns_list_partial(admin_client, session):
    session.add(lead(name="Alpha"))
    await session.commit()
    r = await admin_client.get("/admin/inquiries?stage=new", headers=HX)
    assert r.status_code == 200
    assert r.text.lstrip().startswith('<section id="inquiry-list"')
    assert "<html" not in r.text


async def test_pagination(admin_client, session):
    session.add_all([lead(name=f"Lead {n:03}", created_at=datetime(2026, 1, 1, tzinfo=UTC).replace(minute=n % 60, hour=n // 60)) for n in range(55)])
    await session.commit()
    first = (await admin_client.get("/admin/inquiries")).text
    assert "Lead 054" in first and "Lead 004" not in first and "page=2" in first
    second = (await admin_client.get("/admin/inquiries?page=2")).text
    assert "Lead 004" in second and "Lead 054" not in second


async def test_unread_rows_show_dot(admin_client, session):
    session.add_all([lead(name="Unread"), lead(name="Seen", read_at=datetime.now(UTC))])
    await session.commit()
    t = (await admin_client.get("/admin/inquiries")).text
    assert t.count('aria-label="Unread"') == 1
```

Remove the remaining `xfail` mark from `test_htmx_request_without_session_gets_hx_redirect` in `tests/test_auth.py`.

Run: `uv run --no-sync pytest tests/test_admin_inquiries.py -q` → FAIL (404).

- [ ] **Step 2: List route**

`app/inquiries/admin.py`:
```python
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.context import admin_context
from app.auth.deps import require_admin, verify_csrf
from app.auth.models import User
from app.db import get_session
from app.htmx import is_htmx
from app.inquiries.models import STAGES, Inquiry
from app.templating import templates

router = APIRouter(
    prefix="/admin/inquiries", dependencies=[Depends(verify_csrf), Depends(require_admin)]
)
PAGE_SIZE = 50
TABS = [*STAGES, "archived"]


def list_state(stage: str | None, q: str | None, page: int | None) -> tuple[str, str, int]:
    return (stage if stage in TABS else "new"), (q or "").strip()[:100], max(page or 1, 1)


def list_url(stage: str, q: str, page: int = 1) -> str:
    params = {"stage": stage, **({"q": q} if q else {}), **({"page": page} if page > 1 else {})}
    return f"/admin/inquiries?{urlencode(params)}"


async def load_list(session: AsyncSession, stage: str, q: str, page: int) -> dict:
    stmt = select(Inquiry)
    if q:
        stmt = stmt.where(
            or_(
                Inquiry.name.icontains(q, autoescape=True),
                Inquiry.email.icontains(q, autoescape=True),
                Inquiry.company.icontains(q, autoescape=True),
            )
        )
    count_stmt = stmt.with_only_columns(Inquiry.stage, Inquiry.archived, func.count()).group_by(
        Inquiry.stage, Inquiry.archived
    )
    counts = dict.fromkeys(TABS, 0)
    for s, archived, n in await session.execute(count_stmt):
        counts["archived" if archived else s] += n

    stmt = stmt.where(Inquiry.archived) if stage == "archived" else stmt.where(
        ~Inquiry.archived, Inquiry.stage == stage
    )
    rows = (
        await session.scalars(
            stmt.order_by(Inquiry.created_at.desc(), Inquiry.id.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE + 1)
        )
    ).all()
    return {
        "items": rows[:PAGE_SIZE],
        "has_next": len(rows) > PAGE_SIZE,
        "counts": counts,
        "tabs": TABS,
        "stage": stage,
        "q": q,
        "page": page,
        "list_url": list_url(stage, q, page),
        "page_url": lambda p: list_url(stage, q, p),
    }


@router.get("")
async def inquiries(
    request: Request,
    stage: str | None = None,
    q: str | None = None,
    page: int | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    listing = await load_list(session, *list_state(stage, q, page))
    if is_htmx(request):
        return templates.TemplateResponse(
            request, "admin/_inquiry_list.html", {**listing, "stages": STAGES}
        )
    context = await admin_context(
        request, session, user, "inquiries", "Inquiries", inquiry=None, **listing
    )
    return templates.TemplateResponse(request, "admin/inquiries.html", context)
```

Register in `app/main.py`: `from app.inquiries.admin import router as inquiries_admin_router` and `app.include_router(inquiries_admin_router)`.

- [ ] **Step 3: Templates**

`app/templates/admin/_inquiry_list.html`:
```html
{% from "admin/_macros.html" import stage_chip, unread_dot, empty_state %}
<section id="inquiry-list"
         class="min-w-0 flex-1 lg:max-w-xl lg:border-r lg:border-line"
         hx-get="{{ list_url }}" hx-trigger="inquiry-changed from:document" hx-target="this" hx-swap="outerHTML">
  <div class="flex min-h-16 items-center justify-between gap-4 border-b border-line px-4 sm:px-6">
    <h1 class="text-xl font-semibold tracking-tight">Inquiries</h1>
    <form role="search" action="/admin/inquiries" hx-get="/admin/inquiries" hx-target="#inquiry-list" hx-swap="outerHTML"
          hx-trigger="input changed delay:300ms from:find input, submit" hx-push-url="true" class="w-40 sm:w-56">
      <input type="hidden" name="stage" value="{{ stage }}">
      <label class="sr-only" for="inquiry-search">Search inquiries</label>
      <input id="inquiry-search" name="q" type="search" value="{{ q }}" placeholder="Search" class="field py-2 text-sm">
    </form>
  </div>
  <nav aria-label="Stages" class="flex gap-1 overflow-x-auto border-b border-line px-2 py-2 sm:px-4">
    {% for tab in tabs %}
    {% set label = stages[tab][0] if tab in stages else "Archived" %}
    <a href="/admin/inquiries?stage={{ tab }}{% if q %}&amp;q={{ q | urlencode }}{% endif %}"
       hx-get="/admin/inquiries?stage={{ tab }}{% if q %}&amp;q={{ q | urlencode }}{% endif %}" hx-target="#inquiry-list" hx-swap="outerHTML" hx-push-url="true"
       {% if tab == stage %}aria-current="page"{% endif %}
       data-count-{{ tab }}="{{ counts[tab] }}"
       class="flex shrink-0 items-center gap-2 rounded-full px-3 py-1.5 text-sm text-muted transition-colors duration-200 hover:text-white aria-[current=page]:bg-brand aria-[current=page]:text-black">
      {{ label }} <span class="font-mono text-xs">{{ counts[tab] }}</span>
    </a>
    {% endfor %}
  </nav>
  {% if items %}
  <ul class="divide-y divide-line">
    {% for i in items %}
    <li>
      <a href="/admin/inquiries/{{ i.id }}?stage={{ stage }}{% if q %}&amp;q={{ q | urlencode }}{% endif %}"
         hx-get="/admin/inquiries/{{ i.id }}" hx-target="#inquiry-panel" hx-swap="outerHTML" hx-push-url="true"
         class="flex items-center gap-3 px-4 py-3 transition-colors duration-200 hover:bg-panel sm:px-6">
        {{ unread_dot(i) }}
        <span class="min-w-0 flex-1">
          <span class="flex items-baseline justify-between gap-3">
            <span class="truncate {% if not i.read_at %}font-semibold{% else %}font-medium{% endif %}">{{ i.name }}</span>
            <span class="shrink-0 font-mono text-xs text-muted">{{ i.created_at | local_time }}</span>
          </span>
          <span class="flex items-center gap-2 text-sm text-muted">
            <span class="truncate">{{ i.company or i.email }}</span>
            {% if i.services %}<span aria-hidden="true">·</span><span class="truncate">{{ i.services | join(", ") }}</span>{% endif %}
            {% if not i.notified_at %}<i class="ph ph-envelope-simple-open ml-auto shrink-0 text-brand" title="Notification email not sent" aria-label="Notification email not sent"></i>{% endif %}
          </span>
        </span>
      </a>
    </li>
    {% endfor %}
  </ul>
  {% if page > 1 or has_next %}
  <nav aria-label="Pages" class="flex justify-between px-4 py-4 text-sm sm:px-6">
    {% if page > 1 %}<a class="btn btn-ghost text-sm" href="{{ page_url(page - 1) }}" hx-get="{{ page_url(page - 1) }}" hx-target="#inquiry-list" hx-swap="outerHTML" hx-push-url="true">Newer</a>{% else %}<span></span>{% endif %}
    {% if has_next %}<a class="btn btn-ghost text-sm" href="{{ page_url(page + 1) }}" hx-get="{{ page_url(page + 1) }}" hx-target="#inquiry-list" hx-swap="outerHTML" hx-push-url="true">Older</a>{% endif %}
  </nav>
  {% endif %}
  {% elif q %}
  {{ empty_state("ph-magnifying-glass", "No matches", "Nothing in this stage matches “" ~ q ~ "”. Try another stage or a shorter search.") }}
  {% else %}
  {{ empty_state("ph-tray", "Nothing here yet", "Leads move through New, Contacted, Quoted and Won or Lost as you work them. Archive spam to keep the pipeline clean.") }}
  {% endif %}
</section>
```

`app/templates/admin/inquiries.html`:
```html
{% extends "admin/layout.html" %}
{% block content %}
<div class="flex min-h-dvh">
  {% include "admin/_inquiry_list.html" %}
  {% if inquiry %}
    {% include "admin/_inquiry_panel.html" %}
  {% else %}
  <section id="inquiry-panel" class="hidden flex-1 items-center justify-center text-sm text-muted lg:flex">
    Select an inquiry to see the message and its history.
  </section>
  {% endif %}
</div>
{% endblock %}
```
Until Task 6 creates `_inquiry_panel.html`, `inquiry` is always `None`, so the include is never reached.

- [ ] **Step 4: Run tests and commit**

Run: `uv run --no-sync pytest -q` → all pass, no xfails left.
```bash
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
git add app tests
git commit -m "feat: admin inquiry list with stage tabs, search and pagination

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Inquiry record and pipeline actions

**Files:**
- Create: `app/templates/admin/_inquiry_panel.html`
- Modify: `app/inquiries/admin.py`, `tests/test_admin_inquiries.py`

**Interfaces:**
- Consumes: `load_list`, `list_state`, `notify_inquiry`, `InquiryEvent`, `EventKind`, `InquiryStage`.
- Produces: `GET /admin/inquiries/{id}` (marks read; full page with list + panel, or `_inquiry_panel.html` for htmx), `POST /admin/inquiries/{id}/stage` (form `stage`), `POST /admin/inquiries/{id}/notes` (form `body`), `POST /admin/inquiries/{id}/archive` (form `archived` = `true|false`), `POST /admin/inquiries/{id}/resend`. Every POST returns the panel partial with `HX-Trigger: {"inquiry-changed": true, "toast": "<message>"}`; non-htmx POSTs 303 back to the record. Pydantic models `StageForm`, `NoteForm`, `ArchiveForm`. `REPLY_SUBJECT = "Re: Your quote request – DHM Group"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_admin_inquiries.py`:
```python
import json

from sqlalchemy import select

from app.inquiries import admin as inquiries_admin
from app.inquiries.models import EventKind, InquiryEvent


async def make_lead(session, **kw) -> Inquiry:
    inquiry = lead(**kw)
    session.add(inquiry)
    await session.commit()
    return inquiry


async def test_opening_marks_read_and_shows_record(admin_client, session):
    inquiry = await make_lead(session, name="Chanda Mulenga", services=["Website"], message="Line one\nLine two")
    r = await admin_client.get(f"/admin/inquiries/{inquiry.id}")
    assert r.status_code == 200
    assert "Line one\nLine two" in r.text
    assert "mailto:c@x.co?subject=Re%3A%20Your%20quote%20request" in r.text
    await session.refresh(inquiry)
    assert inquiry.read_at is not None


async def test_htmx_record_is_panel_partial(admin_client, session):
    inquiry = await make_lead(session)
    r = await admin_client.get(f"/admin/inquiries/{inquiry.id}", headers=HX)
    assert r.text.lstrip().startswith('<section id="inquiry-panel"')


async def test_missing_record_is_404(admin_client):
    assert (await admin_client.get("/admin/inquiries/999999")).status_code == 404


async def test_stage_change_records_event_and_triggers(admin_client, session, admin):
    inquiry = await make_lead(session)
    r = await admin_client.post(f"/admin/inquiries/{inquiry.id}/stage", data={"stage": "contacted"}, headers=HX)
    assert r.status_code == 200
    trigger = json.loads(r.headers["HX-Trigger"])
    assert trigger["inquiry-changed"] is True
    assert trigger["toast"] == "Moved to Contacted"
    await session.refresh(inquiry)
    assert inquiry.stage == "contacted"
    event = await session.scalar(select(InquiryEvent))
    assert (event.kind, event.body, event.author_id) == (EventKind.STAGE, "Moved from New to Contacted", admin.id)


async def test_same_stage_is_a_no_op(admin_client, session):
    inquiry = await make_lead(session)
    await admin_client.post(f"/admin/inquiries/{inquiry.id}/stage", data={"stage": "new"}, headers=HX)
    assert (await session.scalars(select(InquiryEvent))).all() == []


async def test_invalid_stage_is_422(admin_client, session):
    inquiry = await make_lead(session)
    r = await admin_client.post(f"/admin/inquiries/{inquiry.id}/stage", data={"stage": "bogus"}, headers=HX)
    assert r.status_code == 422


async def test_notes_append_with_author(admin_client, session, admin):
    inquiry = await make_lead(session)
    for body in ("Called, left voicemail", "Sent quote PDF"):
        r = await admin_client.post(f"/admin/inquiries/{inquiry.id}/notes", data={"body": body}, headers=HX)
        assert r.status_code == 200
    t = r.text
    assert t.index("Sent quote PDF") < t.index("Called, left voicemail")  # newest first
    notes = (await session.scalars(select(InquiryEvent).where(InquiryEvent.kind == EventKind.NOTE))).all()
    assert {n.author_id for n in notes} == {admin.id}


async def test_empty_note_rejected(admin_client, session):
    inquiry = await make_lead(session)
    r = await admin_client.post(f"/admin/inquiries/{inquiry.id}/notes", data={"body": "   "}, headers=HX)
    assert r.status_code == 422
    assert "Write a note first." in r.text


async def test_archive_and_restore(admin_client, session):
    inquiry = await make_lead(session)
    await admin_client.post(f"/admin/inquiries/{inquiry.id}/archive", data={"archived": "true"}, headers=HX)
    await session.refresh(inquiry)
    assert inquiry.archived is True
    await admin_client.post(f"/admin/inquiries/{inquiry.id}/archive", data={"archived": "false"}, headers=HX)
    await session.refresh(inquiry)
    assert inquiry.archived is False
    bodies = [e.body for e in (await session.scalars(select(InquiryEvent).order_by(InquiryEvent.id))).all()]
    assert bodies == ["Archived", "Restored to the pipeline"]


async def test_resend_records_outcome(admin_client, session, monkeypatch):
    inquiry = await make_lead(session)

    async def fake_notify(inquiry_id, session_factory=None):
        pass  # leaves notified_at empty = failure

    monkeypatch.setattr(inquiries_admin, "notify_inquiry", fake_notify)
    r = await admin_client.post(f"/admin/inquiries/{inquiry.id}/resend", headers=HX)
    assert json.loads(r.headers["HX-Trigger"])["toast"] == "Notification still not sent. Check the SMTP settings."
    event = await session.scalar(select(InquiryEvent))
    assert event.body == "Resend failed"


async def test_plain_post_redirects_back(admin_client, session):
    inquiry = await make_lead(session)
    r = await admin_client.post(f"/admin/inquiries/{inquiry.id}/stage", data={"stage": "quoted"})
    assert r.status_code == 303
    assert r.headers["location"] == f"/admin/inquiries/{inquiry.id}"


async def test_two_admins_both_recorded(admin_client, session):
    from app.auth.users import create_admin

    other = await create_admin(session, "second@dhmgroup.net", "second-password-1")
    inquiry = await make_lead(session)
    session.add(InquiryEvent(inquiry_id=inquiry.id, author_id=other.id, kind=EventKind.NOTE, body="From second"))
    await session.commit()
    t = (await admin_client.post(f"/admin/inquiries/{inquiry.id}/notes", data={"body": "From first"}, headers=HX)).text
    assert "second@dhmgroup.net" in t and "admin@dhmgroup.net" in t
```

Run: `uv run --no-sync pytest tests/test_admin_inquiries.py -q` → new tests FAIL.

- [ ] **Step 2: Routes**

Append to `app/inquiries/admin.py` (merge imports at the top: `import json`, `from typing import Literal`, `from urllib.parse import quote`, `from fastapi import HTTPException`, `from fastapi.responses import RedirectResponse`, `from pydantic import BaseModel, Field, ValidationError, field_validator`, `from sqlalchemy.orm import selectinload`, `from app.db import utcnow`, `from app.inquiries.models import EventKind, InquiryEvent`, `from app.inquiries.notify import notify_inquiry`):
```python
REPLY_SUBJECT = "Re: Your quote request – DHM Group"


class StageForm(BaseModel):
    stage: Literal["new", "contacted", "quoted", "won", "lost"]


class NoteForm(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body", mode="before")
    @classmethod
    def _strip(cls, v):
        return str(v or "").strip()


class ArchiveForm(BaseModel):
    archived: bool


async def _get(session: AsyncSession, inquiry_id: int) -> Inquiry:
    inquiry = await session.scalar(
        select(Inquiry)
        .where(Inquiry.id == inquiry_id)
        .options(selectinload(Inquiry.events).joinedload(InquiryEvent.author))
    )
    if inquiry is None:
        raise HTTPException(status_code=404)
    return inquiry


def _panel_context(request: Request, inquiry: Inquiry, **extra) -> dict:
    mailto = f"mailto:{inquiry.email}?subject={quote(REPLY_SUBJECT)}"
    return {
        "inquiry": inquiry,
        "stages": STAGES,
        "mailto": mailto,
        "note_error": "",
        "csrf_token": request.session["csrf"],
        **extra,
    }


async def _after_action(request, session, inquiry_id: int, toast: str, status_code: int = 200, **extra):
    if not is_htmx(request):
        return RedirectResponse(f"/admin/inquiries/{inquiry_id}", status_code=303)
    session.expire_all()
    inquiry = await _get(session, inquiry_id)
    response = templates.TemplateResponse(
        request, "admin/_inquiry_panel.html", _panel_context(request, inquiry, **extra), status_code=status_code
    )
    if toast:
        response.headers["HX-Trigger"] = json.dumps({"inquiry-changed": True, "toast": toast})
    return response


def _event(inquiry: Inquiry, user: User | None, kind: EventKind, body: str) -> InquiryEvent:
    return InquiryEvent(inquiry_id=inquiry.id, author_id=user.id if user else None, kind=kind, body=body)


@router.get("/{inquiry_id}")
async def record(
    request: Request,
    inquiry_id: int,
    stage: str | None = None,
    q: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    inquiry = await _get(session, inquiry_id)
    if inquiry.read_at is None:
        inquiry.read_at = utcnow()
        await session.commit()
    if is_htmx(request):
        response = templates.TemplateResponse(request, "admin/_inquiry_panel.html", _panel_context(request, inquiry))
        response.headers["HX-Trigger"] = json.dumps({"inquiry-changed": True})
        return response
    list_stage = "archived" if inquiry.archived else inquiry.stage.value
    listing = await load_list(session, *list_state(stage or list_stage, q, 1))
    context = await admin_context(
        request, session, user, "inquiries", inquiry.name, **listing, **_panel_context(request, inquiry)
    )
    return templates.TemplateResponse(request, "admin/inquiries.html", context)


@router.post("/{inquiry_id}/stage")
async def change_stage(
    request: Request, inquiry_id: int,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
):
    try:
        form = StageForm.model_validate(dict(await request.form()))
    except ValidationError:
        raise HTTPException(status_code=422, detail="Unknown stage") from None
    inquiry = await _get(session, inquiry_id)
    if inquiry.stage == form.stage:
        return await _after_action(request, session, inquiry_id, "")
    old, new = STAGES[inquiry.stage][0], STAGES[form.stage][0]
    inquiry.stage = form.stage
    session.add(_event(inquiry, user, EventKind.STAGE, f"Moved from {old} to {new}"))
    await session.commit()
    return await _after_action(request, session, inquiry_id, f"Moved to {new}")


@router.post("/{inquiry_id}/notes")
async def add_note(
    request: Request, inquiry_id: int,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
):
    inquiry = await _get(session, inquiry_id)
    try:
        form = NoteForm.model_validate(dict(await request.form()))
    except ValidationError:
        return await _after_action(
            request, session, inquiry_id, "", status_code=422,
            note_error="Write a note first.",
        )
    session.add(_event(inquiry, user, EventKind.NOTE, form.body))
    await session.commit()
    return await _after_action(request, session, inquiry_id, "Note added")


@router.post("/{inquiry_id}/archive")
async def archive(
    request: Request, inquiry_id: int,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
):
    form = ArchiveForm.model_validate(dict(await request.form()))
    inquiry = await _get(session, inquiry_id)
    if inquiry.archived != form.archived:
        inquiry.archived = form.archived
        body = "Archived" if form.archived else "Restored to the pipeline"
        session.add(_event(inquiry, user, EventKind.SYSTEM, body))
        await session.commit()
    return await _after_action(request, session, inquiry_id, "Archived" if form.archived else "Restored")


@router.post("/{inquiry_id}/resend")
async def resend(
    request: Request, inquiry_id: int,
    session: AsyncSession = Depends(get_session), user: User = Depends(require_admin),
):
    inquiry = await _get(session, inquiry_id)
    await notify_inquiry(inquiry_id)
    await session.refresh(inquiry)
    sent = inquiry.notified_at is not None
    session.add(_event(inquiry, user, EventKind.SYSTEM, "Notification resent" if sent else "Resend failed"))
    await session.commit()
    toast = "Notification sent" if sent else "Notification still not sent. Check the SMTP settings."
    return await _after_action(request, session, inquiry_id, toast)
```
Note on `_after_action` with an empty toast: it still returns the refreshed panel, only without `HX-Trigger`. (`notify_inquiry` opens its own session; in tests it is monkeypatched.)

- [ ] **Step 3: Record panel template**

Read `craft-floor.md` first.

`app/templates/admin/_inquiry_panel.html`:
```html
{% from "admin/_macros.html" import stage_chip %}
<section id="inquiry-panel"
         class="fixed inset-0 z-30 flex flex-col overflow-y-auto bg-black pb-20 sm:left-16 sm:pb-0 lg:static lg:z-auto lg:flex-1"
         aria-labelledby="inquiry-name">
  <header class="flex min-h-16 items-center gap-3 border-b border-line px-4 sm:px-6">
    <a href="/admin/inquiries?stage={{ 'archived' if inquiry.archived else inquiry.stage.value }}" class="-ml-2 rounded-lg p-2 text-muted transition-colors duration-200 hover:text-white lg:hidden" aria-label="Back to inquiries">
      <i class="ph ph-arrow-left text-xl" aria-hidden="true"></i>
    </a>
    <div class="min-w-0 flex-1">
      <h2 id="inquiry-name" class="truncate text-xl font-semibold tracking-tight" tabindex="-1" data-autofocus>{{ inquiry.name }}</h2>
      <p class="truncate text-sm text-muted">{% if inquiry.company %}{{ inquiry.company }} · {% endif %}<span class="font-mono">{{ inquiry.email }}</span></p>
    </div>
    <span class="hidden shrink-0 font-mono text-xs text-muted sm:block">{{ inquiry.created_at | local_time("long") }}</span>
  </header>

  <div class="flex flex-wrap items-center gap-2 border-b border-line px-4 py-4 sm:px-6">
    <a href="{{ mailto }}" class="btn btn-primary text-sm"><i class="ph ph-paper-plane-tilt" aria-hidden="true"></i>Reply by email</a>
    <form hx-post="/admin/inquiries/{{ inquiry.id }}/archive" hx-target="#inquiry-panel" hx-swap="outerHTML"
          method="post" action="/admin/inquiries/{{ inquiry.id }}/archive">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
      <input type="hidden" name="archived" value="{{ 'false' if inquiry.archived else 'true' }}">
      <button type="submit" class="btn btn-ghost text-sm">
        <i class="ph {{ 'ph-arrow-counter-clockwise' if inquiry.archived else 'ph-archive' }}" aria-hidden="true"></i>{{ "Restore" if inquiry.archived else "Archive" }}
      </button>
    </form>
  </div>

  <form class="border-b border-line px-4 py-4 sm:px-6" hx-post="/admin/inquiries/{{ inquiry.id }}/stage" hx-trigger="change"
        hx-target="#inquiry-panel" hx-swap="outerHTML" method="post" action="/admin/inquiries/{{ inquiry.id }}/stage">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <fieldset>
      <legend class="mb-2 text-sm font-medium text-muted">Stage</legend>
      <div class="flex flex-wrap gap-2">
        {% for value, (label, icon) in stages.items() %}
        <label class="cursor-pointer">
          <input type="radio" name="stage" value="{{ value }}" class="peer sr-only" {% if inquiry.stage == value %}checked{% endif %}>
          <span class="flex items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-sm transition-colors duration-200 hover:border-white/40 peer-checked:border-brand peer-checked:bg-brand peer-checked:text-black peer-focus-visible:outline-2 peer-focus-visible:outline-brand">
            <i class="ph {{ icon }}" aria-hidden="true"></i>{{ label }}
          </span>
        </label>
        {% endfor %}
      </div>
      <noscript><button type="submit" class="btn btn-ghost mt-3 text-sm">Save stage</button></noscript>
    </fieldset>
  </form>

  {% if not inquiry.notified_at %}
  <div class="flex items-center justify-between gap-3 border-b border-line px-4 py-3 text-sm sm:px-6" role="status">
    <span class="flex items-center gap-2"><i class="ph ph-warning-circle text-brand" aria-hidden="true"></i>The notification email for this lead was not sent.</span>
    <form hx-post="/admin/inquiries/{{ inquiry.id }}/resend" hx-target="#inquiry-panel" hx-swap="outerHTML" hx-disable="find button"
          method="post" action="/admin/inquiries/{{ inquiry.id }}/resend">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
      <button type="submit" class="btn btn-ghost text-sm">Resend</button>
    </form>
  </div>
  {% endif %}

  <div class="flex flex-col gap-4 border-b border-line px-4 py-6 sm:px-6">
    {% if inquiry.services %}
    <ul class="flex flex-wrap gap-2" aria-label="Services requested">
      {% for s in inquiry.services %}<li class="rounded-full border border-line bg-raised px-2 py-0.5 text-xs">{{ s }}</li>{% endfor %}
    </ul>
    {% endif %}
    <p class="max-w-prose whitespace-pre-line">{{ inquiry.message }}</p>
  </div>

  <div class="flex flex-col gap-4 px-4 py-6 sm:px-6">
    <h3 class="text-sm font-medium text-muted">Activity</h3>
    <form hx-post="/admin/inquiries/{{ inquiry.id }}/notes" hx-target="#inquiry-panel" hx-swap="outerHTML" hx-disable="find button"
          method="post" action="/admin/inquiries/{{ inquiry.id }}/notes" class="flex flex-col gap-2">
      <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
      <label class="sr-only" for="note-body">Add a note</label>
      <textarea id="note-body" name="body" rows="2" maxlength="5000" placeholder="Add a note: a call, a quote sent, a follow-up date"
                class="field resize-y text-sm{% if note_error %} !border-brand{% endif %}" {% if note_error %}aria-invalid="true" data-autofocus{% endif %}></textarea>
      {% if note_error %}<span class="text-sm text-brand" role="alert">{{ note_error }}</span>{% endif %}
      <button type="submit" class="btn btn-ghost self-start text-sm">Add note</button>
    </form>
    <ol class="flex flex-col">
      {% for e in inquiry.events %}
      <li class="flex gap-3 border-t border-line py-3 text-sm">
        <i class="ph {{ 'ph-note' if e.kind == 'note' else ('ph-arrows-left-right' if e.kind == 'stage' else 'ph-gear-six') }} mt-0.5 text-muted" aria-hidden="true"></i>
        <div class="min-w-0 flex-1">
          <p class="{% if e.kind != 'note' %}text-muted{% endif %} whitespace-pre-line">{{ e.body }}</p>
          <p class="mt-1 font-mono text-xs text-muted">{{ e.author.email if e.author else "System" }} · {{ e.created_at | local_time("long") }}</p>
        </div>
      </li>
      {% endfor %}
      <li class="flex gap-3 border-t border-line py-3 text-sm">
        <i class="ph ph-envelope-simple mt-0.5 text-muted" aria-hidden="true"></i>
        <div><p class="text-muted">Quote request received from dhmgroup.net</p>
        <p class="mt-1 font-mono text-xs text-muted">{{ inquiry.created_at | local_time("long") }}</p></div>
      </li>
    </ol>
  </div>
</section>
```
`_panel_context` supplies `csrf_token` for the panel's plain-form fallbacks; htmx requests also carry the header from the layout.

- [ ] **Step 4: Run tests, detector, commit**

Run: `uv run --no-sync pytest -q` → all pass.
Run `uv run --no-sync dhm css` and the detector over `app/templates/admin`; fix real findings.
```bash
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
git add app tests
git commit -m "feat: inquiry record with stage control, notes, archive and resend

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Browser check, finish review, docs

**Files:**
- Modify: `README.md`, `CLAUDE.md`, any admin template the review flags

- [ ] **Step 1: Browser pass (one batched round)**

Seed an admin (`uv run --no-sync dhm create-admin you@dhmgroup.net`) and 3–4 inquiries by submitting the public form on a server at `:8001`. With Playwright (`uv run --no-project --with playwright python <scratchpad script>`), at 390×844 and 1440×900:
1. Sign-in: wrong password shows the error; correct password lands on Overview.
2. Overview lists the leads; the nav badge shows the unread count.
3. Inquiries: tabs switch without a full reload (URL updates); search narrows the list.
4. Open a lead: at 1440 the panel sits beside the list; at 390 it covers the screen with a Back arrow that returns to the list.
5. Change stage to Contacted: a toast appears, the list count updates, the timeline shows "Moved from New to Contacted".
6. Add a note: it appears at the top of the timeline.
7. `Reply by email` has the `mailto:` with the subject.
8. Session expiry: delete the `dhm_admin` cookie, click a tab → the browser lands on `/admin/login?next=…`.
9. No console errors.
Save full-page screenshots of Overview, list and record at both sizes to the scratchpad and review them against the design brief.

- [ ] **Step 2: Finish review**

Run the detector once over `app/templates/admin` and dispatch the `impeccable:impeccable-finish-reviewer` agent with the design brief path, the screenshots and `DESIGN.md`. Fix every material item it returns in one batch; confirm with at most one more screenshot round.

- [ ] **Step 3: Docs**

`README.md`: add Configuration rows

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | development placeholder | Signs the admin session cookie. Required in production (64 random characters) |
| `TIMEZONE` | `Africa/Lusaka` | Time zone for times shown in the admin |

and an "Admin" section: `uv run dhm create-admin you@dhmgroup.net` (prompts for a password, 10+ characters), sign in at `/admin`, `dhm set-password` to reset; in Coolify run `dhm create-admin` from the application terminal. Remove "S3 and session secrets (Phase 3) are documented here when that phase lands." and replace with "S3 settings are documented here when Phase 3b lands."

`CLAUDE.md`: Layout gains `auth/  User, argon2, session + CSRF guard, sign-in` and `admin/  shell: layout context, overview` and `templates/admin/  Ledger shell (see .impeccable/surfaces/app-templates-admin-layout-html.md)`; Rules gain "Admin UI follows the Ledger brief in `.impeccable/surfaces/app-templates-admin-layout-html.md`; read it and `DESIGN.md` before changing admin templates." Phase table: split row 3 into `3a | Admin auth, shell, inquiry pipeline | done` and `3b | Legal, projects, settings, assets (S3) | next`.

- [ ] **Step 4: Final checks and commit**

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
uv run --no-sync alembic check
docker build -t dhm-web .
git add app tests README.md CLAUDE.md
git commit -m "feat: finish the admin shell and inquiry pipeline; phase 3a complete

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
