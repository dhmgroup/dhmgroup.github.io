"""Import every model module so Base.metadata is complete (used by Alembic and tests)."""

from app.inquiries import models as inquiries  # noqa: F401
from app.legal import models as legal  # noqa: F401
from app.projects import models as projects  # noqa: F401
from app.site import models as site  # noqa: F401
