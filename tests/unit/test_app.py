from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


def test_liveness_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_openapi_contains_tenant_routes() -> None:
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    assert "/api/v1/organizations/{organization_id}/projects" in schema["paths"]
    assert "/api/v1/organizations/{organization_id}/tasks" in schema["paths"]
    assert "/api/v1/webhooks/stripe" in schema["paths"]


def test_liveness_includes_security_headers() -> None:
    response = TestClient(app).get("/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_invalid_request_id_is_replaced() -> None:
    response = TestClient(app).get("/health/live", headers={"X-Request-ID": "bad id with spaces"})
    assert response.headers["X-Request-ID"] != "bad id with spaces"
    assert len(response.headers["X-Request-ID"]) == 36


def test_validation_errors_use_unified_error_shape() -> None:
    async def fake_session() -> AsyncIterator[object]:
        yield object()

    app.dependency_overrides[get_session] = fake_session
    try:
        response = TestClient(app).post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "short", "full_name": ""},
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["request_id"]
    assert body["error"]["details"]
