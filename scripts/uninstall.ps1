$ErrorActionPreference = "Stop"

$Target = Join-Path $HOME ".agents\skills\wake"

if (Test-Path $Target) {
    Remove-Item -Recurse -Force $Target
    Write-Host "WAKE removed from:"
    Write-Host "  $Target"
} else {
    Write-Host "WAKE is not installed at:"
    Write-Host "  $Target"
}

Write-Host "Restart Codex if the skill still appears in the skill picker."
