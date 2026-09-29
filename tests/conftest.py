import asyncio
import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://dhm:dhm@localhost:5433/dhm_test"
)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, get_session  # noqa: E402
from app.main import app  # noqa: E402

DB_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session", autouse=True)
def _schema():
    async def reset():
        eng = create_async_engine(DB_URL, poolclass=NullPool)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await eng.dispose()

    asyncio.run(reset())


@pytest.fixture
async def session():
    """A session inside a transaction that is rolled back after the test."""
    eng = create_async_engine(DB_URL, poolclass=NullPool)
    async with eng.connect() as conn:
        trans = await conn.begin()
        s = AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        yield s
        await s.close()
        await trans.rollback()
    await eng.dispose()


@pytest.fixture
async def client(session):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
