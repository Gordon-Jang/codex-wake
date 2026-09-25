$ErrorActionPreference = "Stop"
$SkillRoot = Split-Path -Parent $PSScriptRoot
$Watcher = Join-Path $SkillRoot "watcher\wake_watcher.py"
$env:PYTHONUTF8 = "1"
python $Watcher status
