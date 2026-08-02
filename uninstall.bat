@echo off
chcp 65001 >nul
setlocal
set "DEST=%LOCALAPPDATA%\CtrlNote"
set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "DESKTOP=%USERPROFILE%\Desktop"

echo Закройте CtrlNote (трей → Выход), затем нажмите любую клавишу...
pause >nul

taskkill /IM CtrlNote.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul

if exist "%DEST%" rmdir /S /Q "%DEST%" 2>nul
del /F /Q "%START_MENU%\CtrlNote.lnk" 2>nul
del /F /Q "%DESKTOP%\CtrlNote.lnk" 2>nul
del /F /Q "%STARTUP%\CtrlNote.lnk" 2>nul
del /F /Q "%STARTUP%\CtrlNote.cmd" 2>nul

reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v CtrlNote /f >nul 2>&1

echo Удалено.
endlocal
