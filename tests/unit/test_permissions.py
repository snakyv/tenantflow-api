import pytest

from app.core.exceptions import ForbiddenError
from app.core.permissions import Permission, Role, assert_permission, has_permission


def test_owner_has_every_permission() -> None:
    for permission in Permission:
        assert has_permission(Role.OWNER, permission)


def test_viewer_is_read_only() -> None:
    assert has_permission(Role.VIEWER, Permission.PROJECT_READ)
    assert not has_permission(Role.VIEWER, Permission.PROJECT_WRITE)
    assert not has_permission(Role.VIEWER, Permission.PROJECT_DELETE)


def test_forbidden_permission_raises_domain_error() -> None:
    with pytest.raises(ForbiddenError):
        assert_permission(Role.MEMBER, Permission.BILLING_MANAGE)
