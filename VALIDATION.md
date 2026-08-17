# Validation record

This document records checks that have actually been executed. It intentionally separates local target-environment validation from checks that can only be confirmed after the repository is pushed to GitHub.

## Target environment

Latest full local release gate: **2026-08-17**

- Windows 11
- Python 3.12.0
- Docker Desktop 29.5.2
- Docker Compose v5.1.3
- PostgreSQL 18.6
- Redis 8.10.0
- MinIO `RELEASE.2025-09-07T16-13-09Z`
- Mailpit 1.30.7

## Full local release validation

Executed from the repository root with:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\bootstrap_windows.ps1
.\scripts\validate_release.ps1
```

The release gate completed successfully and verified:

- Docker Desktop engine reachable.
- PostgreSQL, Redis, MinIO and Mailpit containers healthy.
- Alembic connected to PostgreSQL and the full migration chain applied.
- MinIO bucket initialization succeeded.
- `ruff check .` passed.
- `mypy app tests` passed with **91 source files** checked.
- Full unit, security, integration and E2E suite: **60 passed**.
- Application coverage: **64.12%**, above the configured **60%** floor.
- `pip-audit`: **no known vulnerabilities found** in auditable dependencies. The local package itself is not published on PyPI and is therefore reported as non-auditable by name.
- Docker image build succeeded as `tenantflow-api:local`.

The final release script reported:

```text
All target-environment release checks passed.
```

## Known non-blocking warning

The test run currently emits one Starlette/FastAPI test-client deprecation warning from a third-party compatibility layer. It does not cause a test failure and is not hidden or suppressed. It should be revisited when the project next updates the FastAPI/Starlette/HTTPX test stack.

## GitHub checks still pending

The following cannot be claimed as passed until the first public push is complete:

- GitHub Actions CI on `main`.
- CodeQL analysis.
- Dependabot operation in the public repository.

No green CI badge should be added until the corresponding public workflow run is genuinely green.

## Deployment status

No paid cloud infrastructure has been provisioned. A public deployment remains intentionally deferred until a provider is selected and managed PostgreSQL, Redis, object storage and secrets are configured explicitly.

## Release policy

Do not tag `v1.0.0` until the public GitHub Actions and CodeQL workflows are green and the README still matches the repository's actual setup.
