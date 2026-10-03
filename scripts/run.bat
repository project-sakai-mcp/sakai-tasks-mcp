@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
"%~dp0python-embed\python.exe" "%~dp0src\server.py" %*
