@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
"%MATERIAL_AGENT_PYTHON%" -m material_agent.config_cli show
pause
exit /b 0
:fail
pause
exit /b 1
