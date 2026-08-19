@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
set /p "CID=calculation_id: "
set /p "RPATH=relative path (example KPATH.in): "
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli explain-calc-file "%CID%" "%RPATH%"
pause
exit /b 0
:fail
pause
exit /b 1
