# Changelog

All notable changes to this project will be documented in this file.

The format follows Keep a Changelog principles. The project intends to use Semantic Versioning once a stable public API is released.

## [Unreleased]

- First public GitHub Actions and CodeQL runs.
- Cloud deployment remains intentionally unprovisioned until a provider is explicitly selected.

## [0.1.1] - 2026-08-17

### Fixed

- Use the published MinIO `RELEASE.2025-09-07T16-13-09Z` container image.
- Use host PostgreSQL port `55432` for local Docker Desktop development to avoid collisions with existing PostgreSQL installations on `5432`.
- Make Windows bootstrap and release-validation scripts fail immediately when native commands return non-zero exit codes.
- Wait for Docker development services before running Alembic or MinIO initialization.
- Correct Python 3.12 typing issues reported by Ruff and mypy without weakening lint rules.
- Make the pytest integration harness use `APP_ENV=test`, preventing asyncpg connections from leaking across per-test event loops on Windows.
- Make production-secret configuration tests independent from a developer's local `.env`.

### Validated

- Completed the target Windows 11 / Python 3.12 / Docker Desktop release gate.
- Verified PostgreSQL 18.6, Redis, MinIO and Mailpit container health.
- Applied the complete Alembic migration chain against PostgreSQL.
- Passed Ruff and mypy across 91 source files.
- Passed all 60 tests with 64.12% application coverage.
- Completed `pip-audit` with no known vulnerabilities in auditable dependencies.
- Built the `tenantflow-api:local` Docker image successfully.

## [0.1.0] - 2026-08-17

### Added

- FastAPI modular-monolith foundation and versioned REST API.
- Async PostgreSQL persistence with SQLAlchemy and Alembic.
- JWT authentication, rotating refresh tokens and Argon2 password hashing.
- Organization multi-tenancy and centralized RBAC.
- Projects/tasks with tenant-aware constraints, filtering and cursor pagination.
- PostgreSQL-backed request idempotency with concurrent duplicate protection.
- Redis-backed distributed token-bucket rate limiting.
- Celery background jobs and Mailpit development email delivery.
- S3-compatible attachment workflow with MinIO local infrastructure.
- HMAC-signed outbound webhooks with retries and delivery history.
- Stripe test-mode checkout/webhook synchronization and event deduplication.
- Immutable API audit trail.
- Structured request logging, Prometheus metrics and optional OpenTelemetry tracing.
- Docker Compose development/full-stack configurations.
- Unit, security and PostgreSQL/Redis integration test suites.
- GitHub Actions CI, Dependabot and CodeQL configuration.
- Architecture documentation, ADRs and a scoped threat model.
- Separate internal/public MinIO endpoints for containerized pre-signed URL flows.
- Windows bootstrap and target-environment release-validation scripts.
- Integration-test Redis isolation to keep rate-limit state deterministic.
