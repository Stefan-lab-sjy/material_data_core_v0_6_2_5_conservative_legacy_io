@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
set "TARGET=%~1"
if not defined TARGET (
  set /p "TARGET=Paste VASP calculation folder path: "
)
if not defined TARGET goto :fail
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli import-vasp "%TARGET%"
if errorlevel 1 goto :fail
echo.
echo IMPORT COMPLETE.
pause
exit /b 0
:fail
echo.
echo IMPORT FAILED.
pause
exit /b 1
