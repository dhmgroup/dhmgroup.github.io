from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.context import admin_context
from app.admin.forms import Email, OptionalHttps, Phone, field_errors, hx_toast
from app.assets.detect import IMAGE_TYPES
from app.assets.models import Asset
from app.auth.deps import require_admin, verify_csrf
from app.auth.models import User
from app.db import get_session
from app.site.models import SLOTS, SOCIALS, SiteSettings, get_site_settings
from app.templating import templates

router = APIRouter(
    prefix="/admin/settings", dependencies=[Depends(require_admin), Depends(verify_csrf)]
)
MESSAGES = {"address": "Enter the registered address (up to 300 characters)."}


class SettingsForm(BaseModel):
    contact_email: Email
    phone: Phone
    address: str = Field(min_length=1, max_length=300)
    notify_email: Email
    linkedin_url: OptionalHttps = None
    facebook_url: OptionalHttps = None
    instagram_url: OptionalHttps = None
    x_url: OptionalHttps = None
    tiktok_url: OptionalHttps = None
    youtube_url: OptionalHttps = None
    logo_asset_id: int | None = None
    tagline_asset_id: int | None = None
    og_asset_id: int | None = None
    favicon_asset_id: int | None = None


def _form_data(form) -> dict:
    data = {name: form.get(name) for name in SettingsForm.model_fields}
    data["address"] = str(data["address"] or "").strip()
    for slot in SLOTS:
        raw = str(data[slot] or "").strip()
        data[slot] = int(raw) if raw.isdigit() else None
    return data


async def _render(request, session, user, site, errors=None, status_code=200, values=None):
    images = (
        await session.scalars(
            select(Asset).where(Asset.content_type.in_(IMAGE_TYPES)).order_by(Asset.filename)
        )
    ).all()
    context = await admin_context(
        request,
        session,
        user,
        "settings",
        "Settings",
        site=site,
        values=values or {},
        errors=errors or {},
        socials=SOCIALS,
        slots=SLOTS,
        images=images,
    )
    return templates.TemplateResponse(
        request, "admin/settings.html", context, status_code=status_code
    )


async def _slot_errors(session: AsyncSession, form: SettingsForm) -> dict[str, str]:
    errors = {}
    for slot, label in SLOTS.items():
        asset_id = getattr(form, slot)
        if asset_id is None:
            continue
        asset = await session.get(Asset, asset_id)
        if asset is None or not asset.is_image:
            errors[slot] = f"Choose an image for the {label}."
        elif not asset.alt_text:
            errors[slot] = (
                f"Add alt text to {asset.filename} in Assets before using it as the {label}."
            )
    return errors


@router.get("")
async def settings_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    return await _render(request, session, user, await get_site_settings(session))


@router.post("")
async def save(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    data = _form_data(await request.form())
    site = await get_site_settings(session)
    try:
        form = SettingsForm.model_validate(data)
    except ValidationError as exc:
        return await _render(request, session, user, site, field_errors(exc, MESSAGES), 422, data)
    if errors := await _slot_errors(session, form):
        return await _render(request, session, user, site, errors, 422, data)
    if await session.get(SiteSettings, 1) is None:
        session.add(site)
    for field, value in form.model_dump().items():
        setattr(site, field, value)
    await session.commit()
    session.expunge(site)  # reload the slot relationships on the next read
    response = await _render(request, session, user, await get_site_settings(session))
    return hx_toast(response, "Settings saved")
