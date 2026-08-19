@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
set "CALC=%~1"
if not defined CALC set /p "CALC=Calculation ID: "
if not defined CALC goto :fail
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli export-output-set "%CALC%"
if errorlevel 1 goto :fail
pause
exit /b 0
:fail
pause
exit /b 1
