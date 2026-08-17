from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    hash_password,
    new_refresh_token,
    token_fingerprint,
    verify_password,
)
from app.db.models import RefreshToken, User
from app.modules.auth.schemas import RegisterRequest, TokenPair


async def register_user(session: AsyncSession, payload: RegisterRequest) -> User:
    existing = await session.scalar(select(User.id).where(User.email == payload.email.lower()))
    if existing is not None:
        raise ConflictError("EMAIL_ALREADY_REGISTERED", "An account already uses this email")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password")
    if not user.is_active:
        raise AuthenticationError("User account is disabled")
    return user


async def issue_token_pair(session: AsyncSession, user: User, family_id: UUID | None = None) -> TokenPair:
    settings = get_settings()
    raw_refresh = new_refresh_token()
    now = datetime.now(UTC)
    refresh = RefreshToken(
        user_id=user.id,
        token_hash=token_fingerprint(raw_refresh),
        family_id=family_id or uuid4(),
        created_at=now,
        expires_at=now + timedelta(days=settings.refresh_token_days),
    )
    session.add(refresh)
    await session.flush()
    return TokenPair(access_token=create_access_token(user.id), refresh_token=raw_refresh)


async def rotate_refresh_token(session: AsyncSession, raw_token: str) -> TokenPair:
    fingerprint = token_fingerprint(raw_token)
    token = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == fingerprint).with_for_update()
    )
    now = datetime.now(UTC)
    if token is None or token.revoked_at is not None or token.expires_at <= now:
        raise AuthenticationError("Refresh token is invalid or expired")
    user = await session.get(User, token.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User account is unavailable")
    pair = await issue_token_pair(session, user, family_id=token.family_id)
    token.revoked_at = now
    token.replaced_by_hash = token_fingerprint(pair.refresh_token)
    return pair


async def revoke_refresh_token(session: AsyncSession, raw_token: str) -> None:
    fingerprint = token_fingerprint(raw_token)
    token = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == fingerprint).with_for_update()
    )
    if token is not None and token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
