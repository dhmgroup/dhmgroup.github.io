from datetime import date
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.config import settings

APP_DIR = Path(__file__).parent

templates = Jinja2Templates(directory=APP_DIR / "templates")
templates.env.globals["current_year"] = lambda: date.today().year
templates.env.globals["base_url"] = settings.base_url.rstrip("/")
