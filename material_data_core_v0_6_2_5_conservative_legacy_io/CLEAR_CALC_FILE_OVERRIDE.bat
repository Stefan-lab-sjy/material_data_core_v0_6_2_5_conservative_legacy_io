@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
set /p "CID=calculation_id: "
set /p "RPATH=relative path: "
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli clear-calc-file-override "%CID%" "%RPATH%"
if errorlevel 1 goto :fail
pause
exit /b 0
:fail
pause
exit /b 1
