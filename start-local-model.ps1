param(
    [string]$RuntimeRoot = (Join-Path (Split-Path $PSScriptRoot -Parent) '.local-tools\ollama')
)
$ErrorActionPreference = 'Stop'
$executable = Join-Path $RuntimeRoot 'ollama.exe'
if (-not (Test-Path -LiteralPath $executable)) {
    throw 'Chua cai Ollama CPU runtime. Xem docs/llm-model-selection.md.'
}
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_MODELS = Join-Path $RuntimeRoot 'models'

function Confirm-LocalModel {
    $body = @{ model = 'episcout-local' } | ConvertTo-Json
    try {
        $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/show' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 10
    } catch {
        if ($null -eq $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 404) {
            throw
        }
        & $executable create episcout-local -f (Join-Path $PSScriptRoot 'Modelfile.local')
        if ($LASTEXITCODE -ne 0) {
            throw 'Khong tao duoc episcout-local. Kiem tra model nguon trong Modelfile.local.'
        }
    }
    Write-Output 'Model local san sang: episcout-local (khong dung API cloud).'
}

$serviceIsRunning = $false
try {
    $version = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 3
    Write-Output "Ollama dang chay: $($version.version)"
    $serviceIsRunning = $true
} catch {
    # Start the local service if it is not reachable.
}
if ($serviceIsRunning) {
    Confirm-LocalModel
    return
}
$env:OLLAMA_NOPRUNE = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_KEEP_ALIVE = '2m'
$logs = Join-Path $PSScriptRoot 'scratch'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$process = Start-Process -FilePath $executable -ArgumentList 'serve' -WorkingDirectory $RuntimeRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'ollama.stdout.log') -RedirectStandardError (Join-Path $logs 'ollama.stderr.log') -PassThru
Write-Output "Ollama local PID: $($process.Id)"
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
        $serviceIsRunning = $true
        break
    } catch {
        Start-Sleep -Milliseconds 500
    }
}
if ($serviceIsRunning) {
    Confirm-LocalModel
    return
}
throw "Ollama chua san sang. Xem log tai $logs\ollama.stderr.log."
