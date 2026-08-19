@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
cd /d "%MATERIAL_AGENT_ROOT%"
echo.
echo [Material Data Core v0.6] Auto Intake for INBOX
echo First showing a dry-run plan...
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli ingest-inbox --dry-run
if errorlevel 1 goto :fail
echo.
set /p "CONFIRM=Proceed with real INBOX ingestion? [y/N]: "
if /I not "%CONFIRM%"=="y" if /I not "%CONFIRM%"=="yes" goto :cancel
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli ingest-inbox
if errorlevel 1 goto :fail
echo.
echo AUTO INTAKE COMPLETE.
pause
exit /b 0
:cancel
echo No data was written.
pause
exit /b 0
:fail
echo.
echo AUTO INTAKE FAILED.
pause
exit /b 1
