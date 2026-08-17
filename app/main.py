import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.db.session import get_session_factory
from app.infra.redis import get_redis
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.billing.router import router as billing_router
from app.modules.files.router import router as files_router
from app.modules.organizations.router import router as organizations_router
from app.modules.projects.router import router as projects_router
from app.modules.tasks.router import router as tasks_router
from app.modules.webhooks.router import router as webhooks_router
from app.observability.metrics import refresh_distributed_metrics
from app.observability.middleware import MetricsMiddleware
from app.observability.tracing import configure_tracing

settings = get_settings()
configure_logging()
logger = logging.getLogger("tenantflow.api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.validate_runtime_secrets()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Production-oriented multi-tenant SaaS backend demonstrating tenant isolation, RBAC, "
        "idempotency, reliable background processing, signed webhooks, billing and observability."
    ),
    lifespan=lifespan,
    debug=settings.app_debug and not settings.is_production,
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(organizations_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")


def _error_payload(request: Request, *, code: str, message: str, details: object | None = None) -> dict[str, object]:
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        error["details"] = details
    return {"error": error}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(request, code=exc.code, message=exc.message),
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Request could not be processed"
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(request, code=f"HTTP_{exc.status_code}", message=message),
        headers=exc.headers,
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.info("database_integrity_conflict", extra={"request_id": getattr(request.state, "request_id", None)})
    return JSONResponse(
        status_code=409,
        content=_error_payload(
            request,
            code="RESOURCE_CONFLICT",
            message="The requested change conflicts with existing data",
        ),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "location": [str(part) for part in error.get("loc", ())],
            "message": str(error.get("msg", "Invalid value")),
            "type": str(error.get("type", "validation_error")),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_error_payload(
            request,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details=details,
        ),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_request_error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=_error_payload(
            request,
            code="INTERNAL_ERROR",
            message="An unexpected server error occurred",
        ),
    )


@app.get("/health/live", tags=["Health"])
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["Health"])
async def readiness() -> JSONResponse:
    checks: dict[str, str] = {}
    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        checks["postgresql"] = "ok"
    except (SQLAlchemyError, OSError):
        checks["postgresql"] = "unavailable"

    redis = None
    try:
        from redis.exceptions import RedisError

        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except (RedisError, OSError):
        checks["redis"] = "unavailable"
    finally:
        if redis is not None:
            await redis.aclose()

    ready = all(value == "ok" for value in checks.values())
    return JSONResponse(status_code=200 if ready else 503, content={"status": "ok" if ready else "degraded", "checks": checks})


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    await refresh_distributed_metrics()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


configure_tracing(app)
