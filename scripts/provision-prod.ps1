param(
    [switch]$SkipStart,
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Comando '$Name' nao encontrado no PATH."
    }
}

function Ensure-FileFromTemplate {
    param(
        [string]$TemplatePath,
        [string]$TargetPath
    )
    if (-not (Test-Path $TargetPath)) {
        Copy-Item $TemplatePath $TargetPath
        Write-Host "Arquivo criado: $TargetPath"
    } else {
        Write-Host "Arquivo ja existe: $TargetPath"
    }
}

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$infraDir = Join-Path $root "infra"
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

Assert-Command "docker"

Ensure-FileFromTemplate (Join-Path $infraDir ".env.prod.example") (Join-Path $infraDir ".env.prod")
Ensure-FileFromTemplate (Join-Path $backendDir ".env.prod.example") (Join-Path $backendDir ".env")
Ensure-FileFromTemplate (Join-Path $frontendDir ".env.prod.example") (Join-Path $frontendDir ".env.local")

New-Item -ItemType Directory -Path (Join-Path $backendDir "data\artifacts") -Force | Out-Null

if (-not $SkipStart) {
    Push-Location $infraDir
    try {
        $composeArgs = @("--env-file", ".env.prod", "-f", "docker-compose.prod.yml", "up", "-d")
        if ($Rebuild) {
            $composeArgs += "--build"
        }
        docker compose @composeArgs
    } finally {
        Pop-Location
    }
}

& (Join-Path $PSScriptRoot "verify-prod.ps1")

Write-Host "Provisionamento concluido."
