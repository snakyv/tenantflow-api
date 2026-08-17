import pytest

from app.core.permissions import Permission, Role, has_permission

pytestmark = pytest.mark.security


@pytest.mark.parametrize(
    ("role", "permission", "expected"),
    [
        (Role.OWNER, Permission.BILLING_MANAGE, True),
        (Role.ADMIN, Permission.BILLING_MANAGE, False),
        (Role.ADMIN, Permission.WEBHOOK_MANAGE, True),
        (Role.MEMBER, Permission.PROJECT_WRITE, True),
        (Role.MEMBER, Permission.MEMBERS_MANAGE, False),
        (Role.VIEWER, Permission.PROJECT_WRITE, False),
    ],
)
def test_permission_matrix(role: Role, permission: Permission, expected: bool) -> None:
    assert has_permission(role, permission) is expected
