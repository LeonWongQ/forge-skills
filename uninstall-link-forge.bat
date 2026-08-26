@echo off
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%\.forge-skill\forge"
if errorlevel 1 (
  echo [ERROR] Forge source directory is unavailable.
  pause
  exit /b 1
)
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 (
  py -3 -m forge_cli.personal_hook_state interactive-uninstall-links
  set "RC=%ERRORLEVEL%"
  popd
  pause
  exit /b %RC%
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 (
  python -m forge_cli.personal_hook_state interactive-uninstall-links
  set "RC=%ERRORLEVEL%"
  popd
  pause
  exit /b %RC%
)
popd
echo [ERROR] Python 3.11 or later is required.
pause
exit /b 1
