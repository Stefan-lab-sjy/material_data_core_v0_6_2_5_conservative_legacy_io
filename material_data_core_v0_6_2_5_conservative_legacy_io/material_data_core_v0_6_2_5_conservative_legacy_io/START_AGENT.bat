@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
cd /d "%MATERIAL_AGENT_ROOT%"
echo.
"%MATERIAL_AGENT_PYTHON%" -m material_agent.agent_cli
exit /b 0
:fail
echo.
echo AGENT START FAILED.
pause
exit /b 1
