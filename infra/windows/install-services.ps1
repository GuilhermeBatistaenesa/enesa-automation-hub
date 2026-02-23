param(
    [string]$NssmPath = "C:\nssm\nssm.exe",
    [string]$RootPath = "C:\enesa-automation-hub"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $NssmPath)) {
    throw "NSSM nao encontrado em $NssmPath"
}

function Install-ServiceWithNssm {
    param(
        [string]$Name,
        [string]$Executable,
        [string]$Arguments,
        [string]$WorkingDir
    )

    & $NssmPath install $Name $Executable $Arguments
    & $NssmPath set $Name AppDirectory $WorkingDir
    & $NssmPath set $Name Start SERVICE_AUTO_START
    & $NssmPath set $Name AppStdout "$WorkingDir\logs\$Name.out.log"
    & $NssmPath set $Name AppStderr "$WorkingDir\logs\$Name.err.log"
}

New-Item -ItemType Directory -Path "$RootPath\backend\logs" -Force | Out-Null
New-Item -ItemType Directory -Path "$RootPath\frontend\logs" -Force | Out-Null

Install-ServiceWithNssm `
    -Name "EnesaAutomationApi" `
    -Executable "uvicorn" `
    -Arguments "app.main:app --host 0.0.0.0 --port 8000" `
    -WorkingDir "$RootPath\backend"

Install-ServiceWithNssm `
    -Name "EnesaAutomationWorker" `
    -Executable "python" `
    -Arguments "-m app.workers.executor" `
    -WorkingDir "$RootPath\backend"

Install-ServiceWithNssm `
    -Name "EnesaAutomationFrontend" `
    -Executable "npm" `
    -Arguments "run start" `
    -WorkingDir "$RootPath\frontend"

Install-ServiceWithNssm `
    -Name "EnesaAutomationCleanup" `
    -Executable "python" `
    -Arguments "-m app.workers.cleanup" `
    -WorkingDir "$RootPath\backend"

Write-Host "Servicos instalados. Inicie com: Start-Service EnesaAutomationApi, EnesaAutomationWorker, EnesaAutomationFrontend, EnesaAutomationCleanup"
