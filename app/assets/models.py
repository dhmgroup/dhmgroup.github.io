from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.assets.detect import IMAGE_TYPES
from app.assets.storage import public_url
from app.db import Base, utcnow


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    alt_text: Mapped[str] = mapped_column(String(300), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    @property
    def url(self) -> str:
        return public_url(self.key)

    @property
    def is_image(self) -> bool:
        return self.content_type in IMAGE_TYPES
