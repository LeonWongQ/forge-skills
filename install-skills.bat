@echo off
setlocal
chcp 65001 >nul 2>nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set "SCRIPT_DIR=%~dp0"
py -3 "%SCRIPT_DIR%\.claude\forge\scripts\sync-agent-skills.py" %*
if not errorlevel 9009 exit /b %ERRORLEVEL%
python "%SCRIPT_DIR%\.claude\forge\scripts\sync-agent-skills.py" %*
exit /b %ERRORLEVEL%
