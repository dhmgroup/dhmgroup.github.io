from datetime import datetime

from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow

# (column, label, Phosphor icon), in display order.
SOCIALS = [
    ("linkedin_url", "LinkedIn", "ph-linkedin-logo"),
    ("facebook_url", "Facebook", "ph-facebook-logo"),
    ("instagram_url", "Instagram", "ph-instagram-logo"),
    ("x_url", "X", "ph-x-logo"),
    ("tiktok_url", "TikTok", "ph-tiktok-logo"),
    ("youtube_url", "YouTube", "ph-youtube-logo"),
]

DEFAULTS = {
    "contact_email": "contact@dhmgroup.net",
    "phone": "+260 770 005 939",
    "address": "Plot 4280 Chikola Loop Area\nChingola, Zambia",
    "notify_email": "contact@dhmgroup.net",
    "linkedin_url": "https://www.linkedin.com/company/dhmgroup",
    "facebook_url": "https://www.facebook.com/dhmgroup",
    "instagram_url": "https://www.instagram.com/dhmgroup",
    "x_url": "https://x.com/dhmgroup",
    "tiktok_url": "https://www.tiktok.com/@dhmgroup",
    "youtube_url": "https://www.youtube.com/@dhmgroup",
}


class SiteSettings(Base):
    __tablename__ = "site_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    contact_email: Mapped[str] = mapped_column(String(254))
    phone: Mapped[str] = mapped_column(String(40))
    address: Mapped[str] = mapped_column(Text)
    notify_email: Mapped[str] = mapped_column(String(254))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    facebook_url: Mapped[str | None] = mapped_column(String(500))
    instagram_url: Mapped[str | None] = mapped_column(String(500))
    x_url: Mapped[str | None] = mapped_column(String(500))
    tiktok_url: Mapped[str | None] = mapped_column(String(500))
    youtube_url: Mapped[str | None] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    @property
    def tel_href(self) -> str:
        return "tel:+" + "".join(c for c in self.phone if c.isdigit())

    @property
    def address_lines(self) -> list[str]:
        return [line.strip() for line in self.address.splitlines() if line.strip()]

    @property
    def address_one_line(self) -> str:
        return ", ".join(self.address_lines)

    @property
    def socials(self) -> list[tuple[str, str, str]]:
        return [
            (label, icon, url) for field, label, icon in SOCIALS if (url := getattr(self, field))
        ]


async def get_site_settings(session: AsyncSession) -> SiteSettings:
    """The settings row, or unsaved defaults so an unseeded database still renders."""
    return await session.get(SiteSettings, 1) or SiteSettings(id=1, **DEFAULTS)
