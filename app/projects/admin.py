from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.context import admin_context
from app.admin.forms import OptionalHttps, Stripped, field_errors, hx_toast
from app.auth.deps import require_admin, verify_csrf
from app.auth.models import User
from app.db import get_session
from app.htmx import is_htmx
from app.projects.models import Project, ProjectStatus
from app.templating import templates

router = APIRouter(
    prefix="/admin/projects", dependencies=[Depends(require_admin), Depends(verify_csrf)]
)
MESSAGES = {
    "name": "Give the project a name (up to 100 characters).",
    "summary": "Add a one-line summary (up to 300 characters).",
}
STATUS_LABELS = {"live": "Live", "coming_soon": "Coming soon", "retired": "Retired"}


class ProjectForm(BaseModel):
    name: Stripped = Field(min_length=1, max_length=100)
    summary: Stripped = Field(min_length=1, max_length=300)
    url: OptionalHttps = None
    ios_url: OptionalHttps = None
    android_url: OptionalHttps = None
    status: Literal["live", "coming_soon", "retired"] = "live"
    is_published: bool = False


async def _projects(session: AsyncSession):
    stmt = select(Project).order_by(Project.sort_order, Project.id)
    return (await session.scalars(stmt)).all()


async def _get(session: AsyncSession, project_id: int) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404)
    return project


def _blank() -> Project:
    return Project(name="", summary="", status=ProjectStatus.LIVE, is_published=True)


def _list_context(request, projects, project) -> dict:
    return {
        "projects": projects,
        "project": project,
        "status_labels": STATUS_LABELS,
        "csrf_token": request.session["csrf"],
    }


async def _render(
    request, session, user, project, values=None, errors=None, status_code=200, toast=""
):
    """The editor panel for htmx requests, the full list + editor page otherwise."""
    context = {
        **_list_context(request, await _projects(session), project),
        "values": values or {},
        "errors": errors or {},
    }
    if is_htmx(request):
        response = templates.TemplateResponse(
            request, "admin/_project_editor.html", context, status_code=status_code
        )
    else:
        full = await admin_context(request, session, user, "projects", "Projects", **context)
        response = templates.TemplateResponse(
            request, "admin/projects.html", full, status_code=status_code
        )
    return hx_toast(response, toast, **{"projects-changed": True}) if toast else response


async def _save(request, session, user, project: Project | None):
    data = dict(await request.form())
    try:
        form = ProjectForm.model_validate(data)
    except ValidationError as exc:
        shown = project or _blank()
        return await _render(request, session, user, shown, data, field_errors(exc, MESSAGES), 422)
    target = project or Project()
    for field, value in form.model_dump().items():
        setattr(target, field, value)
    if project is None:
        next_order = await session.scalar(select(func.coalesce(func.max(Project.sort_order), -1)))
        target.sort_order = next_order + 1
        session.add(target)
    await session.commit()
    if not is_htmx(request):
        return RedirectResponse(f"/admin/projects/{target.id}", status_code=303)
    toast = "Project saved" if project else "Project created"
    return await _render(request, session, user, target, toast=toast)


@router.get("")
async def project_list(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    if is_htmx(request):
        context = _list_context(request, await _projects(session), None)
        return templates.TemplateResponse(request, "admin/_project_list.html", context)
    return await _render(request, session, user, None)


@router.get("/new")
async def new_project(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    return await _render(request, session, user, _blank())


@router.post("")
async def create(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    return await _save(request, session, user, None)


@router.get("/{project_id}")
async def edit(
    request: Request,
    project_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    return await _render(request, session, user, await _get(session, project_id))


@router.post("/{project_id}")
async def update(
    request: Request,
    project_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    return await _save(request, session, user, await _get(session, project_id))


@router.post("/{project_id}/move")
async def move(request: Request, project_id: int, session: AsyncSession = Depends(get_session)):
    direction = str((await request.form()).get("direction") or "")
    if direction not in ("up", "down"):
        raise HTTPException(status_code=422, detail="direction must be up or down")
    projects = list(await _projects(session))
    index = next((i for i, p in enumerate(projects) if p.id == project_id), None)
    if index is None:
        raise HTTPException(status_code=404)
    other = index - 1 if direction == "up" else index + 1
    if 0 <= other < len(projects):
        projects[index], projects[other] = projects[other], projects[index]
    for position, project in enumerate(projects):  # renumber so gaps and ties never stick
        project.sort_order = position
    await session.commit()
    if not is_htmx(request):
        return RedirectResponse("/admin/projects", status_code=303)
    context = _list_context(request, await _projects(session), None)
    return templates.TemplateResponse(request, "admin/_project_list.html", context)


@router.post("/{project_id}/delete")
async def delete(
    request: Request,
    project_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
):
    await session.delete(await _get(session, project_id))
    await session.commit()
    if not is_htmx(request):
        return RedirectResponse("/admin/projects", status_code=303)
    return await _render(request, session, user, None, toast="Project deleted")
