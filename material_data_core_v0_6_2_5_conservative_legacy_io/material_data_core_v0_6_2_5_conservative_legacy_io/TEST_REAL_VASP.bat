@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
cd /d "%MATERIAL_AGENT_ROOT%"
set "TARGET=%~1"
if not defined TARGET set /p "TARGET=Paste a VASP calculation OR outer project folder path: "
if not defined TARGET goto :fail
echo.
echo ================================================================
echo STEP 1 - Inspect only. Nothing is written.
echo ================================================================
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli inspect-path "%TARGET%"
if errorlevel 1 goto :fail
echo.
echo ================================================================
echo STEP 2 - Dry run. Nothing is written.
echo ================================================================
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli auto-ingest "%TARGET%" --dry-run
if errorlevel 1 goto :fail
echo.
echo DRY RUN COMPLETE. Your folder/project was not modified and no data was ingested.
pause
exit /b 0
:fail
echo.
echo TEST FAILED.
pause
exit /b 1
