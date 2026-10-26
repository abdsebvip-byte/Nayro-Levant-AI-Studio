@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Nayro Levant AI Studio

echo.
echo   Nayro Levant AI Studio
echo   ----------------------
echo.

if not exist ".venv\Scripts\python.exe" (
  echo First run: installing requirements, this may take a few minutes...
  py -3 -m venv .venv 2>nul
  if not exist ".venv\Scripts\python.exe" python -m venv .venv
  if not exist ".venv\Scripts\python.exe" goto :error
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -e ".[web,voice]"
  if errorlevel 1 goto :error
)

".venv\Scripts\python.exe" run.py
if errorlevel 1 goto :error
goto :end

:error
echo.
echo Something went wrong. Make sure Python 3.10+ is installed and you are online.
pause
exit /b 1

:end
pause
