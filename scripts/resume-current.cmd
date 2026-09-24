@echo off
python "%~dp0..\watcher\wake_watcher.py" resume-current %*
exit /b %ERRORLEVEL%
