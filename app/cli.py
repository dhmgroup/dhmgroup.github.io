"""`dhm` command: uv run dhm {css,dev,seed,create-admin,set-password}."""

import argparse
import asyncio
import getpass
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


async def _seed() -> None:
    from app.db import SessionLocal, engine
    from app.seed import seed

    async with SessionLocal() as session:
        await seed(session)
    await engine.dispose()


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


def main() -> None:
    parser = argparse.ArgumentParser(prog="dhm")
    sub = parser.add_subparsers(dest="command", required=True)
    css_p = sub.add_parser("css", help="build Tailwind CSS")
    css_p.add_argument("--watch", action="store_true")
    sub.add_parser("dev", help="run uvicorn with reload plus Tailwind watch")
    sub.add_parser("seed", help="insert default content (safe to re-run)")
    for name, help_text in (
        ("create-admin", "add an admin user"),
        ("set-password", "reset an admin's password"),
    ):
        sub.add_parser(name, help=help_text).add_argument("email")
    args = parser.parse_args()

    if args.command == "css":
        css(args.watch)
    elif args.command == "dev":
        dev()
    elif args.command == "seed":
        asyncio.run(_seed())
        print("Seeded.")
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


if __name__ == "__main__":
    main()
