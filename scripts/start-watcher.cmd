@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-watcher.ps1" %*
exit /b %ERRORLEVEL%
