# Contributing

1. Create a feature branch from `main`.
2. Create and activate a Python 3.12 virtual environment.
3. Install the project with `pip install -e ".[dev]"`.
4. Start development infrastructure with `docker compose -f compose.dev.yml up -d --wait`.
5. Apply migrations with `alembic upgrade head`.
6. Keep changes focused and add tests for behavior, especially authorization, tenant isolation and transaction boundaries.
7. Run `ruff check .`, `mypy app tests`, and `pytest -m "not integration"` during development.
8. Before opening a pull request, run the full target-environment gate when Docker is available: `./scripts/validate_release.ps1` on Windows, or the equivalent CI commands documented in the README.

Database changes must include an Alembic migration. Generated migrations must be reviewed rather than committed blindly. Never commit `.env`, credentials, access tokens, production payloads, generated coverage output, IDE metadata or local virtual environments.
