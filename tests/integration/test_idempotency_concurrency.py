import asyncio
from uuid import uuid4

import httpx
import pytest

from app.main import app

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_parallel_duplicate_organization_request_creates_one_resource() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid4().hex[:10]
        email = f"idempotency-{suffix}@example.com"
        password = "LongEnoughPassword!123"
        assert (
            await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": password, "full_name": "Idempotency User"},
            )
        ).status_code == 201
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        token = login.json()["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"parallel-{suffix}",
        }
        payload = {"name": "Concurrent Org", "slug": f"concurrent-{suffix}"}

        first, second = await asyncio.gather(
            client.post("/api/v1/organizations", headers=headers, json=payload),
            client.post("/api/v1/organizations", headers=headers, json=payload),
        )
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_idempotency_key_cannot_be_reused_for_different_payload() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid4().hex[:10]
        email = f"idempotency-conflict-{suffix}@example.com"
        password = "LongEnoughPassword!123"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Idempotency Conflict"},
        )
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        token = login.json()["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"conflict-{suffix}",
        }
        first = await client.post(
            "/api/v1/organizations",
            headers=headers,
            json={"name": "First Org", "slug": f"first-{suffix}"},
        )
        assert first.status_code == 201
        second = await client.post(
            "/api/v1/organizations",
            headers=headers,
            json={"name": "Different Org", "slug": f"different-{suffix}"},
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.asyncio
async def test_invitation_creation_replays_without_creating_a_second_invitation() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid4().hex[:10]
        email = f"invite-idempotency-{suffix}@example.com"
        password = "LongEnoughPassword!123"
        await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "Invite Owner"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        token = login.json()["access_token"]
        organization = await client.post(
            "/api/v1/organizations",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": f"invite-org-{suffix}",
            },
            json={"name": "Invite Org", "slug": f"invite-org-{suffix}"},
        )
        assert organization.status_code == 201, organization.text
        organization_id = organization.json()["id"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": f"invite-create-{suffix}",
        }
        payload = {"email": f"member-{suffix}@example.com", "role": "member"}

        first = await client.post(
            f"/api/v1/organizations/{organization_id}/invitations",
            headers=headers,
            json=payload,
        )
        second = await client.post(
            f"/api/v1/organizations/{organization_id}/invitations",
            headers=headers,
            json=payload,
        )

        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert first.json()["id"] == second.json()["id"]

        conflict = await client.post(
            f"/api/v1/organizations/{organization_id}/invitations",
            headers=headers,
            json={"email": payload["email"], "role": "viewer"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
