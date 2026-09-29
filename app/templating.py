from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.config import settings
from app.legal.render import render_markdown

APP_DIR = Path(__file__).parent
LOCAL_TZ = ZoneInfo(settings.timezone)

templates = Jinja2Templates(directory=APP_DIR / "templates")
templates.env.globals["current_year"] = lambda: date.today().year
templates.env.globals["base_url"] = settings.base_url.rstrip("/")
templates.env.filters["markdown"] = lambda source: Markup(render_markdown(source or ""))


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
