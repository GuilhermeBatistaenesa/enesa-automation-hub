$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$infraDir = Join-Path $root "infra"
$envPath = Join-Path $infraDir ".env.prod"

if (-not (Test-Path $envPath)) {
    throw "Arquivo infra/.env.prod nao encontrado."
}

$apiPort = "8000"
$frontendPort = "3000"

Get-Content $envPath | ForEach-Object {
    if ($_ -match "^\s*API_PORT=(.+)$") { $apiPort = $Matches[1].Trim() }
    if ($_ -match "^\s*FRONTEND_PORT=(.+)$") { $frontendPort = $Matches[1].Trim() }
}

Write-Host "Verificando containers..."
Push-Location $infraDir
try {
    docker compose --env-file .env.prod -f docker-compose.prod.yml ps
} finally {
    Pop-Location
}

Write-Host "Verificando health endpoint da API..."
Invoke-RestMethod -Method Get -Uri "http://localhost:$apiPort/api/v1/health" | Out-Null

Write-Host "Verificando endpoint de metricas..."
$metricsResponse = Invoke-WebRequest -UseBasicParsing -Method Get -Uri "http://localhost:$apiPort/metrics"
if ($metricsResponse.StatusCode -ne 200) {
    throw "Falha ao consultar /metrics"
}

Write-Host "Verificando frontend..."
Invoke-WebRequest -UseBasicParsing -Method Get -Uri "http://localhost:$frontendPort" | Out-Null

Write-Host "Verificacao concluida com sucesso."
