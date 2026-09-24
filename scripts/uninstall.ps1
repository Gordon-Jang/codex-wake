param(
    [string]$TargetRoot = "$HOME\.codex\skills"
)

$ErrorActionPreference = "Stop"
$Target = Join-Path $TargetRoot "wake"

if (Test-Path $Target) {
    $Stop = Join-Path $Target "scripts\stop-watcher.ps1"
    if (Test-Path $Stop) {
        powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Stop | Out-Null
    }
    Remove-Item -Recurse -Force $Target
    Write-Host "WAKE removed from:"
    Write-Host "  $Target"
} else {
    Write-Host "WAKE is not installed at:"
    Write-Host "  $Target"
}
