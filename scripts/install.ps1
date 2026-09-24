param(
    [switch]$StartWatcher,
    [string]$TargetRoot = "$HOME\.codex\skills"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$TargetRoot = [System.IO.Path]::GetFullPath($TargetRoot)
$Target = Join-Path $TargetRoot "wake"

if (-not (Test-Path (Join-Path $RepoRoot "SKILL.md"))) {
    throw "SKILL.md not found at $RepoRoot"
}

New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null

$RepoFull = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
$TargetFull = [System.IO.Path]::GetFullPath($Target).TrimEnd('\')

if ($RepoFull -ieq $TargetFull) {
    Write-Host ""
    Write-Host "WAKE is already located at the target path:"
    Write-Host "  $Target"
    Write-Host "No copy is needed."
} else {
    $SavedState = $null
    $ExistingState = Join-Path $Target ".state"
    if (Test-Path $ExistingState) {
        $SavedState = Join-Path $env:TEMP ("wake-state-" + [guid]::NewGuid().ToString())
        Copy-Item -Recurse -Force $ExistingState $SavedState
    }

    if (Test-Path $Target) {
        Remove-Item -Recurse -Force $Target
    }

    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    Copy-Item -Force (Join-Path $RepoRoot "SKILL.md") $Target
    Copy-Item -Force (Join-Path $RepoRoot "VERSION") $Target
    Copy-Item -Recurse -Force (Join-Path $RepoRoot "agents") $Target
    Copy-Item -Recurse -Force (Join-Path $RepoRoot "watcher") $Target
    Copy-Item -Recurse -Force (Join-Path $RepoRoot "docs") $Target
    Copy-Item -Recurse -Force (Join-Path $RepoRoot "scripts") $Target

    if ($SavedState -and (Test-Path $SavedState)) {
        Copy-Item -Recurse -Force $SavedState (Join-Path $Target ".state")
        Remove-Item -Recurse -Force $SavedState
    }

    Write-Host ""
    Write-Host "WAKE v0.3.2 installed:"
    Write-Host "  $Target"
}

Write-Host ""
Write-Host "Check quota integration:"
Write-Host "  python `"$Target\watcher\wake_watcher.py`" doctor"

if ($StartWatcher) {
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Target "scripts\start-watcher.ps1")
} else {
    Write-Host ""
    Write-Host "Start watcher with:"
    Write-Host "  `"$Target\scripts\start-watcher.cmd`""
}
