$ErrorActionPreference = "Stop"

Write-Host "== TenantFlow local quality gate ==" -ForegroundColor Cyan

python --version
ruff check .
mypy app tests
pytest -m "not integration"
pip-audit
python -m compileall -q app alembic scripts tests

Write-Host "Local non-integration quality gate passed." -ForegroundColor Green
