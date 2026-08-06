@echo off
REM Запуск CtrlNote в режиме разработки (через виртуальное окружение).
cd /d "%~dp0"
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
