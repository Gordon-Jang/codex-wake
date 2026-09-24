$ErrorActionPreference = "Stop"
$SkillRoot = Split-Path -Parent $PSScriptRoot
$Watcher = Join-Path $SkillRoot "watcher\wake_watcher.py"
python $Watcher status
