$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot

Push-Location $projectRoot
try {
    python -m uvicorn app.main:app `
        --reload `
        --host 127.0.0.1 `
        --port 8000
}
finally {
    Pop-Location
}
