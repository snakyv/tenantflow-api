from typing import cast
from uuid import uuid4

import httpx
import pytest

from app.main import app

pytestmark = pytest.mark.integration


async def _register_and_login(client: httpx.AsyncClient, suffix: str) -> str:
    email = f"user-{suffix}@example.com"
    password = "LongEnoughPassword!123"
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Integration User"},
    )
    assert register.status_code == 201, register.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return cast(str, login.json()["access_token"])


@pytest.mark.asyncio
async def test_auth_organization_project_and_cross_tenant_isolation() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        suffix_a = uuid4().hex[:10]
        suffix_b = uuid4().hex[:10]
        token_a = await _register_and_login(client, suffix_a)
        token_b = await _register_and_login(client, suffix_b)

        headers_a = {"Authorization": f"Bearer {token_a}", "Idempotency-Key": f"org-a-{suffix_a}"}
        org_a = await client.post(
            "/api/v1/organizations",
            headers=headers_a,
            json={"name": "Org A", "slug": f"org-a-{suffix_a}"},
        )
        assert org_a.status_code == 201, org_a.text
        org_a_id = org_a.json()["id"]

        replay = await client.post(
            "/api/v1/organizations",
            headers=headers_a,
            json={"name": "Org A", "slug": f"org-a-{suffix_a}"},
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == org_a_id

        create_project = await client.post(
            f"/api/v1/organizations/{org_a_id}/projects",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"name": "Private Project", "description": "tenant A"},
        )
        assert create_project.status_code == 201, create_project.text
        project_id = create_project.json()["id"]

        headers_b = {"Authorization": f"Bearer {token_b}", "Idempotency-Key": f"org-b-{suffix_b}"}
        org_b = await client.post(
            "/api/v1/organizations",
            headers=headers_b,
            json={"name": "Org B", "slug": f"org-b-{suffix_b}"},
        )
        assert org_b.status_code == 201

        forbidden = await client.get(
            f"/api/v1/organizations/{org_a_id}/projects/{project_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert forbidden.status_code == 404
        assert forbidden.json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"
