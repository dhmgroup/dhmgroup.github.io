# DHM Web: Fullstack Migration Design

Date: 2026-09-29
Status: Draft for review

## 1. Goal

Turn the static DHM Group landing page (GitHub Pages) into a fully async server-rendered web app so that legal pages, projects, business contact details and site assets are managed from an admin dashboard, and quote requests are stored in a database and emailed to the team.

The public site must look and behave as it does today. `DESIGN.md` and `PRODUCT.md` remain the source of truth for visual and product decisions.

### Success criteria

- After `dhm seed`, `/` renders visually identical to the current `index.html` (checked against `.impeccable/review/desktop.png` and `mobile.png`).
- A quote request submitted on `/` is saved in Postgres and a notification email is sent; a failed send never loses the inquiry.
- An admin can sign in and edit legal pages, projects, contact details and asset slots, and changes appear on the public site on the next request.
- The app deploys to Coolify from the repo's Dockerfile with Postgres and S3-compatible storage configured by env vars.
- `app-ads.txt` continues to be served at `/app-ads.txt`.

### Decisions made

| Topic | Decision |
|---|---|
| Hosting | Coolify-powered VPS, multistage Dockerfile |
| Database | Postgres (Coolify resource), SQLAlchemy 2.x asyncio + asyncpg, Alembic |
| Storage | S3-compatible (MinIO on Coolify or external S3/R2) via aioboto3 |
| Frontend | Jinja2 templates, htmx v4, Tailwind v4 (standalone CLI build, no Node) |
| Tooling | uv for dependencies, running and scripts |
| Admin auth | Email + password, few admins, no roles |
| Notifications | SMTP email on new inquiry via aiosmtplib |
| Legal editing | Markdown with live htmx preview |
| Assets | Media library plus named site slots |
| Admin design | Built with the impeccable skill, using `DESIGN.md` tokens |

## 2. Current state

- `index.html` (single page, Tailwind v4 browser CDN build, Geist, Phosphor icons, inline JS for menu, reveal animations, FAQ JSON-LD, quote form that falls back to `mailto:`).
- `legal.html` (privacy and terms), `404.html`, `app-ads.txt`, `favicon.svg`, `assets/img/{logo-light,og,tagline}.png`, `logo.png`, `tagline.png`.
- `CNAME` for GitHub Pages.
- Contact details, social links and store links are hard-coded in markup and in a `CONFIG` object in the inline script.

## 3. Architecture

A modular monolith: one FastAPI app, one Postgres database, one bucket. Rejected alternatives: static regeneration on publish (extra build and cache machinery for no gain; inquiries still need a live endpoint) and a JSON API consumed by htmx (works against hypermedia).

### Layout

```
app/
  main.py            # app factory, lifespan (engine, aioboto3 session), routers, static mount, error handlers
  config.py          # pydantic-settings
  db.py              # async engine, async_sessionmaker, get_session dependency, Base
  cli.py             # `dhm` entry point: dev, css, create-admin, set-password, seed
  htmx.py            # is_htmx(request) and render helpers (page vs partial)
  ratelimit.py       # in-memory sliding-window limiter
  auth/              # User model, argon2 hashing, session, CSRF, require_admin, login routes
  site/              # SiteSettings model, admin settings screen
  legal/             # LegalPage model, public /legal/{slug}, admin CRUD + preview
  projects/          # Project model, admin CRUD + reorder
  inquiries/         # Inquiry model, public POST, admin inbox, email notification
  assets/            # Asset model, storage functions (aioboto3), admin library
  public/            # "/", /app-ads.txt, /robots.txt, /sitemap.xml, /healthz, /legal.html redirect
  templates/
    base.html        # shared <head>, fonts, CSS
    public/          # index.html + partials (nav, hero, services, apps, process, faq, quote, footer), legal.html, 404.html, 500.html
    admin/           # layout.html, macros.html (form fields, buttons, tables, toast), per-feature pages and partials
  static/
    src/app.css      # Tailwind v4 entry, @theme tokens from DESIGN.md
    dist/app.css     # build output (gitignored)
    img/             # seed images (logo, tagline, og, favicon)
    js/              # htmx (pinned, vendored), site.js (menu, reveal, tagline effect)
migrations/          # Alembic, async env.py
tests/
compose.yaml         # dev only: postgres, minio, mailpit
Dockerfile
pyproject.toml, uv.lock
CLAUDE.md, README.md
```

Each feature package holds `models.py`, `routes.py` (public and/or admin routers), and a `schemas.py` only when it validates form input. There is no service or repository layer; route handlers use the `AsyncSession` directly. Storage and email are plain async functions in `assets/storage.py` and `inquiries/notify.py`.

### Runtime

- FastAPI on uvicorn, single process, behind Coolify's Traefik (`--proxy-headers`).
- Lifespan creates the async engine and one `aioboto3.Session`; both are disposed on shutdown.
- `get_session` yields one `AsyncSession` per request.
- All I/O is async: asyncpg, aioboto3, aiosmtplib. No sync DB, file or network calls in request handlers.
- htmx and Phosphor icons are vendored under `static/js` and `static/` rather than loaded from a CDN, with pinned versions.

### Frontend

- Tailwind v4 is compiled by the pinned standalone CLI binary. `static/src/app.css` declares the `@theme` tokens that `index.html` currently declares inline (brand, ink, panel, raised, line, muted, fonts, `ease-fluid`), plus the existing component classes (`btn`, `reveal`, etc.).
- The browser CDN Tailwind build is removed.
- The inline script from `index.html` moves to `static/js/site.js`, minus the `CONFIG` object (store links and contact details now come from the server) and minus the form submit logic (handled by htmx).
- The FAQ JSON-LD is rendered server-side in the template instead of built by JS.

## 4. Data model

All tables use integer primary keys and `timestamptz`. Models use SQLAlchemy 2.x `Mapped[...]` annotations.

### users
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| email | varchar(254), unique | stored lowercased |
| password_hash | varchar | argon2 (argon2-cffi) |
| is_active | bool, default true | |
| created_at | timestamptz | |
| last_login_at | timestamptz null | |

### site_settings (single row, id = 1)
| Column | Type | Notes |
|---|---|---|
| id | int PK, check id = 1 | |
| contact_email | varchar | shown on site |
| phone | varchar | shown on site, `tel:` link built by stripping spaces |
| address | text | |
| notify_email | varchar | inquiry notifications go here |
| linkedin_url, facebook_url, instagram_url, x_url, tiktok_url, youtube_url | varchar null | empty hides the icon |
| logo_asset_id, tagline_asset_id, og_asset_id, favicon_asset_id | FK assets null, ON DELETE RESTRICT | empty falls back to the static seed image |
| updated_at | timestamptz | |

### legal_pages
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| slug | varchar(64), unique | lowercase, `[a-z0-9-]+` |
| title | varchar(200) | |
| body_md | text | Markdown source |
| is_published | bool | |
| sort_order | int | footer order |
| updated_at | timestamptz | shown as "Last updated" |

Markdown is rendered with markdown-it-py and sanitised with nh3 (allowlist: headings, paragraphs, lists, links, emphasis, code, blockquote, tables). Rendered HTML is cached in-process keyed by `(id, updated_at)`.

### projects
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| name | varchar(100) | |
| url | varchar null | project landing page |
| summary | varchar(300) | one-line description |
| ios_url, android_url | varchar null | empty renders the button disabled (current behaviour) |
| status | enum `live`, `coming_soon`, `retired` | `live` shows the orange Live dot; `coming_soon` shows a muted "Coming soon" label; `retired` is hidden |
| is_published | bool | |
| sort_order | int | |
| image_asset_id | FK assets null, ON DELETE RESTRICT | optional; the current panel design renders no image, so the template shows it only when set |
| updated_at | timestamptz | |

### inquiries
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| name | varchar(120) | required |
| email | varchar(254) | required, validated |
| company | varchar(160) null | |
| services | JSONB list of strings | subset of `Website`, `Mobile app`, `Email hosting`, `Not sure yet` |
| message | text, max 5000 chars | required |
| status | enum `new`, `read`, `archived` | |
| created_at | timestamptz | |
| notified_at | timestamptz null | null means the email was not sent |

### assets
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| key | varchar, unique | `uploads/{uuid4}{ext}` |
| filename | varchar | original name, display only |
| content_type | varchar | from magic-byte detection |
| size_bytes | int | |
| alt_text | varchar(300) | required for images used in slots |
| created_at | timestamptz | |
| uploaded_by | FK users null, ON DELETE SET NULL | |

Public URL is `{S3_PUBLIC_BASE_URL}/{key}`.

### Seed (`dhm seed`, idempotent)

- `site_settings` from the current footer and quote panel: contact@dhmgroup.net, +260 770 005 939, Plot 4280 Chikola Loop Area, Chingola, Zambia, and the six social URLs.
- Legal pages `privacy` and `terms` from the current `legal.html` wording, converted to Markdown.
- Projects Pepaala News and Nchito with current names, URLs, summaries, status `live`, store URLs empty.

Existing rows are left untouched on re-run (insert only when missing).

## 5. Routes

### Public
| Method, path | Purpose |
|---|---|
| GET `/` | Landing page from settings + published projects + published legal pages (footer) |
| POST `/inquiries` | Quote form submission |
| GET `/legal/{slug}` | Published legal page, 404 otherwise |
| GET `/legal.html` | 301 to `/legal/privacy` |
| GET `/app-ads.txt` | Serves the file content as `text/plain` |
| GET `/robots.txt`, `/sitemap.xml` | Generated |
| GET `/healthz` | `SELECT 1`, returns 200 or 503 |
| static | `/static/...` built CSS, JS, fonts, seed images |

### Admin (all behind `require_admin` except login)
| Path | Purpose |
|---|---|
| `/admin/login`, `/admin/logout` | Session auth |
| `/admin` | Overview: unread inquiry count, recent inquiries, quick links |
| `/admin/inquiries` | Inbox with status filter; view marks read; archive; resend notification |
| `/admin/legal` | List, create, edit (Markdown + preview), publish toggle, delete |
| `/admin/projects` | List, create, edit, publish toggle, reorder (move up/down), delete |
| `/admin/settings` | Contact details, socials, notify email, asset slots |
| `/admin/assets` | Library grid, upload, edit alt text, copy URL, delete |

htmx handles partial updates (row swaps, preview, reorder, upload result, toasts). Every admin screen also works as a full page load.

## 6. Flows

### Quote submission
1. The form keeps `method="post" action="/inquiries"` and adds `hx-post="/inquiries"` targeting the quote panel.
2. Input is validated with a Pydantic model: name, email and message required; email format; services restricted to the four known values; length caps as in the data model.
3. Invalid input returns 422 with the form partial re-rendered, values kept, inline errors in Signal Orange per `DESIGN.md`. The htmx v4 config is set so 422 responses are swapped (verified against the pinned htmx version).
4. A hidden honeypot field (`website`) that is filled returns the success partial without saving.
5. Per-IP limit: 5 submissions per 10 minutes, in-memory (`# ponytail: single-process limiter, move to Redis if running more than one replica`). Exceeding it returns 429 with a friendly message in the form partial.
6. The inquiry is committed, then a `BackgroundTasks` job sends the email via aiosmtplib to `site_settings.notify_email` with `Reply-To` set to the enquirer, and sets `notified_at` in a fresh session.
7. SMTP failure is logged; the inquiry stays with `notified_at = null` and the inbox shows "Not notified" with a Resend action.
8. Success with htmx swaps in the existing confirmation panel. Without JS, the server responds 303 to `/?sent=1#quote`, which renders the confirmation panel.

### Admin authentication
- `POST /admin/login` verifies with argon2 and stores `user_id` and a CSRF token in the Starlette `SessionMiddleware` cookie (signed with `SECRET_KEY`, `HttpOnly`, `Secure` in production, `SameSite=Lax`, max age 8 hours). `last_login_at` is updated.
- Failed logins are limited to 5 per 15 minutes per IP + email using the same limiter. The error message does not reveal whether the email exists.
- `require_admin` loads the user each request and rejects missing or inactive users: 303 to `/admin/login?next=...` for normal requests, `HX-Redirect` header for htmx requests. `next` must be a relative `/admin` path.
- CSRF: the session token is exposed via `hx-headers` on `<body>` (header `X-CSRF-Token`) and a hidden `csrf_token` input in plain forms. Every non-GET admin request is checked; mismatch returns 403.
- Admins are created with `dhm create-admin` and passwords reset with `dhm set-password`. There is no user management UI and no email-based reset.

### Uploads
1. `POST /admin/assets` accepts multipart files up to 10 MB (rejected with 413 beyond that).
2. The type is detected from magic bytes; allowed: PNG, JPEG, WebP, AVIF, SVG, ICO, PDF. Anything else returns 415. The extension comes from the detected type, never the uploaded name.
3. The file is uploaded with `upload_fileobj` to `uploads/{uuid4}{ext}` with the detected `ContentType`, then the `assets` row is inserted. If the insert fails, the object is deleted.
4. SVGs are served only from the bucket origin and never inlined into app pages. The library shows a note to that effect.
5. Delete checks references (settings slots, projects). If referenced, it returns a message naming the users of the asset and does nothing. Otherwise it deletes the row, commits, then deletes the object. A failed object delete is logged and leaves a harmless orphan.

### Legal preview
The editor textarea posts to `/admin/legal/preview` with `hx-trigger="input changed delay:400ms"`. The server returns the sanitised HTML inside the same prose styles the public page uses.

## 7. Error handling

- Public 404 uses the current `404.html` design; public 500 uses the same layout with different copy.
- Admin non-htmx errors render an admin error page. Admin htmx failures (5xx, network) show a toast through one listener in the admin layout, using htmx v4 event names.
- Validation errors are always rendered inline, next to the field, never as a toast.
- Unknown settings row (unseeded database) renders the site with static fallback values from `config.py` defaults, so a fresh deploy never 500s before `dhm seed`.

## 8. Configuration

Loaded by pydantic-settings from env (and `.env` locally).

| Variable | Example | Purpose |
|---|---|---|
| `ENV` | `production` / `development` | toggles Secure cookie, debug |
| `SECRET_KEY` | 64 random chars | session signing, required |
| `DATABASE_URL` | `postgresql+asyncpg://...` | |
| `S3_ENDPOINT_URL` | `https://minio.example.com` | empty for AWS |
| `S3_REGION` | `us-east-1` | |
| `S3_BUCKET` | `dhm-assets` | |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | | |
| `S3_PUBLIC_BASE_URL` | `https://assets.dhmgroup.net/dhm-assets` | base for public asset URLs |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS` | | notifications |
| `SMTP_FROM` | `DHM Group <no-reply@dhmgroup.net>` | |
| `BASE_URL` | `https://dhmgroup.net` | canonical URLs, sitemap, OG |

## 9. Testing

- pytest, pytest-asyncio, `httpx.AsyncClient` with `ASGITransport`.
- Tests run against the compose Postgres (not SQLite) inside a transaction rolled back per test, and against the compose MinIO for storage. The email send function is monkeypatched.
- Required coverage:
  - Inquiry: valid submission saved; validation errors return 422 with inline messages; honeypot saves nothing; rate limit returns 429; SMTP failure keeps the inquiry with `notified_at` null; resend sets it.
  - Auth: login success and failure, lockout after 5 failures, unauthenticated admin request redirects (303 and `HX-Redirect`), CSRF mismatch returns 403, inactive user rejected, `next` rejects external URLs.
  - Uploads: oversize returns 413, disallowed type returns 415, extension derived from content, referenced asset delete refused.
  - Legal: `<script>` and `javascript:` links stripped; unpublished page returns 404; `/legal.html` redirects.
  - Public: `/` renders seeded contact details, projects and footer legal links; unpublished and retired projects hidden; `/app-ads.txt` served.
- Visual parity for phase 1 is checked manually against the `.impeccable/review` screenshots.
- Lint and format with ruff; type check with the current stable checker chosen in the plan.

## 10. Delivery

### Dockerfile (multistage)
1. **builder**: `python:3.13-slim`, `uv` copied from `ghcr.io/astral-sh/uv` (pinned tag). `uv sync --frozen --no-dev --no-install-project`, then the project. Downloads the pinned Tailwind v4 standalone binary, verifies its checksum, and builds `app/static/dist/app.css` minified.
2. **runtime**: `python:3.13-slim`, non-root user, copies `.venv`, `app/`, `migrations/`, `alembic.ini`. Entrypoint runs `alembic upgrade head` then `uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'` (`# ponytail: migrate on boot is single-replica only`). `HEALTHCHECK` calls `/healthz`.

### Local development
`compose.yaml` runs Postgres 17, MinIO (with a bucket created on start and public read on `uploads/`) and Mailpit. `uv run dhm dev` runs uvicorn with reload and the Tailwind CLI in watch mode.

### Coolify
- Application from the Git repo using the Dockerfile; Postgres as a Coolify database resource; MinIO as a Coolify service or an external bucket; env vars set in Coolify.
- After first deploy: `dhm create-admin` and `dhm seed` from the Coolify terminal.

## 11. Migration phases

Each phase ends in a working, deployable state.

0. **Scaffold**: uv project, config, db, Alembic, compose, Dockerfile, `/healthz`, `CLAUDE.md`, `README.md`.
1. **Public port**: split `index.html`, `legal.html`, `404.html` into Jinja templates with markup unchanged; Tailwind build; `site_settings`, `legal_pages`, `projects` models and seed; `/app-ads.txt`, robots, sitemap. Visual parity check.
2. **Inquiries**: model, form endpoint, validation, honeypot, rate limit, SMTP notification.
3. **Admin**: auth and CLI commands; impeccable design pass for the admin shell and components; then inbox, legal (with preview), projects, settings, assets with slots.
4. **Cutover**: deploy on Coolify, point DNS at the VPS, remove the old static HTML files and `CNAME`, disable GitHub Pages.

## 12. Documentation

- **CLAUDE.md** (for coding agents): commands (`uv sync`, `uv run dhm dev`, `uv run pytest`, `uv run ruff check`, `uv run alembic revision --autogenerate`, `uv run dhm seed`), module map and where new code goes, hard rules (async only; `DESIGN.md` tokens only; the Action Orange Rule; public markup changes need a parity check; htmx partials live beside their page template and go through `app/htmx.py`; CSRF on every admin mutation; never trust upload names or client content types; every schema change gets an Alembic migration), and gotchas (htmx v4 differs from v2 docs; `SECRET_KEY` required; S3 public URL vs endpoint URL).
- **README.md** (for people): what the project is, stack, quick start, env var table, running tests, Coolify deployment steps, DNS cutover from GitHub Pages.

## 13. Out of scope

Analytics, multi-language content, legal page revision history, admin roles, user management UI, email password reset, and editing the Services, Process and FAQ sections (they stay in the template). Add any of these as separate changes when needed.
