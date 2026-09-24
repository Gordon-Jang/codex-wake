@echo off
python "%~dp0..\watcher\wake_watcher.py" unregister-current %*
exit /b %ERRORLEVEL%
