@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli ingest-inbox
if errorlevel 1 goto :fail
echo.
echo INBOX INGEST COMPLETE.
pause
exit /b 0
:fail
echo.
echo INBOX INGEST FAILED.
pause
exit /b 1
