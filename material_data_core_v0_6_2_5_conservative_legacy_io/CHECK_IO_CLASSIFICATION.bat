@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
cd /d "%MATERIAL_AGENT_ROOT%"
set "TARGET=%~1"
if not defined TARGET set /p "TARGET=Paste one VASP calculation OR outer project folder path: "
if not defined TARGET goto :fail
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli inspect-io "%TARGET%"
if errorlevel 1 goto :fail
echo.
echo CHECK COMPLETE. Nothing was written.
pause
exit /b 0
:fail
echo.
echo CHECK FAILED.
pause
exit /b 1
