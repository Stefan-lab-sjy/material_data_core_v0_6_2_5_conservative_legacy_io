@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"
set "PYTHONPATH=%PROJECT_ROOT%src"
set "PYTHONUTF8=1"
set "PYTHON_EXE="
if exist "%PROJECT_ROOT%.venv\Scripts\python.exe" set "PYTHON_EXE=%PROJECT_ROOT%.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "D:\anoconda\python.exe" set "BASE_PYTHON=D:\anoconda\python.exe"
if not defined PYTHON_EXE if not defined BASE_PYTHON if exist "D:\Anaconda\python.exe" set "BASE_PYTHON=D:\Anaconda\python.exe"
if not defined PYTHON_EXE if not defined BASE_PYTHON if exist "%USERPROFILE%\anaconda3\python.exe" set "BASE_PYTHON=%USERPROFILE%\anaconda3\python.exe"
if not defined PYTHON_EXE if not defined BASE_PYTHON if exist "%USERPROFILE%\miniconda3\python.exe" set "BASE_PYTHON=%USERPROFILE%\miniconda3\python.exe"
if not defined PYTHON_EXE if not defined BASE_PYTHON for /f "delims=" %%P in ('where python 2^>nul') do if not defined BASE_PYTHON set "BASE_PYTHON=%%P"
if not defined PYTHON_EXE (
  if not defined BASE_PYTHON (
    echo ERROR: No usable Python was found.
    exit /b 10
  )
  echo Creating project virtual environment with: %BASE_PYTHON%
  "%BASE_PYTHON%" -m venv "%PROJECT_ROOT%.venv"
  if errorlevel 1 exit /b 11
  set "PYTHON_EXE=%PROJECT_ROOT%.venv\Scripts\python.exe"
)
"%PYTHON_EXE%" -c "import sys; print('Python', sys.version.split()[0]); import material_agent; print('material_agent import: OK; version', material_agent.__version__)"
if errorlevel 1 exit /b 12
endlocal & set "MATERIAL_AGENT_PYTHON=%PYTHON_EXE%" & set "MATERIAL_AGENT_ROOT=%PROJECT_ROOT%" & set "PYTHONPATH=%PROJECT_ROOT%src" & set "PYTHONUTF8=1"
exit /b 0
