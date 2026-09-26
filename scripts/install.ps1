param(
    [switch]$StartWatcher,
    [string]$TargetRoot = "$HOME\.codex\skills"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$Target = Join-Path ([System.IO.Path]::GetFullPath($TargetRoot)) "wake"
$RepoFull = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
$TargetFull = [System.IO.Path]::GetFullPath($Target).TrimEnd('\')

New-Item -ItemType Directory -Force -Path $Target | Out-Null

if ($RepoFull -ieq $TargetFull) {
    Write-Host "WAKE is already at $Target"
} else {
    foreach ($File in @("SKILL.md","VERSION","README.md","README.zh-CN.md","CHANGELOG.md")) {
        $Source = Join-Path $RepoRoot $File
        if (Test-Path $Source) { Copy-Item -Force $Source $Target }
    }
    foreach ($Dir in @("agents","watcher","docs","scripts")) {
        $SourceDir = Join-Path $RepoRoot $Dir
        $DestDir = Join-Path $Target $Dir
        New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
        Copy-Item -Recurse -Force (Join-Path $SourceDir "*") $DestDir
    }
    foreach ($Old in @(
        "scripts\register-current.cmd","scripts\register-current.sh",
        "scripts\pause-current.cmd","scripts\pause-current.sh",
        "scripts\resume-current.cmd","scripts\resume-current.sh",
        "scripts\unregister-current.cmd","scripts\unregister-current.sh",
        "docs\v0.3.3-local.md","docs\v0.3.3-local2.md","README.local.md"
    )) {
        Remove-Item -Force (Join-Path $Target $Old) -ErrorAction SilentlyContinue
    }
    Remove-Item -Recurse -Force (Join-Path $Target ".state") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $Target "watcher\__pycache__") -ErrorAction SilentlyContinue
    Write-Host "WAKE v0.5.0 installed to $Target"
}

$WakeHome = Join-Path $HOME ".codex\wake"
New-Item -ItemType Directory -Force -Path $WakeHome | Out-Null
Write-Host "Durable jobs: $WakeHome"
Write-Host "Doctor: python $Target\watcher\wake_watcher.py doctor"
if ($StartWatcher) {
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Target "scripts\start-watcher.ps1")
}
