from uuid import uuid4

import httpx
import pytest

from app.main import app

pytestmark = [pytest.mark.integration, pytest.mark.e2e]


@pytest.mark.asyncio
async def test_owner_can_complete_core_tenant_workflow() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        suffix = uuid4().hex[:10]
        email = f"e2e-{suffix}@example.com"
        password = "LongEnoughPassword!123"

        registered = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "full_name": "E2E Owner"},
        )
        assert registered.status_code == 201, registered.text

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        organization = await client.post(
            "/api/v1/organizations",
            headers={**auth, "Idempotency-Key": f"e2e-org-{suffix}"},
            json={"name": "E2E Workspace", "slug": f"e2e-{suffix}"},
        )
        assert organization.status_code == 201, organization.text
        organization_id = organization.json()["id"]

        project = await client.post(
            f"/api/v1/organizations/{organization_id}/projects",
            headers=auth,
            json={"name": "Launch API", "description": "Portfolio workflow"},
        )
        assert project.status_code == 201, project.text
        project_id = project.json()["id"]

        task = await client.post(
            f"/api/v1/organizations/{organization_id}/tasks",
            headers=auth,
            json={
                "project_id": project_id,
                "title": "Ship tenant-safe backend",
                "priority": "high",
            },
        )
        assert task.status_code == 201, task.text
        task_id = task.json()["id"]

        completed = await client.patch(
            f"/api/v1/organizations/{organization_id}/tasks/{task_id}",
            headers=auth,
            json={"status": "done"},
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "done"

        tasks = await client.get(
            f"/api/v1/organizations/{organization_id}/tasks",
            params={"project_id": project_id, "status": "done"},
            headers=auth,
        )
        assert tasks.status_code == 200, tasks.text
        assert [item["id"] for item in tasks.json()["items"]] == [task_id]

        audit = await client.get(
            f"/api/v1/organizations/{organization_id}/audit",
            headers=auth,
        )
        assert audit.status_code == 200, audit.text
        actions = {entry["action"] for entry in audit.json()}
        assert {"organization.created", "project.created", "task.created", "task.updated"} <= actions
