param([int]$Port = 8001)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$backendPython = Join-Path $PSScriptRoot 'backend\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $backendPython)) {
    throw 'Chua co backend\venv. Chay python -m venv backend\venv va cai backend\requirements.txt truoc.'
}
$configFile = Join-Path $PSScriptRoot '.env'
if (Test-Path -LiteralPath $configFile) {
    $usesLocalModel = Select-String -LiteralPath $configFile -Pattern '^\s*OPENAI_BASE_URL\s*=\s*[''"]?http://(127\.0\.0\.1|localhost):11434/v1/?[''"]?\s*$' -Quiet
    if ($usesLocalModel) {
        & (Join-Path $PSScriptRoot 'start-local-model.ps1')
    }
}
Push-Location $PSScriptRoot
try {
    & $backendPython -m uvicorn backend.main:app --app-dir $PSScriptRoot --host 127.0.0.1 --port $Port --reload --reload-dir (Join-Path $PSScriptRoot 'backend')
} finally {
    Pop-Location
}
