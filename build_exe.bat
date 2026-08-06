@echo off
REM Собирает CtrlNote.exe через build_exe.py (нужен .venv с PyInstaller).
cd /d "%~dp0"
".venv\Scripts\python.exe" build_exe.py
if errorlevel 1 pause
