from enum import StrEnum

from app.core.exceptions import ForbiddenError


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Permission(StrEnum):
    ORG_MANAGE = "org:manage"
    MEMBERS_MANAGE = "members:manage"
    BILLING_MANAGE = "billing:manage"
    PROJECT_READ = "project:read"
    PROJECT_WRITE = "project:write"
    PROJECT_DELETE = "project:delete"
    WEBHOOK_MANAGE = "webhook:manage"
    AUDIT_READ = "audit:read"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset(
        {
            Permission.MEMBERS_MANAGE,
            Permission.PROJECT_READ,
            Permission.PROJECT_WRITE,
            Permission.PROJECT_DELETE,
            Permission.WEBHOOK_MANAGE,
            Permission.AUDIT_READ,
        }
    ),
    Role.MEMBER: frozenset({Permission.PROJECT_READ, Permission.PROJECT_WRITE}),
    Role.VIEWER: frozenset({Permission.PROJECT_READ}),
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]


def assert_permission(role: Role, permission: Permission) -> None:
    if not has_permission(role, permission):
        raise ForbiddenError(message=f"Role '{role}' lacks permission '{permission}'")
