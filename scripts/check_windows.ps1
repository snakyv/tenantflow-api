$ErrorActionPreference = "Stop"

Write-Host "TenantFlow environment audit" -ForegroundColor Cyan

$pythonVersion = py -3.12 -c "import sys; print(sys.version.split()[0])"
if (-not $pythonVersion.StartsWith("3.12.")) {
    throw "Python 3.12 is required. Detected: $pythonVersion"
}
Write-Host "Python $pythonVersion" -ForegroundColor Green

git --version
docker --version
docker compose version

docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop engine is not reachable." }
Write-Host "Docker Desktop engine is reachable" -ForegroundColor Green

# TenantFlow deliberately uses 55432 on the Windows host so an existing local
# PostgreSQL installation can continue using the conventional 5432 port.
$ports = 55432, 6379, 8000, 9000, 9001, 1025, 8025, 9090, 16686, 4317, 4318
foreach ($port in $ports) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        Write-Warning "TenantFlow port $port is already in use. PID(s): $($listener.OwningProcess -join ', ')"
    } else {
        Write-Host "Port $port is available"
    }
}

$standardPostgres = Get-NetTCPConnection -LocalPort 5432 -State Listen -ErrorAction SilentlyContinue
if ($standardPostgres) {
    Write-Host "Info: port 5432 is already in use, but TenantFlow uses host port 55432, so this is not a conflict." -ForegroundColor DarkGray
}

Write-Host "Recommended PyCharm interpreter: .venv\Scripts\python.exe" -ForegroundColor Green
Write-Host "PostgreSQL, Redis, MinIO and Mailpit are expected to run through Docker Desktop." -ForegroundColor Green
