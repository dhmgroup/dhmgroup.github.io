import pytest
from pydantic import ValidationError

from app.auth.users import create_admin, hash_password, set_password, verify_password
from app.config import DEV_SECRET_KEY, Settings


def test_hash_and_verify():
    h = hash_password("correct horse")
    assert h.startswith("$argon2")
    assert verify_password(h, "correct horse") is True
    assert verify_password(h, "wrong") is False


async def test_create_admin_lowercases_email(session):
    user = await create_admin(session, "  Douglas@DHMGroup.net ", "pw-123456789")
    assert user.email == "douglas@dhmgroup.net"
    assert user.is_active is True
    assert verify_password(user.password_hash, "pw-123456789")


async def test_create_admin_rejects_duplicate(session):
    await create_admin(session, "a@dhmgroup.net", "pw-123456789")
    with pytest.raises(ValueError, match="already exists"):
        await create_admin(session, "A@dhmgroup.net", "pw-987654321")


async def test_create_admin_rejects_short_password(session):
    with pytest.raises(ValueError, match="at least 10"):
        await create_admin(session, "b@dhmgroup.net", "short")


async def test_set_password(session):
    user = await create_admin(session, "c@dhmgroup.net", "pw-123456789")
    assert await set_password(session, "C@dhmgroup.net", "new-password-1") is True
    await session.refresh(user)
    assert verify_password(user.password_hash, "new-password-1")
    assert await set_password(session, "nobody@dhmgroup.net", "new-password-1") is False


def test_production_requires_a_real_secret_key():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(env="production", secret_key=DEV_SECRET_KEY)
    assert Settings(env="production", secret_key="x" * 40).env == "production"


from app.auth.deps import safe_next  # noqa: E402


@pytest.mark.parametrize(
    "value",
    [None, "", "https://evil.test", "//evil.test", r"/\evil.test", "admin", "/public"],
)
def test_safe_next_rejects_everything_but_admin_paths(value):
    assert safe_next(value) == "/admin"


def test_safe_next_keeps_admin_paths():
    assert safe_next("/admin/inquiries?stage=won") == "/admin/inquiries?stage=won"


async def test_login_page_renders(client):
    r = await client.get("/admin/login")
    assert r.status_code == 200
    assert 'name="password"' in r.text


async def test_login_success_redirects_to_next(client, admin):
    r = await client.post(
        "/admin/login",
        data={
            "email": "ADMIN@dhmgroup.net",
            "password": "admin-password-1",
            "next": "/admin/inquiries",
        },
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/inquiries"
    assert "dhm_admin=" in r.headers["set-cookie"]


async def test_login_failure_is_generic(client, admin):
    for email, pw in [("admin@dhmgroup.net", "wrong-password"), ("nobody@dhmgroup.net", "x")]:
        r = await client.post("/admin/login", data={"email": email, "password": pw})
        assert r.status_code == 401
        assert "Email or password is incorrect." in r.text


async def test_login_rate_limited(client, admin):
    for _ in range(5):
        await client.post(
            "/admin/login", data={"email": "admin@dhmgroup.net", "password": "nope-nope"}
        )
    r = await client.post(
        "/admin/login", data={"email": "admin@dhmgroup.net", "password": "admin-password-1"}
    )
    assert r.status_code == 429


async def test_inactive_user_cannot_log_in(client, admin, session):
    admin.is_active = False
    await session.commit()
    r = await client.post(
        "/admin/login", data={"email": "admin@dhmgroup.net", "password": "admin-password-1"}
    )
    assert r.status_code == 401


@pytest.mark.xfail(reason="admin routes land in Tasks 4-5", strict=True)
async def test_admin_requires_login(client):
    r = await client.get("/admin")
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login?next=/admin"


@pytest.mark.xfail(reason="admin routes land in Tasks 4-5", strict=True)
async def test_htmx_request_without_session_gets_hx_redirect(client):
    r = await client.get("/admin/inquiries?stage=new", headers={"HX-Request": "true"})
    assert r.status_code == 204
    assert r.headers["HX-Redirect"].startswith("/admin/login?next=")


async def test_csrf_required_on_admin_posts(admin_client):
    admin_client.headers.pop("X-CSRF-Token")
    r = await admin_client.post("/admin/logout")
    assert r.status_code == 403


async def test_logout_with_csrf_redirects(admin_client):
    r = await admin_client.post("/admin/logout")
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"


@pytest.mark.xfail(reason="admin routes land in Tasks 4-5", strict=True)
async def test_logout_clears_session(admin_client):
    await admin_client.post("/admin/logout")
    assert (await admin_client.get("/admin")).status_code == 303
