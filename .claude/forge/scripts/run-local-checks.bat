@echo off
setlocal

chcp 65001 >nul 2>nul
set PYTHONIOENCODING=utf-8
set SCRIPT_DIR=%~dp0

python "%SCRIPT_DIR%run-local-checks.py" %*
exit /b %errorlevel%
