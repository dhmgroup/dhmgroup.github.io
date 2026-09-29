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

# Keep equal to TAILWIND_VERSION in app/cli.py. The hash is from the release's sha256sums.txt.
# ponytail: linux-x64 binary only; add an arm64 hash + TARGETARCH switch if the VPS is ARM.
ARG TAILWINDCSS_VERSION=v4.3.3
ARG TAILWINDCSS_SHA256=dc61b3ac6b8c9ca874c0cc4c57b2409791a64c5540404ca5f5367360babc313a
RUN python -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], '/tmp/tailwindcss')" \
      "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWINDCSS_VERSION}/tailwindcss-linux-x64" \
 && echo "${TAILWINDCSS_SHA256}  /tmp/tailwindcss" | sha256sum -c - \
 && chmod +x /tmp/tailwindcss \
 && /tmp/tailwindcss -i app/static/src/app.css -o app/static/dist/app.css --minify

FROM python:${PYTHON_VERSION}-slim
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 ENV=production
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"
# ponytail: migrate on boot is safe for a single replica only; move to a release step if scaled out.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
