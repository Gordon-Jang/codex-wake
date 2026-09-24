@echo off
python "%~dp0..\watcher\wake_watcher.py" register-current %*
exit /b %ERRORLEVEL%
