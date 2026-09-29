from app.db import get_session
from app.main import app


async def test_healthz_ok(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_healthz_database_down(client):
    class DeadSession:
        async def execute(self, *_):
            raise OSError("connection refused")

    async def dead():
        yield DeadSession()

    app.dependency_overrides[get_session] = dead
    r = await client.get("/healthz")
    assert r.status_code == 503
    assert r.json() == {"status": "database unavailable"}
