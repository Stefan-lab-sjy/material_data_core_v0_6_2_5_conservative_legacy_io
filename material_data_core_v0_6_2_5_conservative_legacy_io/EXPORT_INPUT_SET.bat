@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
set /p "CID=calculation_id: "
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli export-input-set "%CID%"
pause
exit /b 0
:fail
pause
exit /b 1
