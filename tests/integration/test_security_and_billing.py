from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import token_fingerprint
from app.db.models import (
    Invitation,
    OrganizationMembership,
    Task,
    User,
)
from app.db.session import get_session_factory
from app.main import app
from app.modules.billing.service import process_stripe_event

pytestmark = pytest.mark.integration


async def _register(client: httpx.AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "LongEnoughPassword!123",
            "full_name": "Integration User",
        },
    )
    assert response.status_code == 201, response.text


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "LongEnoughPassword!123"},
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, str], response.json())


async def _create_org(client: httpx.AsyncClient, token: str, suffix: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/organizations",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"org-{suffix}",
        },
        json={"name": f"Org {suffix}", "slug": f"org-{suffix}"},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, str], response.json())


@pytest.mark.asyncio
async def test_refresh_token_rotates_and_old_token_is_rejected() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid4().hex[:10]
        email = f"refresh-{suffix}@example.com"
        await _register(client, email)
        first = await _login(client, email)

        rotated = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": first["refresh_token"]},
        )
        assert rotated.status_code == 200, rotated.text
        second = rotated.json()
        assert second["refresh_token"] != first["refresh_token"]

        replay = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": first["refresh_token"]},
        )
        assert replay.status_code == 401


@pytest.mark.asyncio
async def test_viewer_can_read_but_cannot_create_project() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid4().hex[:10]
        owner_email = f"owner-{suffix}@example.com"
        viewer_email = f"viewer-{suffix}@example.com"
        await _register(client, owner_email)
        await _register(client, viewer_email)
        owner_tokens = await _login(client, owner_email)
        viewer_tokens = await _login(client, viewer_email)
        org = await _create_org(client, owner_tokens["access_token"], suffix)
        organization_id = UUID(org["id"])

        async with get_session_factory()() as session:
            async with session.begin():
                viewer = await session.scalar(select(User).where(User.email == viewer_email))
                assert viewer is not None
                session.add(
                    OrganizationMembership(
                        organization_id=organization_id,
                        user_id=viewer.id,
                        role="viewer",
                    )
                )

        read = await client.get(
            f"/api/v1/organizations/{organization_id}/projects",
            headers={"Authorization": f"Bearer {viewer_tokens['access_token']}"},
        )
        assert read.status_code == 200, read.text
        assert read.json() == {"items": [], "next_cursor": None}

        write = await client.post(
            f"/api/v1/organizations/{organization_id}/projects",
            headers={"Authorization": f"Bearer {viewer_tokens['access_token']}"},
            json={"name": "Forbidden project"},
        )
        assert write.status_code == 403
        assert write.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_database_rejects_task_linked_to_project_from_another_tenant() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid4().hex[:8]
        email = f"fk-{suffix}@example.com"
        await _register(client, email)
        tokens = await _login(client, email)
        org_a = await _create_org(client, tokens["access_token"], f"{suffix}-a")
        org_b = await _create_org(client, tokens["access_token"], f"{suffix}-b")

        project = await client.post(
            f"/api/v1/organizations/{org_b['id']}/projects",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={"name": "Tenant B project"},
        )
        assert project.status_code == 201, project.text

        async with get_session_factory()() as session:
            user = await session.scalar(select(User).where(User.email == email))
            assert user is not None
            wrong_task = Task(
                organization_id=UUID(org_a["id"]),
                project_id=UUID(project.json()["id"]),
                title="Cross-tenant task",
                status="todo",
                priority="medium",
                created_by=user.id,
            )
            session.add(wrong_task)
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()


@pytest.mark.asyncio
async def test_invitation_acceptance_binds_token_to_email() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid4().hex[:10]
        owner_email = f"invite-owner-{suffix}@example.com"
        member_email = f"invite-member-{suffix}@example.com"
        await _register(client, owner_email)
        await _register(client, member_email)
        owner_tokens = await _login(client, owner_email)
        member_tokens = await _login(client, member_email)
        org = await _create_org(client, owner_tokens["access_token"], suffix)
        raw_token = f"test-invitation-{uuid4().hex}"

        async with get_session_factory()() as session:
            async with session.begin():
                owner = await session.scalar(select(User).where(User.email == owner_email))
                assert owner is not None
                session.add(
                    Invitation(
                        organization_id=UUID(org["id"]),
                        email=member_email,
                        role="member",
                        token_hash=token_fingerprint(raw_token),
                        status="pending",
                        invited_by=owner.id,
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                    )
                )

        accepted = await client.post(
            "/api/v1/organizations/invitations/accept",
            headers={"Authorization": f"Bearer {member_tokens['access_token']}"},
            json={"token": raw_token},
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["role"] == "member"
        assert accepted.json()["email"] == member_email


@pytest.mark.asyncio
async def test_stripe_event_deduplication_is_database_backed() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid4().hex[:10]
        email = f"stripe-{suffix}@example.com"
        await _register(client, email)
        tokens = await _login(client, email)
        org = await _create_org(client, tokens["access_token"], suffix)
        event = {
            "id": f"evt_{uuid4().hex}",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": f"sub_{uuid4().hex}",
                    "customer": f"cus_{uuid4().hex}",
                    "status": "active",
                    "metadata": {"organization_id": org["id"]},
                    "items": {"data": []},
                }
            },
        }

        async with get_session_factory()() as session:
            async with session.begin():
                assert await process_stripe_event(session, event) is True
        async with get_session_factory()() as session:
            async with session.begin():
                assert await process_stripe_event(session, event) is False
