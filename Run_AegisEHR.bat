@echo off
title AegisEHR - Algorand TestNet Healthcare Portal
cd /d "%~dp0"

echo ======================================================================
echo   Launching AegisEHR Desktop Application (Algorand TestNet)
echo ======================================================================

REM Check for virtual environment python
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Starting AegisEHR system with %PYTHON_EXE%...
"%PYTHON_EXE%" desktop_app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application stopped with error code %ERRORLEVEL%.
    pause
)
