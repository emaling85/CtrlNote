@echo off
chcp 65001 >nul
setlocal
set "SRC_DIR=%~dp0dist\CtrlNote"
set "SRC_EXE=%SRC_DIR%\CtrlNote.exe"
set "DEST=%LOCALAPPDATA%\CtrlNote"
set "START_MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
set "DESKTOP=%USERPROFILE%\Desktop"

if not exist "%SRC_EXE%" (
  echo Сначала соберите: build_exe.bat
  echo Ожидалась папка: %SRC_DIR%
  exit /b 1
)

echo Закройте CtrlNote (трей → Выход), если запущен...
timeout /t 2 /nobreak >nul

mkdir "%DEST%" 2>nul
robocopy "%SRC_DIR%" "%DEST%" /MIR /NFL /NDL /NJH /NJS /nc /ns /np >nul
if errorlevel 8 (
  echo Не удалось скопировать. Закройте CtrlNote и повторите.
  exit /b 1
)

REM иконка рядом с exe на случай если robocopy не подхватил
if exist "%~dp0assets\icon.ico" copy /Y "%~dp0assets\icon.ico" "%DEST%\icon.ico" >nul

set "ICON=%DEST%\icon.ico"
if not exist "%ICON%" set "ICON=%DEST%\CtrlNote.exe"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%START_MENU%\CtrlNote.lnk'); ^
   $s.TargetPath = '%DEST%\CtrlNote.exe'; $s.WorkingDirectory = '%DEST%'; ^
   $s.Description = 'CtrlNote'; $s.IconLocation = '%ICON%,0'; $s.Save(); ^
   $d = $ws.CreateShortcut('%DESKTOP%\CtrlNote.lnk'); ^
   $d.TargetPath = '%DEST%\CtrlNote.exe'; $d.WorkingDirectory = '%DEST%'; ^
   $d.Description = 'CtrlNote'; $d.IconLocation = '%ICON%,0'; $d.Save()"

echo.
echo Установлено: %DEST%\CtrlNote.exe
echo Ярлыки: Пуск + Рабочий стол
echo.
echo Включите «Запускать с Windows» в настройках ⚙ — тогда после перезагрузки само поднимется.
echo.
start "" "%DEST%\CtrlNote.exe"
endlocal
