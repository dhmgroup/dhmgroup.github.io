import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.context import admin_context
from app.admin.forms import hx_toast
from app.assets import storage
from app.assets.detect import detect
from app.assets.models import Asset
from app.auth.deps import require_admin, verify_csrf
from app.auth.models import User
from app.db import get_session
from app.htmx import is_htmx
from app.templating import templates

router = APIRouter(
    prefix="/admin/assets", dependencies=[Depends(require_admin), Depends(verify_csrf)]
)
MAX_BYTES = 10 * 1024 * 1024


async def asset_references(session: AsyncSession, asset_id: int) -> list[str]:
    """Where an asset is used, as labels for the admin."""
    from app.site.models import SLOTS, SiteSettings  # site imports assets: avoid an import cycle

    site = await session.get(SiteSettings, 1)
    if site is None:
        return []
    return [
        f"Used as the {label}" for slot, label in SLOTS.items() if getattr(site, slot) == asset_id
    ]


async def _assets(session: AsyncSession):
    stmt = select(Asset).order_by(Asset.created_at.desc(), Asset.id.desc())
    return (await session.scalars(stmt)).all()


async def _grid(request: Request, session: AsyncSession, status_code: int = 200, error: str = ""):
    context = {
        "assets": await _assets(session),
        "csrf_token": request.session["csrf"],
        "error": error,
    }
    return templates.TemplateResponse(
        request, "admin/_asset_grid.html", context, status_code=status_code
    )


async def _get(session: AsyncSession, asset_id: int) -> Asset:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404)
    return asset


@router.get("")
async def library(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    if is_htmx(request):
        return await _grid(request, session)
    context = await admin_context(
        request, session, user, "assets", "Assets", assets=await _assets(session), error=""
    )
    return templates.TemplateResponse(request, "admin/assets.html", context)


@router.post("")
async def upload(
    request: Request,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        return await _grid(request, session, 413, "That file is over 10 MB.")
    detected = detect(data[:512])
    if detected is None:
        return await _grid(
            request, session, 415, "Upload a PNG, JPEG, WebP, AVIF, SVG, ICO or PDF file."
        )
    ext, content_type = detected
    key = f"uploads/{uuid.uuid4()}{ext}"
    await storage.put(key, data, content_type)
    form = await request.form()
    asset = Asset(
        key=key,
        filename=(file.filename or "upload")[:255],
        content_type=content_type,
        size_bytes=len(data),
        alt_text=str(form.get("alt_text") or "").strip()[:300],
        uploaded_by=user.id,
    )
    session.add(asset)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        await storage.delete(key)  # never leave an orphan object behind
        raise
    return hx_toast(await _grid(request, session), "Uploaded")


@router.post("/{asset_id}/alt")
async def set_alt(request: Request, asset_id: int, session: AsyncSession = Depends(get_session)):
    asset = await _get(session, asset_id)
    asset.alt_text = str((await request.form()).get("alt_text") or "").strip()[:300]
    await session.commit()
    return hx_toast(await _grid(request, session), "Alt text saved")


@router.post("/{asset_id}/delete")
async def delete(request: Request, asset_id: int, session: AsyncSession = Depends(get_session)):
    asset = await _get(session, asset_id)
    if refs := await asset_references(session, asset_id):
        message = f"{asset.filename} can't be deleted. {'; '.join(refs)}."
        return await _grid(request, session, 409, message)
    key = asset.key
    await session.delete(asset)
    await session.commit()
    await storage.delete(key)  # after the commit: a failure here leaves only a harmless orphan
    return hx_toast(await _grid(request, session), "Deleted")
