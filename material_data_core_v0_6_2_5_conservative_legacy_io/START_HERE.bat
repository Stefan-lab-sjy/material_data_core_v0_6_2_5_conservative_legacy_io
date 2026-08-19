@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
cd /d "%MATERIAL_AGENT_ROOT%"
echo.
echo Running Material Data Core + Agent v0.6.2.5 tests...
"%MATERIAL_AGENT_PYTHON%" -m unittest discover -s tests -v
if errorlevel 1 goto :fail
echo.
echo ALL TESTS PASSED.
echo.
echo You can now:
echo   1. Run SET_DATA_ROOT.bat if you want to reuse data from v0.4.1.
echo   2. Run CHECK_IO_CLASSIFICATION.bat first, then TEST_REAL_VASP.bat / AUTO_INGEST_PATH.bat for real data.
echo   3. Run AUTO_INGEST.bat for INBOX auto-routing, or START_AGENT.bat to query the data.
pause
exit /b 0
:fail
echo.
echo TEST FAILED.
pause
exit /b 1
