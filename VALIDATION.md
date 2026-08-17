# Validation record

This document records checks that have actually been executed. It separates local target-environment validation, external integration validation, and public GitHub repository checks.

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

The latest full release gate completed successfully and verified:

- Docker Desktop engine reachable.
- PostgreSQL, Redis, MinIO and Mailpit containers healthy.
- Alembic connected to PostgreSQL and the full migration chain applied.
- MinIO bucket initialization succeeded.
- `ruff check .` passed.
- `mypy app tests` passed with **92 source files** checked.
- Full unit, security, integration and E2E suite: **61 passed**.
- Application coverage: **64.37%**, above the configured **60%** floor.
- `pip-audit`: **no known vulnerabilities found** in auditable dependencies. The local `tenantflow-api` package itself is not published on PyPI and is therefore reported as non-auditable by package name.
- Docker image build succeeded as `tenantflow-api:local`.
- Docker build continued to use the validated Python 3.12 runtime.

The final release script reported:

```text
All target-environment release checks passed.
```

### Current validation summary

```text
Python: 3.12.0
Tests: 61 passed
Coverage: 64.37%
mypy: 92 source files
Ruff: passed
pip-audit: no known vulnerabilities
Docker build: passed
Stripe Sandbox E2E: passed
```

## Stripe Sandbox end-to-end validation

A real Stripe Sandbox subscription flow was executed against the local TenantFlow API.

The validation covered the complete billing path:

1. A test user was registered through the TenantFlow API.
2. The user authenticated and received an access token.
3. A new organization was created.
4. The organization started with:

```text
plan: free
status: inactive
```

5. TenantFlow created a real Stripe Sandbox Checkout Session for the `pro` plan.
6. Stripe-hosted Checkout was completed using Stripe test-mode payment data.
7. Stripe emitted the expected subscription events.
8. Stripe CLI forwarded signed webhook requests to:

```text
POST /api/v1/webhooks/stripe
```

9. TenantFlow successfully verified and processed the Stripe webhook events.
10. Both observed webhook deliveries returned:

```text
204 No Content
```

11. The organization subscription was synchronized to:

```text
plan: pro
status: active
```

This confirms that the validated flow crossed the actual external integration boundary:

```text
TenantFlow API
    -> Stripe Sandbox API
    -> Stripe Checkout
    -> Stripe subscription
    -> signed Stripe webhook
    -> TenantFlow webhook handler
    -> PostgreSQL subscription state
```

No live Stripe mode or real payment card data was used.

During the first live Sandbox webhook validation, the test exposed a compatibility issue with Stripe Python SDK v15 event objects. The webhook boundary was corrected to convert Stripe SDK objects using their supported dictionary conversion before application-level processing.

A regression test was added for the corrected Stripe event conversion behavior.

The complete Stripe Sandbox Checkout flow was then repeated successfully.

## Dependency validation

Following automated dependency updates, the local development environment was synchronized with the repository dependencies.

SQLAlchemy was updated from:

```text
2.0.51
```

to:

```text
2.0.52
```

The installed version was explicitly verified:

```text
2.0.52
```

The complete local release validation was rerun after this update and remained green.

The Docker runtime remains intentionally based on:

```text
python:3.12-slim
```

An automated Dependabot proposal to move the Docker runtime directly from Python 3.12 to Python 3.14 was not accepted as an ordinary dependency update. Runtime-version migration requires separate compatibility validation.

## Public GitHub validation

The repository has been pushed publicly to GitHub and the repository-level automation has been exercised.

Confirmed public checks include:

- GitHub Actions CI successfully executed on `main`.
- The required `quality-and-tests` status check passed.
- CodeQL Python analysis successfully executed.
- GitHub code scanning completed without blocking alerts for the validated changes.
- Dependabot successfully detected dependencies and created automated pull requests.
- Dependabot updates for SQLAlchemy and the GitHub CodeQL Action were validated through pull requests and merged into `main`.
- The protected `main` branch is configured to require repository checks before merging.
- Pull-request-based changes are required for protected updates to `main`.
- Force pushes to the protected branch are blocked.
- Branch deletion protection is enabled.
- Linear history is required.
- Required code scanning results are enforced for CodeQL.

The current `main` branch contains the validated Stripe SDK compatibility fix and the accepted dependency updates.

## Known non-blocking warning

The test run currently emits one Starlette/FastAPI test-client deprecation warning from a third-party compatibility layer:

```text
StarletteDeprecationWarning:
Using `httpx` with `starlette.testclient` is deprecated;
install `httpx2` instead.
```

The warning does not cause a test failure and is not hidden or suppressed.

It should be revisited when the project next updates the FastAPI, Starlette, and HTTPX testing stack.

## Deployment status

No paid cloud infrastructure has been provisioned.

A public production deployment remains intentionally deferred until a provider is selected and the following production services are configured explicitly:

- managed PostgreSQL;
- managed Redis;
- S3-compatible object storage;
- production secrets;
- TLS and public domain configuration;
- production Stripe configuration, if live billing is ever enabled;
- observability/export infrastructure.

The absence of a paid public deployment does not affect the local, Docker, CI, CodeQL, or Stripe Sandbox validation recorded above.

## Release readiness

The technical validation gates required before the first stable release have now been completed:

- Python 3.12 target environment validated.
- Ruff passed.
- mypy passed.
- 61 tests passed.
- 64.37% coverage exceeded the configured 60% threshold.
- No known vulnerabilities were reported by `pip-audit` for auditable dependencies.
- PostgreSQL integration passed.
- Redis integration passed.
- MinIO integration passed.
- Mailpit integration passed.
- Alembic migration validation passed.
- Docker image build passed.
- Stripe Sandbox end-to-end billing flow passed.
- GitHub Actions CI passed.
- CodeQL analysis passed.
- Dependabot operation was confirmed.
- Protected-branch rules are enabled for `main`.

Before tagging `v1.0.0`, the project version, changelog, and public documentation should be updated to match this final validated state.

No validation result in this document should be interpreted as evidence of a production cloud deployment unless such a deployment is separately performed and recorded.
