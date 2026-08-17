$ErrorActionPreference = "Stop"

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE. Fix this error before continuing."
    }
}

& .\scripts\check_windows.ps1

if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
    Assert-NativeSuccess "Creating Python 3.12 virtual environment"
}
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
Assert-NativeSuccess "Upgrading pip"
pip install -e ".[dev]"
Assert-NativeSuccess "Installing TenantFlow dependencies"

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    $jwtSecret = python -c "import secrets; print(secrets.token_urlsafe(48))"
    $webhookSecret = python -c "import secrets; print(secrets.token_urlsafe(48))"
    $content = Get-Content .env -Raw
    $content = $content.Replace("replace-with-at-least-32-random-characters", $jwtSecret)
    $content = $content.Replace("replace-with-a-separate-32-character-secret", $webhookSecret)
    Set-Content .env $content -NoNewline
    Write-Host "Created .env with separate random development JWT and webhook-encryption secrets." -ForegroundColor Green
} else {
    # v0.1.1 migration: early archives used host PostgreSQL port 5432. Keep a
    # previously generated development .env usable without deleting its secrets.
    $content = Get-Content .env -Raw
    if ($content -notmatch '(?m)^POSTGRES_HOST_PORT=') {
        $content = "POSTGRES_HOST_PORT=55432`r`n" + $content
    }
    $content = $content.Replace("postgresql+asyncpg://tenantflow:tenantflow@localhost:5432/tenantflow", "postgresql+asyncpg://tenantflow:tenantflow@localhost:55432/tenantflow")
    Set-Content .env $content -NoNewline
}

docker compose -f compose.dev.yml up -d --wait postgres redis minio mailpit
Assert-NativeSuccess "Starting Docker development infrastructure"

alembic upgrade head
Assert-NativeSuccess "Applying Alembic migrations"

python scripts/init_minio.py
Assert-NativeSuccess "Initializing MinIO bucket"

Write-Host "Infrastructure and migrations are ready." -ForegroundColor Green
Write-Host "Run from PyCharm or: uvicorn app.main:app --reload" -ForegroundColor Green
