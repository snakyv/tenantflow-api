$ErrorActionPreference = "Stop"

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

Write-Host "== TenantFlow target-environment release validation ==" -ForegroundColor Cyan

& .\scripts\check_windows.ps1

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Missing .venv. Run .\scripts\bootstrap_windows.ps1 first."
}

. .\.venv\Scripts\Activate.ps1

python -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version"
Assert-NativeSuccess "Verifying Python 3.12"

docker compose -f compose.dev.yml up -d --wait postgres redis minio mailpit
Assert-NativeSuccess "Starting Docker integration infrastructure"

alembic upgrade head
Assert-NativeSuccess "Applying Alembic migrations"

python scripts/init_minio.py
Assert-NativeSuccess "Initializing MinIO bucket"

$previousIntegration = $env:RUN_INTEGRATION
$previousAppEnv = $env:APP_ENV
$env:RUN_INTEGRATION = "1"
$env:APP_ENV = "test"

try {
    ruff check .
    Assert-NativeSuccess "Ruff"
    mypy app tests
    Assert-NativeSuccess "mypy"
    pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=60
    Assert-NativeSuccess "pytest integration suite"
    pip-audit
    Assert-NativeSuccess "pip-audit"
    docker build -t tenantflow-api:local .
    Assert-NativeSuccess "Docker image build"

    Write-Host "All target-environment release checks passed." -ForegroundColor Green
    Write-Host "Next: push to GitHub and confirm CI + CodeQL are green before tagging v1.0.0." -ForegroundColor Green
}
finally {
    if ($null -eq $previousIntegration) {
        Remove-Item Env:RUN_INTEGRATION -ErrorAction SilentlyContinue
    } else {
        $env:RUN_INTEGRATION = $previousIntegration
    }
    if ($null -eq $previousAppEnv) {
        Remove-Item Env:APP_ENV -ErrorAction SilentlyContinue
    } else {
        $env:APP_ENV = $previousAppEnv
    }
}
