$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$TargetRoot = Join-Path $HOME ".agents\skills"
$Target = Join-Path $TargetRoot "wake"

if (-not (Test-Path (Join-Path $RepoRoot "SKILL.md"))) {
    throw "SKILL.md not found at $RepoRoot"
}

New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null

if (Test-Path $Target) {
    Remove-Item -Recurse -Force $Target
}

New-Item -ItemType Directory -Force -Path $Target | Out-Null
Copy-Item -Force (Join-Path $RepoRoot "SKILL.md") $Target
if (Test-Path (Join-Path $RepoRoot "agents")) {
    Copy-Item -Recurse -Force (Join-Path $RepoRoot "agents") $Target
}

Write-Host ""
Write-Host "WAKE installed successfully:"
Write-Host "  $Target"
Write-Host ""
Write-Host "Try it in Codex:"
Write-Host '  $wake'
Write-Host ""
Write-Host "Codex should detect skill changes automatically; restart it if WAKE does not appear."
