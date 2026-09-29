from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine, get_session


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/healthz")
async def healthz(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return JSONResponse({"status": "database unavailable"}, status_code=503)
    return {"status": "ok"}
