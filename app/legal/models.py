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
