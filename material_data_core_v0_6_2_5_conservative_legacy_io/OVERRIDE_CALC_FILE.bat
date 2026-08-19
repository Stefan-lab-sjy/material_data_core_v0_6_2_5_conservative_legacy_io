@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
set /p "CID=calculation_id: "
set /p "RPATH=relative path: "
echo Allowed roles: input output reference intermediate auxiliary unknown
set /p "ROLE=correct role: "
set /p "REASON=reason (optional): "
if defined REASON (
  "%MATERIAL_AGENT_PYTHON%" -m material_agent.cli override-calc-file "%CID%" "%RPATH%" --role "%ROLE%" --reason "%REASON%"
) else (
  "%MATERIAL_AGENT_PYTHON%" -m material_agent.cli override-calc-file "%CID%" "%RPATH%" --role "%ROLE%"
)
if errorlevel 1 goto :fail
echo.
echo OVERRIDE SAVED. Automatic re-import will preserve it.
pause
exit /b 0
:fail
echo.
echo OVERRIDE FAILED.
pause
exit /b 1
