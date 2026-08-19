@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
cd /d "%MATERIAL_AGENT_ROOT%"
echo Available recipes:
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli list-recipes
echo.
set /p "RECIPE=Recipe ID: "
set /p "DEST=New run folder: "
if not defined RECIPE goto :fail
if not defined DEST goto :fail
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli instantiate-recipe "%RECIPE%" "%DEST%"
if errorlevel 1 goto :fail
echo.
echo Recipe instantiated. Add the required runtime inputs (POSCAR/POTCAR/KPOINTS/CHGCAR as listed) before running VASP.
pause
exit /b 0
:fail
echo.
echo CREATE RUN FAILED.
pause
exit /b 1
