@echo off
python "%~dp0..\watcher\wake_watcher.py" pause-current %*
exit /b %ERRORLEVEL%
