param(
    [switch]$PurgeJobs,
    [string]$TargetRoot = "$HOME\.codex\skills"
)

$ErrorActionPreference = "Stop"
$Target = Join-Path $TargetRoot "wake"
$Stop = Join-Path $Target "scripts\stop-watcher.ps1"
if (Test-Path $Stop) {
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Stop | Out-Null
}
if (Test-Path $Target) {
    Remove-Item -Recurse -Force $Target
    Write-Host "WAKE removed: $Target"
}
if ($PurgeJobs) {
    $WakeHome = Join-Path $HOME ".codex\wake"
    if (Test-Path $WakeHome) { Remove-Item -Recurse -Force $WakeHome }
    Write-Host "WAKE durable jobs purged."
} else {
    Write-Host "Durable job/checkpoint history preserved under $HOME\.codex\wake"
}
