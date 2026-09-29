from datetime import date
from pathlib import Path

from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.config import settings
from app.legal.render import render_markdown

APP_DIR = Path(__file__).parent

templates = Jinja2Templates(directory=APP_DIR / "templates")
templates.env.globals["current_year"] = lambda: date.today().year
templates.env.globals["base_url"] = settings.base_url.rstrip("/")
templates.env.filters["markdown"] = lambda source: Markup(render_markdown(source or ""))
