# DHM Web Phases 0–1: Scaffold and Public Site Port — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static GitHub Pages site with a fully async FastAPI app that serves the same landing page, legal pages, 404 page and `app-ads.txt`, driven by Postgres (site settings, legal pages, projects), packaged in a multistage Dockerfile, and documented in `CLAUDE.md` and `README.md`.

**Architecture:** One FastAPI app (`app/`) organised by feature package (`site`, `legal`, `projects`, `public`). Jinja2 renders every page; Tailwind v4 is compiled by the standalone CLI (via `pytailwindcss`, no Node). SQLAlchemy 2.x asyncio + asyncpg talk to Postgres; Alembic owns the schema. Inquiries (Phase 2), admin (Phase 3) and cutover (Phase 4) get their own plans.

**Tech Stack:** Python 3.13, uv 0.11, FastAPI 0.141, SQLAlchemy 2.1 (asyncio), asyncpg 0.31, Alembic 1.20, Jinja2 3.1, pydantic-settings 2.15, markdown-it-py 4.2, nh3 0.3, uvicorn 0.54, Tailwind CSS v4.3.3 (standalone via pytailwindcss 0.3.1), pytest 9 + pytest-asyncio 1.4 + httpx 0.28, ruff 0.16, Postgres 17, Docker.

**Spec:** `docs/superpowers/specs/2026-09-29-dhm-web-fullstack-design.md`

## Global Constraints

- All work happens on branch `fullstack`. `main` is the live GitHub Pages site until Phase 4; never push app code to `main`.
- Async only: no sync DB, file or network calls inside request handlers.
- Public markup is copied from the current `index.html`, `legal.html` and `404.html` unchanged except where a task says otherwise. Colours, radii, spacing and type come only from `DESIGN.md` tokens.
- The Action Orange Rule: `#F05A2B` (`brand`) only on the primary action, selected/live state, focus, selection and errors.
- Every schema change ships an Alembic migration; `uv run alembic check` must pass.
- Tailwind version is `v4.3.3`, pinned in two places: `app/cli.py` (`TAILWIND_VERSION`) and `Dockerfile` (`ARG TAILWINDCSS_VERSION`). Keep them equal.
- Python `>=3.13`; Docker images use `python:3.13-slim`.
- Seed contact details (verbatim): `contact@dhmgroup.net`, `+260 770 005 939`, `Plot 4280 Chikola Loop Area` / `Chingola, Zambia`; socials `https://www.linkedin.com/company/dhmgroup`, `https://www.facebook.com/dhmgroup`, `https://www.instagram.com/dhmgroup`, `https://x.com/dhmgroup`, `https://www.tiktok.com/@dhmgroup`, `https://www.youtube.com/@dhmgroup`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. A social URL left empty → its icon disappears from both the quote panel and the footer (test in Task 8; unit in Task 6).
2. A phone number stored with spaces, dashes or brackets → `tel:` link contains `+` and digits only (test in Task 6).
3. Legal Markdown containing raw HTML (`<iframe>`, `<img onerror>`, `<script>`) or `javascript:` links → rendered inert (test in Task 5).
4. Project name or summary containing `<`, `&` or quotes → escaped on `/`, never interpreted as markup (test in Task 8).
5. Database unreachable → `/healthz` returns 503 (Task 1) and `/` returns the designed 500 page rather than a stack trace (Task 8).

---

## File map

```
.python-version                    T1   pins 3.13 for uv
.gitignore                         T1   python + build output ignores
.env.example                       T1   local env template
pyproject.toml, uv.lock            T1   deps, dhm script, pytest + ruff config
compose.yaml                       T1   dev Postgres (+ test DB)
docker/postgres-init.sql           T1   creates dhm_test
alembic.ini, migrations/           T1   async Alembic env; first revision in T5
app/__init__.py                    T1
app/config.py                      T1   Settings (pydantic-settings)
app/db.py                          T1   Base, engine, SessionLocal, get_session
app/models.py                      T1   imports every model module (Alembic + tests)
app/main.py                        T1   app, lifespan, /healthz; T2 error handlers + static; T7–T9 routers
app/templating.py                  T2   Jinja2Templates + globals/filters
app/cli.py                         T2   `dhm css|dev`; T6 `dhm seed`
app/static/src/app.css             T2   Tailwind entry + tokens + component utilities
app/static/img/*                   T2   logo-light.png, og.png, tagline.png, favicon.svg (copied)
app/static/vendor/phosphor/*       T2   vendored Phosphor 2.1.1 regular + fill
app/templates/base.html            T2   shared <head>
app/templates/public/404.html      T2
app/templates/public/500.html      T2
Dockerfile, .dockerignore          T3
CLAUDE.md, README.md               T4   (PRODUCT.md Stack line updated)
app/site/{__init__,models}.py      T5   SiteSettings, SOCIALS, DEFAULTS, get_site_settings (T6)
app/legal/{__init__,models}.py     T5   LegalPage
app/legal/render.py                T5   render_markdown
app/projects/{__init__,models}.py  T5   Project, ProjectStatus
migrations/versions/*_initial.py   T5
app/seed.py                        T6   seed()
app/legal/routes.py                T7   /legal/{slug}, /legal.html, published_pages()
app/templates/public/legal.html    T7
app/public/{__init__,routes}.py    T8   "/", T9 robots/sitemap/app-ads
app/templates/public/index.html    T8
app/templates/public/_macros.html  T8
app/static/js/site.js              T8
app/static/app-ads.txt             T9   (git mv from repo root)
tests/conftest.py                  T1
tests/test_health.py               T1
tests/test_errors.py               T2
tests/test_render.py               T5
tests/test_site.py                 T6
tests/test_seed.py                 T6
tests/test_legal.py                T7
tests/test_home.py                 T8
tests/test_meta_routes.py          T9
```

---

## Phase 0 — Scaffold

### Task 1: Project scaffold, database, Alembic, health check

**Files:**
- Create: `.python-version`, `.env.example`, `pyproject.toml`, `compose.yaml`, `docker/postgres-init.sql`, `app/__init__.py`, `app/config.py`, `app/db.py`, `app/models.py`, `app/main.py`, `alembic.ini`, `migrations/` (generated), `tests/__init__.py`, `tests/conftest.py`, `tests/test_health.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `app.config.settings` (`env: str`, `database_url: str`, `base_url: str`); `app.db.Base`, `app.db.engine`, `app.db.SessionLocal`, `app.db.get_session() -> AsyncIterator[AsyncSession]`, `app.db.utcnow() -> datetime`; `app.main.app`; test fixtures `session: AsyncSession`, `client: httpx.AsyncClient`.

- [ ] **Step 1: Create the branch**

```bash
git checkout -b fullstack
```

- [ ] **Step 2: Write project files**

`.python-version`:
```
3.13
```

`pyproject.toml`:
```toml
[project]
name = "dhm-web"
version = "0.1.0"
description = "DHM Group website and admin dashboard"
requires-python = ">=3.13"
dependencies = [
    "alembic>=1.20",
    "asyncpg>=0.31",
    "fastapi>=0.141",
    "jinja2>=3.1.6",
    "markdown-it-py>=4.2",
    "nh3>=0.3.7",
    "pydantic-settings>=2.15",
    "sqlalchemy[asyncio]>=2.1.1",
    "uvicorn[standard]>=0.54",
]

[project.scripts]
dhm = "app.cli:main"

[dependency-groups]
dev = [
    "httpx>=0.28.1",
    "pytailwindcss>=0.3.1",
    "pytest>=9.1",
    "pytest-asyncio>=1.4",
    "ruff>=0.16",
]

[build-system]
requires = ["uv_build>=0.11,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "app"
module-root = ""

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "ASYNC"]
```

`.gitignore` (replace whole file; keep the existing CNAME line until Phase 4):
```
# Gitignore for Jekyll
CNAME

# Python
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
.env

# Build output
app/static/dist/
```

`.env.example`:
```
ENV=development
DATABASE_URL=postgresql+asyncpg://dhm:dhm@localhost:5432/dhm
BASE_URL=http://localhost:8000
```

`compose.yaml`:
```yaml
# Local development only. Production services are provisioned in Coolify.
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_USER: dhm
      POSTGRES_PASSWORD: dhm
      POSTGRES_DB: dhm
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./docker/postgres-init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dhm"]
      interval: 2s
      retries: 20

volumes:
  pgdata:
```

`docker/postgres-init.sql`:
```sql
CREATE DATABASE dhm_test OWNER dhm;
```

`app/__init__.py`: empty file.

`app/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+asyncpg://dhm:dhm@localhost:5432/dhm"
    base_url: str = "http://localhost:8000"


settings = Settings()
```

`app/db.py`:
```python
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = {datetime: DateTime(timezone=True)}


def utcnow() -> datetime:
    return datetime.now(UTC)


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
```

`app/models.py`:
```python
"""Import every model module so Base.metadata is complete (used by Alembic and tests)."""
```

`app/main.py`:
```python
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine, get_session


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/healthz")
async def healthz(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return JSONResponse({"status": "database unavailable"}, status_code=503)
    return {"status": "ok"}
```

- [ ] **Step 3: Install and start Postgres**

```bash
uv sync
docker compose up -d --wait db
```
Expected: `uv sync` creates `.venv` and `uv.lock`; compose reports `db` healthy.

- [ ] **Step 4: Initialise async Alembic**

```bash
uv run alembic init -t async migrations
```

Then edit `migrations/env.py`. Replace the line `target_metadata = None` with:
```python
from app import models  # noqa: E402,F401  registers every model on Base.metadata
from app.config import settings  # noqa: E402
from app.db import Base  # noqa: E402

target_metadata = Base.metadata
# configparser treats % specially; escape it so URL-encoded passwords survive.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
```

In `alembic.ini`, delete the line `sqlalchemy.url = driver://user:pass@localhost/dbname`.

Git does not track empty folders, and the Docker image needs `migrations/versions/` to exist:
```bash
touch migrations/versions/.gitkeep
```

Run: `uv run alembic upgrade head`
Expected: exits 0 (no revisions yet).

- [ ] **Step 5: Write test fixtures and the failing health tests**

`tests/__init__.py`: empty file.

`tests/conftest.py`:
```python
import asyncio
import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://dhm:dhm@localhost:5432/dhm_test"
)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, get_session  # noqa: E402
from app.main import app  # noqa: E402

DB_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session", autouse=True)
def _schema():
    async def reset():
        eng = create_async_engine(DB_URL, poolclass=NullPool)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await eng.dispose()

    asyncio.run(reset())


@pytest.fixture
async def session():
    """A session inside a transaction that is rolled back after the test."""
    eng = create_async_engine(DB_URL, poolclass=NullPool)
    async with eng.connect() as conn:
        trans = await conn.begin()
        s = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
        yield s
        await s.close()
        await trans.rollback()
    await eng.dispose()


@pytest.fixture
async def client(session):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

`tests/test_health.py`:
```python
from app.db import get_session
from app.main import app


async def test_healthz_ok(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_healthz_database_down(client):
    class DeadSession:
        async def execute(self, *_):
            raise OSError("connection refused")

    async def dead():
        yield DeadSession()

    app.dependency_overrides[get_session] = dead
    r = await client.get("/healthz")
    assert r.status_code == 503
    assert r.json() == {"status": "database unavailable"}
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest -v`
Expected: 2 passed. (If you run this before Step 2's `/healthz` exists it fails with 404 — the route and tests land together here because the route is three lines.)

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff check . && uv run ruff format --check .
git add .python-version .gitignore .env.example pyproject.toml uv.lock compose.yaml docker app tests alembic.ini migrations
git commit -m "feat: scaffold FastAPI app with async DB, Alembic and health check

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Tailwind pipeline, base template, static assets, error pages, `dhm` CLI

**Files:**
- Create: `app/static/src/app.css`, `app/static/img/{logo-light.png,og.png,tagline.png,favicon.svg}` (copies), `app/static/vendor/phosphor/{regular,fill}/*`, `app/templating.py`, `app/templates/base.html`, `app/templates/public/404.html`, `app/templates/public/500.html`, `app/cli.py`, `tests/test_errors.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `app.main.app` (Task 1).
- Produces: `app.templating.templates` (`Jinja2Templates`, globals `current_year()`, `base_url`); `base.html` blocks `title`, `description`, `meta`, `body_class`, `body`; `app.cli.main()`, `app.cli.TAILWIND_VERSION = "v4.3.3"`; 404 and 500 handlers on `app`.

- [ ] **Step 1: Write the failing test**

`tests/test_errors.py`:
```python
async def test_unknown_path_renders_designed_404(client):
    r = await client.get("/no-such-page")
    assert r.status_code == 404
    assert "This page does not exist." in r.text
    assert '/static/dist/app.css' in r.text


async def test_static_css_entry_is_served(client):
    r = await client.get("/static/src/app.css")
    assert r.status_code == 200
```

Run: `uv run pytest tests/test_errors.py -v`
Expected: FAIL (404 body is FastAPI's JSON; static mount missing).

- [ ] **Step 2: Copy images and vendor Phosphor**

Copy, do not move — the old `index.html` still needs them for the parity check in Task 10.

```bash
mkdir -p app/static/img app/static/vendor/phosphor
cp assets/img/logo-light.png assets/img/og.png assets/img/tagline.png favicon.svg app/static/img/
TMP=$(mktemp -d)
curl -sL https://registry.npmjs.org/@phosphor-icons/web/-/web-2.1.1.tgz | tar -xz -C "$TMP"
cp -r "$TMP/package/src/regular" "$TMP/package/src/fill" app/static/vendor/phosphor/
ls app/static/vendor/phosphor/regular app/static/vendor/phosphor/fill
```
Expected: each folder contains `style.css` and font files (`Phosphor.woff2` / `Phosphor-Fill.woff2` among them).

- [ ] **Step 3: Write the Tailwind entry**

`app/static/src/app.css` (tokens and utilities copied from `index.html` lines 35–82; `source(none)` stops Tailwind scanning `.venv`):
```css
@import "tailwindcss" source(none);
@source "../../templates";
@source "../js";

@theme {
  --font-sans: "Geist", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "Geist Mono", ui-monospace, monospace;
  --color-brand: #F05A2B;
  --color-ink: #000000;
  --color-panel: #181818;
  --color-raised: #1F1F1F;
  --color-line: #272727;
  --color-muted: #A3A3A3;
  --ease-fluid: cubic-bezier(0.32, 0.72, 0, 1);
}

@layer base {
  html { scroll-behavior: smooth; scroll-padding-top: 96px; color-scheme: dark; }
  body { @apply bg-black text-white font-sans antialiased; }
  h1, h2, h3 { text-wrap: balance; }
  p, li, dd { text-wrap: pretty; }
  ::selection { background: #F05A2B; color: #000; }
  input, textarea, select { caret-color: #F05A2B; }
  :focus-visible { outline: 2px solid #F05A2B; outline-offset: 2px; }
  * { scrollbar-color: #313131 #000; }
}

@utility btn {
  @apply inline-flex items-center justify-center gap-2 rounded-full px-3 py-2 font-semibold transition-all duration-700 ease-fluid active:scale-[0.98] disabled:cursor-not-allowed;
}
@utility btn-primary {
  @apply bg-brand text-black hover:bg-white;
}
@utility btn-ghost {
  @apply border border-line text-white hover:border-white/40 hover:bg-white/5;
}
@utility field {
  @apply w-full rounded-xl border border-line bg-black px-3 py-3 text-base text-white placeholder:text-neutral-400 transition-all duration-700 ease-fluid hover:border-white/30 focus:border-brand focus:outline-none;
}

/* Legal page body rendered from Markdown */
.legal-prose {
  & h2 { @apply mt-6 text-2xl font-semibold tracking-tight text-white; }
  & h3 { @apply mt-4 text-xl font-semibold text-white; }
  & ul { @apply flex list-disc flex-col gap-2 pl-6; }
  & ol { @apply flex list-decimal flex-col gap-2 pl-6; }
  & a { @apply text-white underline decoration-line underline-offset-4 transition-all duration-700 ease-fluid hover:decoration-brand; }
  & strong { @apply font-semibold text-white; }
}

/* Scroll interpolation. Content stays visible without JS or with reduced motion. */
@media (prefers-reduced-motion: no-preference) {
  .js .reveal { opacity: 0; transform: translateY(4rem); filter: blur(12px); transition: opacity 900ms cubic-bezier(0.32,0.72,0,1), transform 900ms cubic-bezier(0.32,0.72,0,1), filter 900ms cubic-bezier(0.32,0.72,0,1); transition-delay: var(--d, 0ms); }
  .js .reveal.in { opacity: 1; transform: none; filter: blur(0); }
  .js .swash { clip-path: inset(0 100% 0 0); transition: clip-path 1400ms cubic-bezier(0.32,0.72,0,1); }
  .js .swash.in { clip-path: inset(0 0 0 0); }
}
.word { color: rgb(255 255 255 / 0.3); transition: color 700ms cubic-bezier(0.32,0.72,0,1); }
.word.lit { color: #fff; }
@media (prefers-reduced-motion: reduce) { .word { color: #fff; } }
details > summary { list-style: none; }
details > summary::-webkit-details-marker { display: none; }
details[open] .faq-icon { transform: rotate(45deg); }
```

- [ ] **Step 4: Write the CLI**

`app/cli.py`:
```python
"""`dhm` command: uv run dhm {css,dev}."""

import argparse
import os
import shutil
import subprocess
import sys

TAILWIND_VERSION = "v4.3.3"  # keep equal to ARG TAILWINDCSS_VERSION in Dockerfile
CSS_IN = "app/static/src/app.css"
CSS_OUT = "app/static/dist/app.css"


def _tailwind(*extra: str) -> list[str]:
    exe = shutil.which("tailwindcss")
    if exe is None:
        sys.exit("tailwindcss not found: run `uv sync` (it ships with the dev dependency group).")
    return [exe, "-i", CSS_IN, "-o", CSS_OUT, *extra]


def _env() -> dict[str, str]:
    return {**os.environ, "TAILWINDCSS_VERSION": TAILWIND_VERSION}


def css(watch: bool) -> None:
    if watch:
        subprocess.run(_tailwind("--watch=always"), env=_env(), check=False)
    else:
        subprocess.run(_tailwind("--minify"), env=_env(), check=True)


def dev() -> None:
    watcher = subprocess.Popen(_tailwind("--watch=always"), env=_env())
    try:
        subprocess.run(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--reload"], check=False
        )
    finally:
        watcher.terminate()


def main() -> None:
    parser = argparse.ArgumentParser(prog="dhm")
    sub = parser.add_subparsers(dest="command", required=True)
    css_p = sub.add_parser("css", help="build Tailwind CSS")
    css_p.add_argument("--watch", action="store_true")
    sub.add_parser("dev", help="run uvicorn with reload plus Tailwind watch")
    args = parser.parse_args()

    if args.command == "css":
        css(args.watch)
    elif args.command == "dev":
        dev()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Write templates and templating module**

`app/templating.py`:
```python
from datetime import date
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import settings

APP_DIR = Path(__file__).parent

templates = Jinja2Templates(directory=APP_DIR / "templates")
templates.env.globals["current_year"] = lambda: date.today().year
templates.env.globals["base_url"] = settings.base_url.rstrip("/")
```

`app/templates/base.html`:
```html
<!DOCTYPE html>
<html lang="en" class="bg-black">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}DHM Group{% endblock %}</title>
    <meta name="description" content="{% block description %}{% endblock %}">
    <meta name="theme-color" content="#000000">
    <link rel="icon" href="/static/img/favicon.svg" type="image/svg+xml">
    {% block meta %}{% endblock %}
    <script>document.documentElement.classList.add('js')</script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@500&display=swap"
          rel="stylesheet">
    <link rel="stylesheet" href="/static/vendor/phosphor/regular/style.css">
    <link rel="stylesheet" href="/static/vendor/phosphor/fill/style.css">
    <link rel="stylesheet" href="/static/dist/app.css">
  </head>
  <body class="{% block body_class %}{% endblock %}">
    {% block body %}{% endblock %}
  </body>
</html>
```

`app/templates/public/404.html` (markup from `404.html` lines 18–23, paths made absolute):
```html
{% extends "base.html" %}
{% block title %}Page not found | DHM Group{% endblock %}
{% block meta %}<meta name="robots" content="noindex">{% endblock %}
{% block body_class %}grid min-h-dvh place-items-center px-4{% endblock %}
{% block body %}
  <main class="flex max-w-[680px] flex-col items-start gap-6">
    <a href="/"><img src="/static/img/logo-light.png" alt="DHM Group home" class="h-10 w-auto"></a>
    <h1 class="bg-linear-to-r from-white to-[#9B9B9B] bg-clip-text text-5xl font-semibold tracking-tight text-transparent">This page does not exist.</h1>
    <p class="text-lg text-neutral-400">The link may be old or mistyped. Everything we do is on the home page.</p>
    <a href="/" class="btn btn-primary text-base">Back to home</a>
  </main>
{% endblock %}
```

`app/templates/public/500.html`:
```html
{% extends "base.html" %}
{% block title %}Something went wrong | DHM Group{% endblock %}
{% block meta %}<meta name="robots" content="noindex">{% endblock %}
{% block body_class %}grid min-h-dvh place-items-center px-4{% endblock %}
{% block body %}
  <main class="flex max-w-[680px] flex-col items-start gap-6">
    <a href="/"><img src="/static/img/logo-light.png" alt="DHM Group home" class="h-10 w-auto"></a>
    <h1 class="bg-linear-to-r from-white to-[#9B9B9B] bg-clip-text text-5xl font-semibold tracking-tight text-transparent">Something went wrong on our side.</h1>
    <p class="text-lg text-neutral-400">Please try again in a minute. If it keeps happening, email contact@dhmgroup.net.</p>
    <a href="/" class="btn btn-primary text-base">Back to home</a>
  </main>
{% endblock %}
```

- [ ] **Step 6: Wire static files and error handlers into `app/main.py`**

Add imports:
```python
import logging

from fastapi import Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.templating import APP_DIR, templates

logger = logging.getLogger("app")
```

After `app = FastAPI(...)`, add:
```python
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return templates.TemplateResponse(request, "public/404.html", status_code=404)
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def server_error(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path, exc_info=exc)
    return templates.TemplateResponse(request, "public/500.html", status_code=500)
```

- [ ] **Step 7: Run tests and build CSS**

Run: `uv run pytest -v`
Expected: all pass.

Run: `uv run dhm css`
Expected: first run downloads Tailwind v4.3.3; `app/static/dist/app.css` exists and contains `--color-brand`.

- [ ] **Step 8: Commit**

```bash
uv run ruff check . && uv run ruff format --check .
git add app tests
git commit -m "feat: add Tailwind build, base template, static assets and error pages

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Multistage Dockerfile

**Files:**
- Create: `Dockerfile`, `.dockerignore`

**Interfaces:**
- Consumes: `pyproject.toml`, `uv.lock`, `alembic.ini`, `app/`, `migrations/` (Tasks 1–2).
- Produces: image that migrates on boot and serves on port 8000; `HEALTHCHECK` on `/healthz`.

- [ ] **Step 1: Write `.dockerignore`**

```
.git
.venv
**/__pycache__
.pytest_cache
.ruff_cache
.env
.claude
.impeccable
docs
tests
app/static/dist
assets
*.html
*.png
!app/**
CNAME
compose.yaml
docker
```

- [ ] **Step 2: Write `Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.18 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app

# Dependencies first so code changes don't bust this layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

# Keep equal to TAILWIND_VERSION in app/cli.py.
ARG TAILWINDCSS_VERSION=v4.3.3
RUN --mount=type=cache,target=/root/.cache/uv \
    TAILWINDCSS_VERSION=${TAILWINDCSS_VERSION} \
    uvx --from pytailwindcss==0.3.1 tailwindcss \
      -i app/static/src/app.css -o app/static/dist/app.css --minify

FROM python:${PYTHON_VERSION}-slim
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"
# ponytail: migrate on boot is safe for a single replica only; move to a release step if scaled out.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
```

- [ ] **Step 3: Build and smoke-test**

```bash
docker build -t dhm-web .
docker run --rm -d --name dhm-web-smoke -p 8001:8000 \
  -e DATABASE_URL=postgresql+asyncpg://dhm:dhm@host.docker.internal:5432/dhm dhm-web
curl -s --retry 10 --retry-connrefused --retry-delay 1 http://localhost:8001/healthz
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/static/dist/app.css
docker exec dhm-web-smoke whoami
docker rm -f dhm-web-smoke
```
Expected: `{"status":"ok"}`, `200`, `app`.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "build: add multistage Dockerfile for Coolify

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: CLAUDE.md and README.md

**Files:**
- Create: `CLAUDE.md`, `README.md`
- Modify: `PRODUCT.md` (Stack section)

**Interfaces:**
- Consumes: commands and layout from Tasks 1–3; target layout from the spec.
- Produces: the documents every later task and plan keeps current (the phase table in `CLAUDE.md` is updated when each phase lands).

- [ ] **Step 1: Write `CLAUDE.md`**

````markdown
# CLAUDE.md

Guidance for coding agents working in this repository.

## What this is

The DHM Group website (dhmgroup.net) and, from Phase 3, its admin dashboard. A fully async FastAPI app that server-renders Jinja2 templates styled with Tailwind v4, using htmx v4 for partial updates (from Phase 2). Postgres through SQLAlchemy 2.x asyncio; uploads to S3-compatible storage through aioboto3 (Phase 3). Deployed on a Coolify VPS from the `Dockerfile`.

Read before changing anything visible:
- `PRODUCT.md`: audience, positioning, brand commitments, what must never be fabricated.
- `DESIGN.md`: the design system. Every colour, radius, spacing and type size comes from it.
- `docs/superpowers/specs/2026-09-29-dhm-web-fullstack-design.md`: the approved architecture.
- `docs/superpowers/plans/`: one plan per phase.

## Migration status

| Phase | Scope | Status |
|---|---|---|
| 0 | Scaffold, Docker, docs | done |
| 1 | Public site port (landing, legal, 404, app-ads.txt) | in progress |
| 2 | Inquiries: form endpoint, validation, spam guards, SMTP | not started |
| 3 | Admin: auth, inbox, legal, projects, settings, assets | not started |
| 4 | Cutover from GitHub Pages to Coolify | not started |

Update this table in the commit that finishes a phase.

**Until Phase 4, `main` is the live GitHub Pages site.** Work on the `fullstack` branch. Do not merge or push app code to `main` before cutover.

## Commands

All Python tooling runs through uv.

```bash
uv sync                                   # install deps (incl. dev group)
docker compose up -d --wait db            # local Postgres (creates dhm and dhm_test)
uv run alembic upgrade head               # apply migrations
uv run dhm seed                           # insert default content (idempotent)
uv run dhm dev                            # uvicorn --reload + Tailwind watch, http://localhost:8000
uv run dhm css                            # one-off minified CSS build
uv run pytest                             # tests (needs the compose db)
uv run ruff check . && uv run ruff format .
uv run alembic revision --autogenerate -m "describe change"
uv run alembic check                      # fails if models and migrations disagree
docker build -t dhm-web .                 # production image
```

## Layout

```
app/
  main.py         app, lifespan, error handlers, router registration, /healthz
  config.py       Settings from env / .env
  db.py           Base (naming convention, tz-aware datetimes), engine, get_session, utcnow
  models.py       imports every model module; Alembic and tests rely on it
  templating.py   the one Jinja2Templates instance, globals and filters
  cli.py          `dhm` command
  seed.py         default content
  site/           SiteSettings (single row): contact details, socials, get_site_settings
  legal/          LegalPage, Markdown rendering, public routes
  projects/       Project ("Our apps" panels)
  public/         landing page, robots.txt, sitemap.xml, app-ads.txt
  templates/      base.html, public/, admin/ (Phase 3)
  static/         src/app.css (Tailwind entry), dist/ (built, gitignored), img/, js/, vendor/
migrations/       Alembic (async env)
tests/            pytest against the compose Postgres
```

New feature = new package under `app/` with `models.py` and `routes.py`; add its models import to `app/models.py` and its router to `app/main.py`. No service or repository layers: handlers use the `AsyncSession` directly.

## Rules

- **Async all the way.** No sync DB drivers, `requests`, `open()` on large files, or `time.sleep` in handlers. Use asyncpg, aioboto3, aiosmtplib.
- **One session per request** via `Depends(get_session)`. Never create engines in handlers.
- **Timestamps** use `app.db.utcnow` as a Python-side default. Do not use server-side `onupdate`: an expired attribute lazy-loads, which fails under asyncio.
- **Schema changes** always get an Alembic migration, and `uv run alembic check` must pass.
- **Design tokens only.** Use Tailwind classes backed by the `@theme` in `app/static/src/app.css`, which mirrors `DESIGN.md`. No new colours, radii or fonts.
- **The Action Orange Rule.** `brand` (#F05A2B) appears only on the primary action, selected or live state, focus, selection and errors.
- **Public markup parity.** Public templates are ports of the original static pages. Visual changes to them need a before/after screenshot check at 1440px and 390px.
- **Templates autoescape.** Only mark HTML safe through the `markdown` filter (sanitised with nh3). Never `|safe` user or admin input.
- **No fabricated proof.** No client names, testimonials, statistics or download counts (see PRODUCT.md).
- **htmx (Phase 2+)**: partials live beside their page template, prefixed `_`. Route handlers check for htmx requests through one helper in `app/htmx.py`.
- **Admin (Phase 3+)**: every non-GET admin request is CSRF-checked. Never trust upload file names or client-sent content types.

## Gotchas

- The Tailwind version is pinned in two places: `TAILWIND_VERSION` in `app/cli.py` and `ARG TAILWINDCSS_VERSION` in `Dockerfile`.
- Tailwind uses `source(none)` and only scans `app/templates` and `app/static/js`. Classes built in Python strings will not be generated; keep class names literal in templates or JS.
- Tests use `raise_app_exceptions=False`, so an unexpected exception shows up as a 500 response. Read the logged traceback.
- `.env` is for local dev only. In production every setting comes from Coolify env vars.
- htmx 4 (npm tag `next`) is not htmx 2. Most examples online are htmx 2; check the htmx 4 docs and the vendored source.
````

- [ ] **Step 2: Write `README.md`**

````markdown
# DHM Group website

The website for [DHM Group](https://dhmgroup.net), a Zambian technology company building websites, mobile apps and business email. It is migrating from a static GitHub Pages site to a server-rendered app, so legal pages, projects, contact details and site images can be managed from an admin dashboard, and quote requests are stored and emailed to the team.

## Stack

- **FastAPI** with **Jinja2** templates, fully async
- **SQLAlchemy 2.x (asyncio)** + **asyncpg** on **Postgres**, migrations with **Alembic**
- **Tailwind CSS v4** (standalone CLI, no Node) and **htmx v4**
- **aioboto3** for uploads to S3-compatible storage (admin, Phase 3)
- **uv** for Python tooling, **Docker** for deployment on **Coolify**

## Quick start

Requirements: [uv](https://docs.astral.sh/uv/), Docker.

```bash
cp .env.example .env
uv sync
docker compose up -d --wait db
uv run alembic upgrade head
uv run dhm seed
uv run dhm dev
```

Open http://localhost:8000.

## Configuration

Settings come from environment variables (or `.env` locally).

| Variable | Default | Purpose |
|---|---|---|
| `ENV` | `development` | `production` enables secure cookies (Phase 3) |
| `DATABASE_URL` | `postgresql+asyncpg://dhm:dhm@localhost:5432/dhm` | Postgres connection, must use the `asyncpg` driver |
| `BASE_URL` | `http://localhost:8000` | Canonical URL for sitemap and Open Graph tags |

SMTP (Phase 2) and S3 and session secrets (Phase 3) are documented here as those phases land.

## Tests and linting

```bash
docker compose up -d --wait db     # tests use the dhm_test database
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run alembic check
```

## Deploying on Coolify

1. **Database.** In Coolify, add a PostgreSQL 17 resource. Copy its internal connection URL and change the scheme to `postgresql+asyncpg://`.
2. **Application.** Add an application from this Git repository, branch `fullstack` until cutover (then `main`). Build pack: **Dockerfile**. Port: **8000**.
3. **Environment.** Set `ENV=production`, `DATABASE_URL` and `BASE_URL=https://dhmgroup.net`.
4. **Domain.** Assign `dhmgroup.net` (and `www.dhmgroup.net` if used). Coolify's proxy handles TLS.
5. **Deploy.** Migrations run automatically on container start. After the first deploy, open the application terminal in Coolify and run `dhm seed`.
6. **Health.** The container reports health from `/healthz`, which also checks the database.

## Cutover from GitHub Pages

1. Deploy on Coolify with a temporary domain and check every page.
2. Lower the DNS TTL for `dhmgroup.net` a day ahead.
3. Point the `A`/`AAAA` (or `CNAME`) records at the VPS and assign the domain in Coolify.
4. Once TLS is issued, disable GitHub Pages for the repository and remove the `CNAME` file.
5. Check `https://dhmgroup.net/app-ads.txt` still returns the ad seller list; AdMob depends on it.

## Content notes

- The privacy policy and terms wording is a draft carried over from the static site. Have it reviewed before relying on it.
- App Store and Google Play links for Pepaala News and Nchito are empty until supplied. Empty links render as disabled buttons.
- Project docs: `PRODUCT.md` (product and brand), `DESIGN.md` (design system), `docs/superpowers/` (spec and phase plans), `CLAUDE.md` (guidance for coding agents).
````

- [ ] **Step 3: Update `PRODUCT.md` Stack section**

Replace:
```
Static HTML + Tailwind (user choice). Single `index.html`, no build step, host anywhere.
```
with:
```
FastAPI + Jinja2 + htmx v4 + Tailwind v4, Postgres, deployed on Coolify (migration from the original static `index.html`; see `docs/superpowers/specs/2026-09-29-dhm-web-fullstack-design.md`).
```

And under Capabilities and Constraints replace:
```
- Undecided: form submission backend (no endpoint provided yet).
```
with:
```
- Quote requests are stored in Postgres and emailed to the team (Phase 2).
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md PRODUCT.md
git commit -m "docs: add CLAUDE.md and README.md for the fullstack migration

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Phase 1 — Public site port

### Task 5: Models, Markdown rendering, initial migration

**Files:**
- Create: `app/site/__init__.py`, `app/site/models.py`, `app/legal/__init__.py`, `app/legal/models.py`, `app/legal/render.py`, `app/projects/__init__.py`, `app/projects/models.py`, `migrations/versions/<rev>_initial_content_tables.py` (generated), `tests/test_render.py`
- Modify: `app/models.py`, `app/templating.py`

**Interfaces:**
- Consumes: `app.db.Base`, `app.db.utcnow`.
- Produces:
  - `app.site.models.SiteSettings` with columns `id, contact_email, phone, address, notify_email, linkedin_url, facebook_url, instagram_url, x_url, tiktok_url, youtube_url, updated_at` and properties `tel_href: str`, `address_lines: list[str]`, `address_one_line: str`, `socials: list[tuple[str, str, str]]` (label, phosphor icon class, url); constant `SOCIALS: list[tuple[str, str, str]]` (field, label, icon).
  - `app.legal.models.LegalPage` (`id, slug, title, body_md, is_published, sort_order, updated_at`).
  - `app.projects.models.ProjectStatus` (`StrEnum`: `LIVE="live"`, `COMING_SOON="coming_soon"`, `RETIRED="retired"`) and `Project` (`id, name, url, summary, ios_url, android_url, status, is_published, sort_order, updated_at`).
  - `app.legal.render.render_markdown(source: str) -> str`; Jinja filter `markdown` returning `Markup`.

- [ ] **Step 1: Write the failing render tests**

`tests/test_render.py`:
```python
from app.legal.render import render_markdown


def test_basic_markdown():
    html = render_markdown("## Heading\n\nSome **bold** text and a [link](https://dhmgroup.net).")
    assert "<h2>Heading</h2>" in html
    assert "<strong>bold</strong>" in html
    assert 'href="https://dhmgroup.net"' in html


def test_raw_html_is_not_rendered():
    html = render_markdown(
        '<script>alert(1)</script>\n\n<iframe src="https://evil.test"></iframe>\n\n'
        '<img src=x onerror="alert(1)">'
    )
    assert "<script" not in html
    assert "<iframe" not in html
    assert "<img" not in html


def test_javascript_links_are_neutralised():
    html = render_markdown("[click](javascript:alert(1))")
    assert 'href="javascript' not in html
```

Run: `uv run pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.legal'`.

- [ ] **Step 2: Write models and the renderer**

`app/site/__init__.py`, `app/legal/__init__.py`, `app/projects/__init__.py`: empty files.

`app/site/models.py`:
```python
from datetime import datetime

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow

# (column, label, Phosphor icon), in display order.
SOCIALS = [
    ("linkedin_url", "LinkedIn", "ph-linkedin-logo"),
    ("facebook_url", "Facebook", "ph-facebook-logo"),
    ("instagram_url", "Instagram", "ph-instagram-logo"),
    ("x_url", "X", "ph-x-logo"),
    ("tiktok_url", "TikTok", "ph-tiktok-logo"),
    ("youtube_url", "YouTube", "ph-youtube-logo"),
]


class SiteSettings(Base):
    __tablename__ = "site_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    contact_email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str] = mapped_column(String(40))
    address: Mapped[str] = mapped_column(Text)
    notify_email: Mapped[str] = mapped_column(String(254))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    facebook_url: Mapped[str | None] = mapped_column(String(500))
    instagram_url: Mapped[str | None] = mapped_column(String(500))
    x_url: Mapped[str | None] = mapped_column(String(500))
    tiktok_url: Mapped[str | None] = mapped_column(String(500))
    youtube_url: Mapped[str | None] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    @property
    def tel_href(self) -> str:
        return "tel:+" + "".join(c for c in self.phone if c.isdigit())

    @property
    def address_lines(self) -> list[str]:
        return [line.strip() for line in self.address.splitlines() if line.strip()]

    @property
    def address_one_line(self) -> str:
        return ", ".join(self.address_lines)

    @property
    def socials(self) -> list[tuple[str, str, str]]:
        return [
            (label, icon, url)
            for field, label, icon in SOCIALS
            if (url := getattr(self, field))
        ]
```

`app/legal/models.py`:
```python
from datetime import datetime

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class LegalPage(Base):
    __tablename__ = "legal_pages"
    __table_args__ = (CheckConstraint("slug ~ '^[a-z0-9-]+$'", name="slug_format"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    body_md: Mapped[str] = mapped_column(Text, default="")
    is_published: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
```

`app/projects/models.py`:
```python
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class ProjectStatus(StrEnum):
    LIVE = "live"
    COMING_SOON = "coming_soon"
    RETIRED = "retired"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    url: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(String(300))
    ios_url: Mapped[str | None] = mapped_column(String(500))
    android_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(
            ProjectStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ProjectStatus.LIVE,
    )
    is_published: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
```

`app/legal/render.py`:
```python
from functools import lru_cache

import nh3
from markdown_it import MarkdownIt

# html=False escapes raw HTML in the source; nh3 is the second line of defence.
_md = MarkdownIt("commonmark", {"html": False}).enable("table")


@lru_cache(maxsize=64)
def render_markdown(source: str) -> str:
    return nh3.clean(_md.render(source))
```

Replace `app/models.py` with:
```python
"""Import every model module so Base.metadata is complete (used by Alembic and tests)."""

from app.legal import models as legal  # noqa: F401
from app.projects import models as projects  # noqa: F401
from app.site import models as site  # noqa: F401
```

Append to `app/templating.py`:
```python
from markupsafe import Markup  # noqa: E402

from app.legal.render import render_markdown  # noqa: E402

templates.env.filters["markdown"] = lambda source: Markup(render_markdown(source or ""))
```
(Then move both imports to the top of the file and drop the `noqa` comments — `ruff check --fix` sorts them.)

- [ ] **Step 3: Run render tests**

Run: `uv run pytest tests/test_render.py -v`
Expected: 3 passed.

- [ ] **Step 4: Generate and apply the migration**

```bash
uv run alembic revision --autogenerate -m "initial content tables"
uv run alembic upgrade head
uv run alembic check
```
Expected: the new revision creates `site_settings`, `legal_pages`, `projects` with `ck_site_settings_single_row`, `ck_legal_pages_slug_format`, `uq_legal_pages_slug`; `alembic check` prints `No new upgrade operations detected.` Open the revision file and confirm `projects.status` is `sa.Enum(..., native_enum=False, length=20)` (a `VARCHAR(20)` with a check), not a native Postgres enum.

- [ ] **Step 5: Run all tests and commit**

```bash
uv run pytest -v
uv run ruff check . && uv run ruff format --check .
git add app migrations tests
git commit -m "feat: add site settings, legal page and project models

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Defaults, `get_site_settings`, seed command

**Files:**
- Create: `app/seed.py`, `tests/test_site.py`, `tests/test_seed.py`
- Modify: `app/site/models.py`, `app/cli.py`

**Interfaces:**
- Consumes: models from Task 5.
- Produces: `app.site.models.DEFAULTS: dict[str, str]`; `app.site.models.get_site_settings(session: AsyncSession) -> SiteSettings` (never `None`; returns an unsaved instance built from `DEFAULTS` when the row is missing); `app.seed.seed(session: AsyncSession) -> None` (idempotent, commits); `dhm seed`.

- [ ] **Step 1: Write the failing tests**

`tests/test_site.py`:
```python
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
```

`tests/test_seed.py`:
```python
from sqlalchemy import func, select

from app.legal.models import LegalPage
from app.projects.models import Project, ProjectStatus
from app.seed import seed
from app.site.models import SiteSettings


async def test_seed_creates_default_content(session):
    await seed(session)
    settings = await session.get(SiteSettings, 1)
    assert settings.contact_email == "contact@dhmgroup.net"
    assert settings.youtube_url == "https://www.youtube.com/@dhmgroup"
    slugs = (await session.scalars(select(LegalPage.slug).order_by(LegalPage.sort_order))).all()
    assert slugs == ["privacy", "terms"]
    names = (await session.scalars(select(Project.name).order_by(Project.sort_order))).all()
    assert names == ["Pepaala News", "Nchito"]
    pepaala = await session.scalar(select(Project).where(Project.name == "Pepaala News"))
    assert pepaala.status is ProjectStatus.LIVE
    assert pepaala.url == "https://pepaala.dhmgroup.net"


async def test_seed_is_idempotent_and_keeps_edits(session):
    await seed(session)
    settings = await session.get(SiteSettings, 1)
    settings.phone = "+260 999 999 999"
    await session.commit()

    await seed(session)

    assert (await session.get(SiteSettings, 1)).phone == "+260 999 999 999"
    assert await session.scalar(select(func.count()).select_from(LegalPage)) == 2
    assert await session.scalar(select(func.count()).select_from(Project)) == 2
```

Run: `uv run pytest tests/test_site.py tests/test_seed.py -v`
Expected: FAIL with `ImportError: cannot import name 'DEFAULTS'`.

- [ ] **Step 2: Add defaults and the lookup to `app/site/models.py`**

Add below `SOCIALS`:
```python
DEFAULTS = {
    "contact_email": "contact@dhmgroup.net",
    "phone": "+260 770 005 939",
    "address": "Plot 4280 Chikola Loop Area\nChingola, Zambia",
    "notify_email": "contact@dhmgroup.net",
    "linkedin_url": "https://www.linkedin.com/company/dhmgroup",
    "facebook_url": "https://www.facebook.com/dhmgroup",
    "instagram_url": "https://www.instagram.com/dhmgroup",
    "x_url": "https://x.com/dhmgroup",
    "tiktok_url": "https://www.tiktok.com/@dhmgroup",
    "youtube_url": "https://www.youtube.com/@dhmgroup",
}
```

Add at the end of the file (plus `from sqlalchemy.ext.asyncio import AsyncSession` at the top):
```python
async def get_site_settings(session: AsyncSession) -> SiteSettings:
    """The settings row, or unsaved defaults so an unseeded database still renders."""
    return await session.get(SiteSettings, 1) or SiteSettings(id=1, **DEFAULTS)
```

- [ ] **Step 3: Write `app/seed.py`**

```python
"""Default content. Inserts only what is missing, so re-running never overwrites edits."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.legal.models import LegalPage
from app.projects.models import Project, ProjectStatus
from app.site.models import DEFAULTS, SiteSettings

LEGAL_PAGES = [
    {
        "slug": "privacy",
        "title": "Privacy policy",
        "sort_order": 0,
        "is_published": True,
        "body_md": (
            "When you request a quote, we collect your name, email address, company name and "
            "the project details you choose to share. We use them only to reply to you and "
            "prepare your quote.\n\n"
            "We do not sell your information or share it with advertisers. This website does "
            "not use tracking cookies.\n\n"
            "To see, correct or delete the information we hold about you, email us and we will "
            "act on your request.\n"
        ),
    },
    {
        "slug": "terms",
        "title": "Terms of use",
        "sort_order": 1,
        "is_published": True,
        "body_md": (
            "The content on this website is provided for general information about DHM Group "
            "and its services. It is not a binding offer; the terms of any project are set out "
            "in its written quote.\n\n"
            "The DHM Group name, logo, Pepaala News and Nchito are the property of DHM Group "
            "and may not be used without permission.\n"
        ),
    },
]

PROJECTS = [
    {
        "name": "Pepaala News",
        "url": "https://pepaala.dhmgroup.net",
        "summary": (
            "Zambian news from across the country, gathered into one feed you can read in a "
            "few minutes."
        ),
        "status": ProjectStatus.LIVE,
        "sort_order": 0,
    },
    {
        "name": "Nchito",
        "url": "https://nchito.dhmgroup.net",
        "summary": (
            "A job board that puts open roles from Zambian employers in front of job seekers, "
            "right on their phone."
        ),
        "status": ProjectStatus.LIVE,
        "sort_order": 1,
    },
]


async def seed(session: AsyncSession) -> None:
    if await session.get(SiteSettings, 1) is None:
        session.add(SiteSettings(id=1, **DEFAULTS))

    slugs = set((await session.scalars(select(LegalPage.slug))).all())
    session.add_all(LegalPage(**p) for p in LEGAL_PAGES if p["slug"] not in slugs)

    names = set((await session.scalars(select(Project.name))).all())
    session.add_all(Project(**p) for p in PROJECTS if p["name"] not in names)

    await session.commit()
```

- [ ] **Step 4: Add `dhm seed` to `app/cli.py`**

Add `import asyncio` at the top, and this function:
```python
async def _seed() -> None:
    from app.db import SessionLocal, engine
    from app.seed import seed

    async with SessionLocal() as session:
        await seed(session)
    await engine.dispose()
```

In `main()`, register the subcommand after `dev`:
```python
    sub.add_parser("seed", help="insert default content (safe to re-run)")
```
and dispatch it:
```python
    elif args.command == "seed":
        asyncio.run(_seed())
        print("Seeded.")
```

Update the module docstring to `"""`dhm` command: uv run dhm {css,dev,seed}."""`.

- [ ] **Step 5: Run tests and the command**

```bash
uv run pytest -v
uv run dhm seed && uv run dhm seed
```
Expected: all tests pass; `Seeded.` printed twice with no error.

- [ ] **Step 6: Commit**

```bash
uv run ruff check . && uv run ruff format --check .
git add app tests
git commit -m "feat: add default content, settings fallback and dhm seed

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Public legal pages

**Files:**
- Create: `app/legal/routes.py`, `app/templates/public/legal.html`, `tests/test_legal.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `LegalPage`, `markdown` filter, `seed()`, `templates`.
- Produces: `app.legal.routes.router`; `app.legal.routes.published_pages(session: AsyncSession) -> list[LegalPage]` (published, ordered by `sort_order, id`); routes `GET /legal/{slug}`, `GET /legal.html`.

- [ ] **Step 1: Write the failing tests**

`tests/test_legal.py`:
```python
from app.legal.models import LegalPage
from app.seed import seed


async def test_published_page_renders(client, session):
    await seed(session)
    r = await client.get("/legal/privacy")
    assert r.status_code == 200
    assert "<h1" in r.text and "Privacy policy" in r.text
    assert "We do not sell your information" in r.text
    assert "Last updated" in r.text
    assert 'href="/legal/terms"' in r.text


async def test_unpublished_page_is_404(client, session):
    session.add(LegalPage(slug="cookies", title="Cookies", body_md="x", is_published=False))
    await session.commit()
    r = await client.get("/legal/cookies")
    assert r.status_code == 404
    assert "This page does not exist." in r.text


async def test_unknown_page_is_404(client):
    assert (await client.get("/legal/nope")).status_code == 404


async def test_markdown_body_is_sanitised_on_page(client, session):
    session.add(
        LegalPage(
            slug="xss",
            title="Test",
            body_md="<script>alert(1)</script>\n\n[x](javascript:alert(1))",
            is_published=True,
        )
    )
    await session.commit()
    r = await client.get("/legal/xss")
    assert "<script>alert(1)</script>" not in r.text
    assert 'href="javascript' not in r.text


async def test_old_legal_url_redirects(client):
    r = await client.get("/legal.html")
    assert r.status_code == 301
    assert r.headers["location"] == "/legal/privacy"
```

Run: `uv run pytest tests/test_legal.py -v`
Expected: FAIL (routes return 404 / redirect missing).

- [ ] **Step 2: Write the router**

`app/legal/routes.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.legal.models import LegalPage
from app.templating import templates

router = APIRouter()


async def published_pages(session: AsyncSession) -> list[LegalPage]:
    result = await session.scalars(
        select(LegalPage).where(LegalPage.is_published).order_by(LegalPage.sort_order, LegalPage.id)
    )
    return list(result.all())


@router.get("/legal.html")
async def legacy_legal() -> RedirectResponse:
    return RedirectResponse("/legal/privacy", status_code=301)


@router.get("/legal/{slug}")
async def legal_page(slug: str, request: Request, session: AsyncSession = Depends(get_session)):
    pages = await published_pages(session)
    page = next((p for p in pages if p.slug == slug), None)
    if page is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request, "public/legal.html", {"page": page, "legal_pages": pages}
    )
```

- [ ] **Step 3: Write the template**

`app/templates/public/legal.html` (structure and classes from the old `legal.html`):
```html
{% extends "base.html" %}
{% block title %}{{ page.title }} | DHM Group{% endblock %}
{% block description %}{{ page.title }} for DHM Group and the dhmgroup.net website.{% endblock %}
{% block body_class %}px-4 py-16 sm:px-6{% endblock %}
{% block body %}
  <main class="mx-auto flex max-w-[680px] flex-col gap-12">
    <a href="/" class="flex items-center gap-2 text-sm text-neutral-400 transition-all duration-700 ease-fluid hover:text-white">Back to DHM Group</a>
    <article class="flex flex-col gap-4 text-neutral-300">
      <h1 class="text-4xl font-semibold tracking-tight text-white">{{ page.title }}</h1>
      <p class="text-sm text-muted">Last updated <time datetime="{{ page.updated_at.date().isoformat() }}">{{ page.updated_at.day }} {{ page.updated_at.strftime('%B %Y') }}</time></p>
      <div class="legal-prose flex flex-col gap-4">{{ page.body_md | markdown }}</div>
    </article>
    {% if legal_pages | length > 1 %}
      <nav aria-label="Legal" class="flex flex-wrap gap-6 border-t border-line pt-8 text-sm text-muted">
        {% for p in legal_pages if p.slug != page.slug %}
          <a href="/legal/{{ p.slug }}" class="transition-all duration-700 ease-fluid hover:text-white">{{ p.title }}</a>
        {% endfor %}
      </nav>
    {% endif %}
  </main>
{% endblock %}
```

- [ ] **Step 4: Register the router**

In `app/main.py`, add `from app.legal.routes import router as legal_router` and, after the static mount, `app.include_router(legal_router)`.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest -v
uv run ruff check . && uv run ruff format --check .
git add app tests
git commit -m "feat: serve legal pages from the database

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Landing page port

**Files:**
- Create: `app/public/__init__.py`, `app/public/routes.py`, `app/templates/public/index.html`, `app/templates/public/_macros.html`, `app/static/js/site.js`, `tests/test_home.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `get_site_settings`, `Project`, `ProjectStatus`, `published_pages`, `seed`, `templates`.
- Produces: `app.public.routes.router` with `GET /`; template context keys `site: SiteSettings`, `projects: list[Project]`, `legal_pages: list[LegalPage]`, `org_ld: dict`; `app.public.routes.organization_ld(site: SiteSettings) -> dict`.

- [ ] **Step 1: Write the failing tests**

`tests/test_home.py`:
```python
from sqlalchemy import select

from app.db import get_session
from app.legal.models import LegalPage
from app.main import app
from app.projects.models import Project, ProjectStatus
from app.seed import seed
from app.site.models import SiteSettings


async def test_home_renders_seeded_content(client, session):
    await seed(session)
    r = await client.get("/")
    assert r.status_code == 200
    t = r.text
    assert "We don’t only build apps." in t
    assert 'href="mailto:contact@dhmgroup.net"' in t
    assert 'href="tel:+260770005939"' in t
    assert "Plot 4280 Chikola Loop Area,<br>" in t
    assert "Pepaala News" in t and "Nchito" in t
    assert 'href="/legal/privacy"' in t and 'href="/legal/terms"' in t
    assert '"@type": "Organization"' in t or '"@type":"Organization"' in t
    assert "/static/dist/app.css" in t


async def test_home_renders_without_seed(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "contact@dhmgroup.net" in r.text


async def test_store_buttons(client, session):
    await seed(session)
    pepaala = await session.scalar(select(Project).where(Project.name == "Pepaala News"))
    pepaala.ios_url = "https://apps.apple.com/app/id123"
    await session.commit()
    t = (await client.get("/")).text
    assert 'href="https://apps.apple.com/app/id123"' in t
    assert t.count('aria-disabled="true"') == 3  # Pepaala Android + Nchito iOS/Android


async def test_hidden_and_coming_soon_projects(client, session):
    await seed(session)
    session.add_all(
        [
            Project(name="Draft App", summary="s", is_published=False),
            Project(name="Old App", summary="s", status=ProjectStatus.RETIRED),
            Project(name="Next App", summary="s", status=ProjectStatus.COMING_SOON, sort_order=9),
        ]
    )
    await session.commit()
    t = (await client.get("/")).text
    assert "Draft App" not in t
    assert "Old App" not in t
    assert "Next App" in t and "Coming soon" in t


async def test_project_text_is_escaped(client, session):
    session.add(Project(name='<b>Bold</b> & "Co"', summary="<script>x()</script>"))
    await session.commit()
    t = (await client.get("/")).text
    assert "<b>Bold</b>" not in t
    assert "&lt;b&gt;Bold&lt;/b&gt; &amp;" in t
    assert "<script>x()</script>" not in t


async def test_empty_social_hidden_everywhere(client, session):
    await seed(session)
    (await session.get(SiteSettings, 1)).instagram_url = ""
    await session.commit()
    t = (await client.get("/")).text
    assert "instagram.com" not in t
    assert t.count('aria-label="LinkedIn"') == 2  # quote panel + footer


async def test_unpublished_legal_not_in_footer(client, session):
    await seed(session)
    terms = await session.scalar(select(LegalPage).where(LegalPage.slug == "terms"))
    terms.is_published = False
    await session.commit()
    t = (await client.get("/")).text
    assert 'href="/legal/terms"' not in t


async def test_database_error_renders_500_page(client):
    class DeadSession:
        async def get(self, *_):
            raise OSError("connection refused")

    async def dead():
        yield DeadSession()

    app.dependency_overrides[get_session] = dead
    r = await client.get("/")
    assert r.status_code == 500
    assert "Something went wrong on our side." in r.text
```

Run: `uv run pytest tests/test_home.py -v`
Expected: FAIL (`/` is 404).

- [ ] **Step 2: Write the route**

`app/public/__init__.py`: empty file.

`app/public/routes.py`:
```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.legal.routes import published_pages
from app.projects.models import Project, ProjectStatus
from app.site.models import SiteSettings, get_site_settings
from app.templating import templates

router = APIRouter()


def organization_ld(site: SiteSettings) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "DHM Group",
        "email": site.contact_email,
        "telephone": site.tel_href.removeprefix("tel:"),
        "address": {
            "@type": "PostalAddress",
            "streetAddress": site.address_one_line,
            "addressCountry": "ZM",
        },
        "sameAs": [url for _, _, url in site.socials],
    }


@router.get("/")
async def home(request: Request, session: AsyncSession = Depends(get_session)):
    site = await get_site_settings(session)
    projects = (
        await session.scalars(
            select(Project)
            .where(Project.is_published, Project.status != ProjectStatus.RETIRED)
            .order_by(Project.sort_order, Project.id)
        )
    ).all()
    return templates.TemplateResponse(
        request,
        "public/index.html",
        {
            "site": site,
            "projects": projects,
            "legal_pages": await published_pages(session),
            "org_ld": organization_ld(site),
        },
    )
```

Register in `app/main.py`: `from app.public.routes import router as public_router` and `app.include_router(public_router)`.

- [ ] **Step 3: Write the macros**

`app/templates/public/_macros.html`:
```html
{% macro social_links(site, link_class) -%}
  {% for label, icon, url in site.socials %}
    <li>
      <a href="{{ url }}" target="_blank" rel="noopener" aria-label="{{ label }}" class="{{ link_class }}"><i class="ph {{ icon }}" aria-hidden="true"></i></a>
    </li>
  {% endfor %}
{%- endmacro %}

{% macro store_link(url, icon, label) -%}
  <a {% if url %}href="{{ url }}" target="_blank" rel="noopener"{% else %}aria-disabled="true" title="Store link coming soon"{% endif %}
     class="btn btn-ghost text-sm aria-disabled:pointer-events-none aria-disabled:opacity-50"><i class="ph-fill {{ icon }}" aria-hidden="true"></i>{{ label }}</a>
{%- endmacro %}
```

- [ ] **Step 4: Build `index.html` from the old page**

Create `app/templates/public/index.html` with this frame:
```html
{% extends "base.html" %}
{% from "public/_macros.html" import social_links, store_link %}
{% block title %}DHM Group | Web development, mobile apps and email hosting{% endblock %}
{% block description %}DHM Group designs, builds and hosts websites, iOS and Android apps, and business email. Makers of Pepaala News and Nchito. Request a free project quote.{% endblock %}
{% block meta %}
    <link rel="canonical" href="{{ base_url }}/">
    <meta property="og:type" content="website">
    <meta property="og:title" content="DHM Group | Websites, apps and email, built to keep running">
    <meta property="og:description" content="Web development, mobile apps and business email from the team behind Pepaala News and Nchito.">
    <meta property="og:image" content="{{ base_url }}/static/img/og.png">
    <meta name="twitter:card" content="summary_large_image">
    <script type="application/ld+json">{{ org_ld | tojson }}</script>
{% endblock %}
{% block body %}
BODY
    <script src="/static/js/site.js" defer></script>
{% endblock %}
```

Replace `BODY` with **lines 86–669 of the old `index.html` copied verbatim** (skip link through `</footer>`), then make exactly these edits inside it:

1. **Images.** `src="assets/img/logo-light.png"` → `src="/static/img/logo-light.png"` (nav and footer); `src="assets/img/tagline.png"` → `src="/static/img/tagline.png"` (tagline section and footer).

2. **Apps panels.** Replace both `<article>` elements inside `<div class="mt-16 grid gap-4 md:grid-cols-2">` (old lines 316–347) with:
```html
            {% for p in projects %}
            <article class="reveal{% if not loop.first %} [--d:120ms]{% endif %} flex flex-col rounded-2xl border border-line bg-panel p-8">
              <h3 class="text-3xl font-semibold tracking-tight">
                {%- if p.url -%}
                <a href="{{ p.url }}" target="_blank" rel="noopener" class="group inline-flex items-center gap-2 transition-all duration-700 ease-fluid hover:text-brand">{{ p.name }}<i class="ph ph-arrow-up-right text-2xl text-muted transition-all duration-700 ease-fluid group-hover:translate-x-1 group-hover:-translate-y-1 group-hover:text-brand" aria-hidden="true"></i></a>
                {%- else -%}{{ p.name }}{%- endif -%}
              </h3>
              <p class="mt-3 max-w-sm text-lg text-muted">{{ p.summary }}</p>
              <div class="mt-auto flex flex-wrap items-center gap-3 pt-10">
                {{ store_link(p.ios_url, "ph-apple-logo", "App Store") }}
                {{ store_link(p.android_url, "ph-google-play-logo", "Google Play") }}
                {% if p.status == "live" %}
                <span class="ml-auto flex items-center gap-2 text-sm text-muted"><span class="size-2 rounded-full bg-brand"></span>Live</span>
                {% elif p.status == "coming_soon" %}
                <span class="ml-auto text-sm text-muted">Coming soon</span>
                {% endif %}
              </div>
            </article>
            {% endfor %}
```

3. **Quote panel contact list.** Replace the three `<a>` elements inside the `<dl>` (old lines 442–463) with:
```html
                  <a href="mailto:{{ site.contact_email }}"
                     class="transition-all duration-700 ease-fluid hover:text-brand">{{ site.contact_email }}</a>
```
```html
                  <a href="{{ site.tel_href }}"
                     class="font-mono transition-all duration-700 ease-fluid hover:text-brand">{{ site.phone }}</a>
```
```html
                  <a href="https://www.google.com/maps/search/?api=1&amp;query={{ site.address_one_line | urlencode }}"
                     target="_blank"
                     rel="noopener"
                     class="transition-all duration-700 ease-fluid hover:text-brand">{% for line in site.address_lines %}{{ line }}{% if not loop.last %},<br>{% endif %}{% endfor %}</a>
```

4. **Quote panel socials.** Replace the six `<li>` elements of `<ul class="mt-6 flex flex-wrap gap-2" ...>` (old lines 469–510) with:
```html
                {{ social_links(site, "grid size-10 place-items-center rounded-full border border-line text-xl text-muted transition-all duration-700 ease-fluid hover:border-white/40 hover:text-white active:scale-[0.98]") }}
```

5. **Quote form.** On `<form id="quote-form" novalidate class="flex flex-col gap-4">` add `data-contact-email="{{ site.contact_email }}"`. (Phase 2 replaces the mailto fallback with a real endpoint.)

6. **Footer legal links.** Replace the two `legal.html#privacy` / `legal.html#terms` anchors with:
```html
            {% for p in legal_pages %}
            <a href="/legal/{{ p.slug }}"
               class="transition-all duration-700 ease-fluid hover:text-white">{{ p.title }}</a>
            {% endfor %}
```

7. **Footer socials.** Replace the six `<li>` elements of `<ul class="flex gap-4 text-xl" ...>` with:
```html
            {{ social_links(site, "transition-all duration-700 ease-fluid hover:text-white") }}
```

8. **Year.** Replace `<p>© <span id="year">2016 &middash; 2026</span> DHM Group. All rights reserved.</p>` with `<p>© {{ current_year() }} DHM Group. All rights reserved.</p>`.

- [ ] **Step 5: Move the page script to `app/static/js/site.js`**

Copy old `index.html` lines 690–799 (from `// Mobile menu` to the end of the FAQ schema block) into `app/static/js/site.js`, then:

a. Insert at the top of the file:
```js
// Behaviour for the public landing page. Store links, contact details and the year are rendered by the server.
const CONFIG = { contactEmail: document.getElementById('quote-form')?.dataset.contactEmail || '', formEndpoint: '' };
```
b. Nothing else changes: the remaining code already reads `CONFIG.contactEmail` and `CONFIG.formEndpoint`. The old `CONFIG.stores` block and the `year` line (old lines 671–688) are not copied.

- [ ] **Step 6: Run tests**

Run: `uv run pytest -v`
Expected: all pass. If `test_home_renders_seeded_content` fails on the Organization assertion, check the `tojson` output spacing and keep whichever form it produces.

- [ ] **Step 7: Build CSS and eyeball the page**

```bash
uv run dhm css
uv run dhm seed
uv run uvicorn app.main:app --port 8000
```
Open http://localhost:8000: menu opens on a 390px viewport, sections reveal on scroll, the tagline words light up, the FAQ opens, the quote form's "Request a quote" opens a mail draft addressed to contact@dhmgroup.net. Stop the server.

- [ ] **Step 8: Commit**

```bash
uv run ruff check . && uv run ruff format --check .
git add app tests
git commit -m "feat: render the landing page from site settings and projects

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: robots.txt, sitemap.xml, app-ads.txt

**Files:**
- Create: `tests/test_meta_routes.py`
- Move: `app-ads.txt` → `app/static/app-ads.txt`
- Modify: `app/public/routes.py`

**Interfaces:**
- Consumes: `published_pages`, `settings.base_url`, `APP_DIR`.
- Produces: `GET /robots.txt`, `GET /sitemap.xml`, `GET /app-ads.txt`.

- [ ] **Step 1: Write the failing tests**

`tests/test_meta_routes.py`:
```python
from app.seed import seed


async def test_app_ads_txt(client):
    r = await client.get("/app-ads.txt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "google.com, pub-7456853939285004, DIRECT, f08c47fec0942fa0" in r.text


async def test_robots(client):
    r = await client.get("/robots.txt")
    assert r.status_code == 200
    assert "Disallow: /admin" in r.text
    assert "Sitemap: http://localhost:8000/sitemap.xml" in r.text


async def test_sitemap_lists_home_and_published_legal(client, session):
    await seed(session)
    r = await client.get("/sitemap.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    assert "<loc>http://localhost:8000/</loc>" in r.text
    assert "<loc>http://localhost:8000/legal/privacy</loc>" in r.text
    assert "<loc>http://localhost:8000/legal/terms</loc>" in r.text
```

(The expected `base_url` is the `Settings` default; tests do not set `BASE_URL`. If your shell exports `BASE_URL`, unset it before running tests.)

Run: `uv run pytest tests/test_meta_routes.py -v`
Expected: FAIL (404s).

- [ ] **Step 2: Move the file and add routes**

```bash
git mv app-ads.txt app/static/app-ads.txt
```

Add to `app/public/routes.py` (imports at the top: `from xml.sax.saxutils import escape`, `from fastapi.responses import FileResponse, PlainTextResponse, Response`, `from app.config import settings`, `from app.templating import APP_DIR`):
```python
@router.get("/app-ads.txt")
async def app_ads() -> FileResponse:
    return FileResponse(APP_DIR / "static" / "app-ads.txt", media_type="text/plain")


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots() -> str:
    base = settings.base_url.rstrip("/")
    return f"User-agent: *\nDisallow: /admin\nSitemap: {base}/sitemap.xml\n"


@router.get("/sitemap.xml")
async def sitemap(session: AsyncSession = Depends(get_session)) -> Response:
    base = settings.base_url.rstrip("/")
    urls = [f"{base}/"] + [f"{base}/legal/{p.slug}" for p in await published_pages(session)]
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{escape(u)}</loc></url>\n" for u in urls)
        + "</urlset>\n"
    )
    return Response(body, media_type="application/xml")
```

- [ ] **Step 3: Run tests and commit**

```bash
uv run pytest -v
uv run ruff check . && uv run ruff format --check .
git add app tests
git commit -m "feat: serve app-ads.txt, robots.txt and sitemap.xml

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Visual parity check and retire the static pages

**Files:**
- Delete: `index.html`, `legal.html`, `404.html`, `favicon.svg`, `assets/img/logo-light.png`, `assets/img/og.png`, `assets/img/tagline.png`
- Modify: `CLAUDE.md` (phase table)

**Interfaces:**
- Consumes: the running app (Tasks 1–9) and the old `index.html`.
- Produces: screenshot evidence of parity; Phase 1 marked done.

- [ ] **Step 1: Serve old and new side by side**

```bash
uv run dhm css && uv run dhm seed
uv run uvicorn app.main:app --port 8000 &        # new
uv run python -m http.server 8080 &              # old static page from the repo root
```

- [ ] **Step 2: Screenshot both at desktop and mobile widths**

Save this as `parity.py` in the session scratchpad (not in the repo):
```python
import sys

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

out = sys.argv[1]
targets = {"old": "http://127.0.0.1:8080/index.html", "new": "http://127.0.0.1:8000/"}
sizes = {"desktop": (1440, 900), "mobile": (390, 844)}

with sync_playwright() as p:
    browser = p.chromium.launch()
    for size, (w, h) in sizes.items():
        # Reduced motion shows every .reveal section without scrolling.
        ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce")
        page = ctx.new_page()
        for name, url in targets.items():
            page.goto(url, wait_until="networkidle")
            page.screenshot(path=f"{out}/{size}-{name}.png", full_page=True)
        ctx.close()
    browser.close()

for size in sizes:
    a = Image.open(f"{out}/{size}-old.png").convert("RGB")
    b = Image.open(f"{out}/{size}-new.png").convert("RGB")
    print(size, "old", a.size, "new", b.size)
    if a.size == b.size:
        diff = ImageChops.difference(a, b)
        changed = sum(1 for px in diff.getdata() if px != (0, 0, 0))
        print(f"  changed pixels: {changed / (a.width * a.height):.2%}, bbox {diff.getbbox()}")
```

Run:
```bash
uvx --with playwright playwright install chromium
uv run --with playwright --with pillow python <scratchpad>/parity.py <scratchpad>
```
Expected: same page heights at both sizes and a changed-pixel share under 1%. Differences are only expected in the footer year text (the old page also rendered the current year via JS, so none) and font anti-aliasing.

- [ ] **Step 3: Review the screenshots**

Open all four PNGs and compare each section: nav, hero, services, apps, tagline, process, FAQ, quote panel, footer. Also compare `mobile-new.png` against `.impeccable/review/mobile.png` and `desktop-new.png` against `.impeccable/review/desktop.png`. Any layout, colour or spacing difference is a bug in the Task 8 port: fix it and re-run Step 2. The most likely cause is a class used only in the old inline `<style type="text/tailwindcss">` that `app/static/src/app.css` does not define. Also check http://127.0.0.1:8000/legal/privacy against http://127.0.0.1:8080/legal.html, and http://127.0.0.1:8000/missing against http://127.0.0.1:8080/404.html.

- [ ] **Step 4: Stop servers and remove the old static files**

```bash
kill %1 %2
git rm index.html legal.html 404.html favicon.svg assets/img/logo-light.png assets/img/og.png assets/img/tagline.png
```
(`CNAME` stays until Phase 4. `logo.png` and `tagline.png` at the root are source artwork referenced by `PRODUCT.md`; leave them.)

- [ ] **Step 5: Mark Phase 1 done**

In `CLAUDE.md`'s migration table set Phase 1 to `done` and Phase 2 to `next`.

- [ ] **Step 6: Final checks and commit**

```bash
uv run pytest -v
uv run ruff check . && uv run ruff format --check .
uv run alembic check
docker build -t dhm-web .
git add -A CLAUDE.md
git commit -m "chore: retire static pages after parity check; phase 1 complete

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
Expected: tests pass, lint clean, no pending migrations, image builds.
