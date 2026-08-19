@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
cd /d "%MATERIAL_AGENT_ROOT%"
set "TARGET=%~1"
if not defined TARGET set /p "TARGET=Paste file, VASP calculation, or outer project folder path: "
if not defined TARGET goto :fail
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli auto-ingest "%TARGET%" --dry-run
if errorlevel 1 goto :fail
echo.
set /p "CONFIRM=The plan above looks correct. Ingest now? [y/N]: "
if /I not "%CONFIRM%"=="y" if /I not "%CONFIRM%"=="yes" goto :cancel
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli auto-ingest "%TARGET%"
if errorlevel 1 goto :fail
echo.
echo INGEST COMPLETE.
pause
exit /b 0
:cancel
echo No data was written.
pause
exit /b 0
:fail
echo.
echo INGEST FAILED.
pause
exit /b 1
