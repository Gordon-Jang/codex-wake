$ErrorActionPreference = "Stop"
$SkillRoot = Split-Path -Parent $PSScriptRoot
$Watcher = Join-Path $SkillRoot "watcher\wake_watcher.py"
$WakeHome = Join-Path $HOME ".codex\wake"
$PidFile = Join-Path $WakeHome "watcher.pid"
New-Item -ItemType Directory -Force -Path $WakeHome | Out-Null

if (Test-Path $PidFile) {
    $OldPid = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($OldPid -and (Get-Process -Id $OldPid -ErrorAction SilentlyContinue)) {
        Write-Host "WAKE watcher already running (PID $OldPid)."
        exit 0
    }
}

$Python = $null
foreach ($Name in @("pythonw.exe", "python.exe", "pythonw", "python")) {
    $Cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($Cmd) { $Python = $Cmd.Source; break }
}
if (-not $Python) { throw "Python 3 was not found in PATH." }

$env:PYTHONUTF8 = "1"
$Proc = Start-Process -FilePath $Python -ArgumentList @($Watcher, "run") -WindowStyle Hidden -PassThru
Start-Sleep -Milliseconds 800
Write-Host "WAKE watcher start requested (PID $($Proc.Id))."
python $Watcher status
