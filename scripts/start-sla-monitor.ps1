$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\backend"
python -m app.workers.sla_monitor
