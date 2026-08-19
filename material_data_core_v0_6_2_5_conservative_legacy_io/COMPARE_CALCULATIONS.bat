@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
set /p "A=Calculation A id: "
set /p "B=Calculation B id: "
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli compare-calculations "%A%" "%B%"
pause
exit /b 0
:fail
pause
exit /b 1
