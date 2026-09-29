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
