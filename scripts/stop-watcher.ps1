$ErrorActionPreference = "Stop"

$SkillRoot = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $SkillRoot ".state\watcher.pid"

if (-not (Test-Path $PidFile)) {
    Write-Host "WAKE watcher is not running (no PID file)."
    exit 0
}

$PidValue = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
if ($PidValue -and (Get-Process -Id $PidValue -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $PidValue -Force
    Write-Host "Stopped WAKE watcher PID $PidValue."
} else {
    Write-Host "WAKE watcher PID file was stale."
}

Remove-Item -Force $PidFile -ErrorAction SilentlyContinue
