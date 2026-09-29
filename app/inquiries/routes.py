from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.htmx import is_htmx
from app.inquiries.forms import SERVICES, QuoteForm
from app.inquiries.models import Inquiry
from app.inquiries.notify import notify_inquiry
from app.public.routes import home_context
from app.ratelimit import RateLimiter
from app.templating import templates

router = APIRouter()
quote_limiter = RateLimiter(limit=5, window=600)
TOO_MANY = "Too many requests from your connection. Please try again in a few minutes."


async def _form_response(request, session, form, errors, status_code):
    if is_htmx(request):
        context = {"form": form, "errors": errors, "done": False, "quote_services": SERVICES}
        return templates.TemplateResponse(
            request, "public/_quote_form.html", context, status_code=status_code
        )
    context = await home_context(session)
    context.update(form=form, errors=errors)
    return templates.TemplateResponse(
        request, "public/index.html", context, status_code=status_code
    )


def _done_response(request, form):
    if is_htmx(request):
        context = {"form": form, "errors": {}, "done": True, "quote_services": SERVICES}
        return templates.TemplateResponse(request, "public/_quote_form.html", context)
    return RedirectResponse("/?sent=1#quote", status_code=303)


@router.post("/inquiries")
async def submit_quote(
    request: Request, background: BackgroundTasks, session: AsyncSession = Depends(get_session)
):
    form = QuoteForm.from_form(await request.form())
    if form.website:  # honeypot filled: pretend it worked, keep nothing
        return _done_response(request, form)

    client_ip = request.client.host if request.client else "unknown"
    if not quote_limiter.hit(client_ip):
        return await _form_response(request, session, form, {"form": TOO_MANY}, 429)

    if errors := form.errors():
        return await _form_response(request, session, form, errors, 422)

    inquiry = Inquiry(
        name=form.name,
        email=form.email,
        company=form.company or None,
        services=form.services,
        message=form.message,
    )
    session.add(inquiry)
    await session.commit()
    background.add_task(notify_inquiry, inquiry.id)
    return _done_response(request, form)
