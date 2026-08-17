from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ForbiddenError, NotFoundError
from app.core.permissions import Permission, Role, assert_permission
from app.core.security import decode_access_token
from app.db.models import OrganizationMembership, User
from app.db.session import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    user_id = decode_access_token(token)
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User account is unavailable")
    return user


@dataclass(slots=True)
class OrganizationContext:
    user: User
    membership: OrganizationMembership

    @property
    def role(self) -> Role:
        return Role(self.membership.role)


async def get_organization_context(
    organization_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrganizationContext:
    membership = await session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    if membership is None:
        # Deliberately conceal tenant existence.
        raise NotFoundError("ORGANIZATION_NOT_FOUND", "Organization was not found")
    return OrganizationContext(user=user, membership=membership)


def require_permission(
    permission: Permission,
) -> Callable[..., Awaitable[OrganizationContext]]:
    async def dependency(
        context: OrganizationContext = Depends(get_organization_context),
    ) -> OrganizationContext:
        try:
            assert_permission(context.role, permission)
        except ForbiddenError:
            raise
        return context

    return dependency
