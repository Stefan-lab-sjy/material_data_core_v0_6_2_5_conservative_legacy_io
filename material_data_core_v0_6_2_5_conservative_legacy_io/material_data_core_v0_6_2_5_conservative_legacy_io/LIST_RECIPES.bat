@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
cd /d "%MATERIAL_AGENT_ROOT%"
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli list-recipes
pause
exit /b 0
:fail
pause
exit /b 1
