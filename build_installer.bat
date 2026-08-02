@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "dist\CtrlNote\CtrlNote.exe" (
  echo Building app first...
  call build_exe.bat
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" build_installer.py
echo.
echo Setup: dist\installer\CtrlNote-Setup.exe
pause
