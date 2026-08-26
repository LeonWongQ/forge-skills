@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "SCRIPT_DIR=%~dp0"
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 (
  py -3 "%SCRIPT_DIR%\.forge-skill\forge\scripts\sync-agent-skills.py" %*
  exit /b !ERRORLEVEL!
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 (
  python "%SCRIPT_DIR%\.forge-skill\forge\scripts\sync-agent-skills.py" %*
  exit /b !ERRORLEVEL!
)
echo [ERROR] Python 3.11 or later is required.
exit /b 1
