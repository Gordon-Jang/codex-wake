@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-watcher.ps1" %*
exit /b %ERRORLEVEL%
