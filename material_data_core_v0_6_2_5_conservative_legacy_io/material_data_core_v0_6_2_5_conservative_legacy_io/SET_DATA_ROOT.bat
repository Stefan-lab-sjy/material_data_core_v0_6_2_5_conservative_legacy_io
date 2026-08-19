@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
set /p "ROOT=Paste an existing data folder path (the folder containing catalog.db): "
if not defined ROOT goto :fail
"%MATERIAL_AGENT_PYTHON%" -m material_agent.config_cli set "%ROOT%"
echo.
echo DATA ROOT SAVED.
pause
exit /b 0
:fail
echo.
echo CONFIGURATION FAILED.
pause
exit /b 1
