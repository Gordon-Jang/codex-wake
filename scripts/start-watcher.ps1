$ErrorActionPreference = "Stop"

$SkillRoot = Split-Path -Parent $PSScriptRoot
$Watcher = Join-Path $SkillRoot "watcher\wake_watcher.py"
$StateDir = Join-Path $SkillRoot ".state"
$PidFile = Join-Path $StateDir "watcher.pid"

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

if (Test-Path $PidFile) {
    $OldPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($OldPid -and (Get-Process -Id $OldPid -ErrorAction SilentlyContinue)) {
        Write-Host "WAKE watcher already running (PID $OldPid)."
        exit 0
    }
}

$Python = $null
foreach ($Name in @("pythonw.exe", "python.exe", "pythonw", "python")) {
    $Cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($Cmd) {
        $Python = $Cmd.Source
        break
    }
}
if (-not $Python) {
    throw "Python 3 was not found in PATH."
}

$Proc = Start-Process -FilePath $Python -ArgumentList @($Watcher, "run") -WindowStyle Hidden -PassThru
Start-Sleep -Milliseconds 500
Write-Host "WAKE watcher start requested (PID $($Proc.Id))."
Write-Host "Status: python `"$Watcher`" status"
