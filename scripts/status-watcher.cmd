@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0status-watcher.ps1" %*
exit /b %ERRORLEVEL%
