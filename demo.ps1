$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    & .venv/Scripts/python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependencies failed' }
}
if (-not (Test-Path -LiteralPath 'frontend/dist/index.html')) {
    Push-Location frontend
    npm ci
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    Pop-Location
}
$env:FEDTRACE_DEMO = '1'
& .venv/Scripts/python -m fedtrace.cli demo
if ($LASTEXITCODE -ne 0) { throw 'Demonstration failed' }
& .venv/Scripts/python -m fedtrace.cli serve
