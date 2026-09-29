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
        subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--reload"], check=False)
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
