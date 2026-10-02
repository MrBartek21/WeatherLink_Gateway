@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
py -3 --version >nul 2>&1 && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD python --version >nul 2>&1 && set "PYTHON_CMD=python"
if not defined PYTHON_CMD python3 --version >nul 2>&1 && set "PYTHON_CMD=python3"

if not defined PYTHON_CMD (
    where winget >nul 2>&1
    if errorlevel 1 goto python_missing

    echo Python is not installed. The OLED emulator needs Python 3.13.
    choice /C YN /M "Install Python 3.13 for this Windows user now"
    if errorlevel 2 goto python_missing

    winget install --id Python.Python.3.13 --exact --scope user --accept-source-agreements --accept-package-agreements
    if errorlevel 1 goto failed

    set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python313\python.exe"
    if not exist "%LocalAppData%\Programs\Python\Python313\python.exe" goto python_missing
)

if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto failed

    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 goto failed

    ".venv\Scripts\python.exe" -m pip install -r requirements-emulator.txt
    if errorlevel 1 goto failed
)

".venv\Scripts\python.exe" oled_emulator.py
if errorlevel 1 goto failed
exit /b 0

:failed
echo.
echo Emulator setup or startup failed. Read the error above and try again.
pause
exit /b 1

:python_missing
echo.
echo Python 3 could not be found. Install it from https://www.python.org/downloads/windows/
echo During installation, enable the option to add Python to PATH, then run this file again.
pause
exit /b 1
