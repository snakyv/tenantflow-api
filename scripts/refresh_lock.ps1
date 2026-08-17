$ErrorActionPreference = "Stop"

Write-Host "== Refreshing the reproducible uv lockfile ==" -ForegroundColor Cyan

$pythonVersion = py -3.12 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
if ($pythonVersion -ne "3.12") {
    throw "Python 3.12 is required. Detected $pythonVersion."
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "uv was not found. Installing uv 0.12.5 into Python 3.12..." -ForegroundColor Yellow
    py -3.12 -m pip install "uv==0.12.5"
}

uv lock --python 3.12
uv sync --extra dev --python 3.12

Write-Host "uv.lock refreshed. Review and commit it together with dependency changes." -ForegroundColor Green
