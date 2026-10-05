@echo off
setlocal
cd /d "%~dp0"

:: フォルダ内の Mark of the Web (Zone.Identifier) をサイレントに解除
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%~dp0' -Recurse | Unblock-File -ErrorAction SilentlyContinue" 2>nul

set "PYTHONPATH=%~dp0"
set "PYTHONHOME=%~dp0python-embed"
set "PYTHONNET_PYDLL=%~dp0python-embed\python312.dll"
"%~dp0python-embed\python.exe" "%~dp0src\server.py" %*
