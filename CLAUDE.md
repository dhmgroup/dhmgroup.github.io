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
| 1 | Public site port (landing, legal, 404, app-ads.txt) | done |
| 2 | Inquiries: form endpoint, validation, spam guards, SMTP | next |
| 3 | Admin: auth, inbox, legal, projects, settings, assets | not started |
| 4 | Cutover from GitHub Pages to Coolify | not started |

Update this table in the commit that finishes a phase.

**Until Phase 4, `main` is the live GitHub Pages site.** Work on the `fullstack` branch. Do not merge or push app code to `main` before cutover.

## Commands

All Python tooling runs through uv.

```bash
uv sync                                   # install deps (incl. dev group)
docker compose up -d --wait db            # local Postgres on localhost:5433 (dhm and dhm_test)
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

```text
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
migrations/       Alembic (async env); versions/ holds generated revisions only
tests/            pytest against the compose Postgres
```

New feature = new package under `app/` with `models.py` and `routes.py`; add its models import to `app/models.py` and its router to `app/main.py`. No service or repository layers: handlers use the `AsyncSession` directly.

## Rules

- **Migrations are always generated, never written by hand.** Change the models, then run `uv run alembic revision --autogenerate -m "..."`. Do not create or hand-write migration files, and do not add operations to generated ones. If autogenerate misses or gets a change wrong, fix the model (or the compare settings in `migrations/env.py`), delete the generated file and regenerate. Review each generated file before committing, and `uv run alembic check` must pass.
- **Async all the way.** No sync DB drivers, `requests`, blocking file reads or `time.sleep` in handlers. Use asyncpg, aioboto3, aiosmtplib.
- **One session per request** via `Depends(get_session)`. Never create engines in handlers.
- **Timestamps** use `app.db.utcnow` as a Python-side default. Do not use server-side `onupdate`: an expired attribute lazy-loads, which fails under asyncio.
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
- The dev database listens on host port 5433 (5432 is often taken by other local Postgres containers).
- `.env` is for local dev only. In production every setting comes from Coolify env vars.
- htmx 4 (npm tag `next`) is not htmx 2. Most examples online are htmx 2; check the htmx 4 docs and the vendored source.
- ruff excludes `docs/` (it would otherwise reformat code blocks in the plans).
