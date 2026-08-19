@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
set /p "CALC_ID=Calculation ID: "
if not defined CALC_ID goto :fail
set /p "SOURCE_DIR=Original calculation folder: "
if not defined SOURCE_DIR goto :fail
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli verify-calculation "%CALC_ID%" "%SOURCE_DIR%"
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo VERIFY PASSED: every source file matches the catalog by path and SHA256.
) else (
  echo VERIFY FOUND DIFFERENCES. Review the table above.
)
pause
exit /b %RC%
:fail
echo.
echo VERIFY FAILED.
pause
exit /b 1
