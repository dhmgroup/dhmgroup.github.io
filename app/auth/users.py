from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User

_hasher = PasswordHasher()
MIN_PASSWORD = 10


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _clean(email: str) -> str:
    return email.strip().lower()


def _check(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"Password must be at least {MIN_PASSWORD} characters.")


async def create_admin(session: AsyncSession, email: str, password: str) -> User:
    email = _clean(email)
    _check(password)
    if await session.scalar(select(User).where(User.email == email)):
        raise ValueError(f"An admin with {email} already exists.")
    user = User(email=email, password_hash=hash_password(password))
    session.add(user)
    await session.commit()
    return user


async def set_password(session: AsyncSession, email: str, password: str) -> bool:
    _check(password)
    user = await session.scalar(select(User).where(User.email == _clean(email)))
    if user is None:
        return False
    user.password_hash = hash_password(password)
    await session.commit()
    return True
