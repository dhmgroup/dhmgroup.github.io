from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String, Text, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import User
from app.db import Base, utcnow


def _enum(cls):
    return Enum(cls, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])


class InquiryStage(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    QUOTED = "quoted"
    WON = "won"
    LOST = "lost"


# stage -> (label, Phosphor icon), in pipeline order
STAGES = {
    "new": ("New", "ph-sparkle"),
    "contacted": ("Contacted", "ph-chat-circle-text"),
    "quoted": ("Quoted", "ph-file-text"),
    "won": ("Won", "ph-check-circle"),
    "lost": ("Lost", "ph-x-circle"),
}


class EventKind(StrEnum):
    NOTE = "note"
    STAGE = "stage"
    SYSTEM = "system"


class Inquiry(Base):
    __tablename__ = "inquiries"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    company: Mapped[str | None] = mapped_column(String(160))
    services: Mapped[list[str]] = mapped_column(JSONB, default=list)
    message: Mapped[str] = mapped_column(Text)
    # The check lives on the column type: autogenerate cannot add a table-level CHECK to an
    # existing table, but it does emit the type's constraint together with the new column.
    stage: Mapped[InquiryStage] = mapped_column(
        Enum(
            InquiryStage,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
            create_constraint=True,
            name="stage_values",
        ),
        default=InquiryStage.NEW,
        server_default="new",
    )
    archived: Mapped[bool] = mapped_column(default=False, server_default=false())
    read_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    notified_at: Mapped[datetime | None]

    events: Mapped[list["InquiryEvent"]] = relationship(
        back_populates="inquiry",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="desc(InquiryEvent.created_at), desc(InquiryEvent.id)",
    )


class InquiryEvent(Base):
    __tablename__ = "inquiry_events"
    __table_args__ = (CheckConstraint("kind IN ('note', 'stage', 'system')", name="kind_values"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    inquiry_id: Mapped[int] = mapped_column(
        ForeignKey("inquiries.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[EventKind] = mapped_column(_enum(EventKind))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    inquiry: Mapped[Inquiry] = relationship(back_populates="events")
    author: Mapped[User | None] = relationship(lazy="joined")
