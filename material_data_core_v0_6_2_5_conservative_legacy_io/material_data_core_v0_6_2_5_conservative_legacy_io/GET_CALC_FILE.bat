@echo off
call "%~dp0_bootstrap.bat"
if errorlevel 1 goto :fail
set /p "CID=calculation_id: "
set /p "FT=file type (INCAR/KPOINTS/POSCAR/OUTCAR/...): "
"%MATERIAL_AGENT_PYTHON%" -m material_agent.cli get-calc-file "%CID%" "%FT%"
pause
exit /b 0
:fail
pause
exit /b 1
