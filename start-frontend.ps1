param([int]$Port = 8080)
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot 'frontend')
try {
    & npm.cmd run dev -- --host 127.0.0.1 --port $Port --strictPort
} finally {
    Pop-Location
}
