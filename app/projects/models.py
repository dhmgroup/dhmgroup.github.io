from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class ProjectStatus(StrEnum):
    LIVE = "live"
    COMING_SOON = "coming_soon"
    RETIRED = "retired"


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("status IN ('live', 'coming_soon', 'retired')", name="status_values"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    url: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(String(300))
    ios_url: Mapped[str | None] = mapped_column(String(500))
    android_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(
            ProjectStatus,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ProjectStatus.LIVE,
    )
    is_published: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
