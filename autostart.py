"""
Автозапуск CtrlNote вместе с Windows.

Создаёт ярлык в папке «Автозагрузка» и/или запись в реестре Run.
"""

from __future__ import annotations

import base64
import subprocess
import sys
import winreg
from pathlib import Path

from config import APP_DIR
from paths import asset_path

SHORTCUT_NAME = "CtrlNote.lnk"  # ярлык в Автозагрузке
CMD_FALLBACK_NAME = "CtrlNote.cmd"  # запасной вариант, если ярлык не создался
RUN_VALUE_NAME = "CtrlNote"  # имя записи в реестре автозапуска


def startup_dir() -> Path:
    """Папка автозагрузки текущего пользователя Windows."""
    appdata = Path.home() / "AppData" / "Roaming"
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def install_dir() -> Path:
    """Обычная папка установки: LocalAppData\\CtrlNote."""
    return Path.home() / "AppData" / "Local" / "CtrlNote"


def shortcut_path() -> Path:
    """Полный путь к ярлыку автозапуска."""
    return startup_dir() / SHORTCUT_NAME


def cmd_fallback_path() -> Path:
    """Путь к .cmd-файлу-запаснику в автозагрузке."""
    return startup_dir() / CMD_FALLBACK_NAME


def is_autostart_enabled() -> bool:
    """Проверяет, включён ли автозапуск (ярлык, .cmd или реестр)."""
    if shortcut_path().exists() or cmd_fallback_path().exists():
        return True
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        ) as key:
            winreg.QueryValueEx(key, RUN_VALUE_NAME)
            return True
    except OSError:
        return False


def _resolve_launch() -> tuple[Path, str, Path]:
    """
    Ищет, чем именно запускать CtrlNote.

    Порядок: установленный exe → текущий frozen exe → dist → python из venv.
    Возвращает (программа, аргументы, рабочая папка).
    """
    installed = install_dir() / "CtrlNote.exe"
    if installed.exists():
        return installed, "", installed.parent

    # Вариант раскладки onedir: .../CtrlNote/CtrlNote/CtrlNote.exe
    nested = install_dir() / "CtrlNote" / "CtrlNote.exe"
    if nested.exists():
        return nested, "", nested.parent

    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        return exe, "", exe.parent

    dist_onedir = APP_DIR / "dist" / "CtrlNote" / "CtrlNote.exe"
    if dist_onedir.exists():
        return dist_onedir, "", dist_onedir.parent

    dist_exe = APP_DIR / "dist" / "CtrlNote.exe"
    if dist_exe.exists():
        return dist_exe, "", dist_exe.parent

    # Режим разработки: pythonw + main.py (без чёрного окна консоли)
    venv_pythonw = APP_DIR / ".venv" / "Scripts" / "pythonw.exe"
    if venv_pythonw.exists():
        return venv_pythonw, str(APP_DIR / "main.py"), APP_DIR

    venv_python = APP_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        sibling = venv_python.with_name("pythonw.exe")
        target = sibling if sibling.exists() else venv_python
        return target, str(APP_DIR / "main.py"), APP_DIR

    current = Path(sys.executable)
    sibling = current.with_name("pythonw.exe")
    target = sibling if sibling.exists() else current
    return target, str(APP_DIR / "main.py"), APP_DIR


def _run_powershell(script: str) -> None:
    """Выполняет короткий скрипт PowerShell (нужно для создания .lnk)."""
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise OSError(err or f"PowerShell failed with code {result.returncode}")


def _ps_quote(value: str) -> str:
    """Экранирует строку для PowerShell в одинарных кавычках."""
    return "'" + value.replace("'", "''") + "'"


def _icon_for_shortcut(workdir: Path) -> Path | None:
    """Ищет icon.ico рядом с программой или в assets."""
    for candidate in (
        workdir / "icon.ico",
        workdir / "assets" / "icon.ico",
        asset_path("icon.ico"),
        APP_DIR / "assets" / "icon.ico",
    ):
        if candidate.exists():
            return candidate
    return None


def _create_shortcut() -> None:
    """Создаёт ярлык CtrlNote.lnk в папке автозагрузки."""
    target, arguments, workdir = _resolve_launch()
    lnk = shortcut_path()
    lnk.parent.mkdir(parents=True, exist_ok=True)
    icon = _icon_for_shortcut(workdir)
    icon_line = ""
    if icon is not None:
        icon_line = f"$s.IconLocation = {_ps_quote(str(icon) + ',0')}"

    script = f"""
$ErrorActionPreference = 'Stop'
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut({_ps_quote(str(lnk))})
$s.TargetPath = {_ps_quote(str(target))}
$s.Arguments = {_ps_quote(arguments)}
$s.WorkingDirectory = {_ps_quote(str(workdir))}
$s.WindowStyle = 7
$s.Description = 'CtrlNote'
{icon_line}
$s.Save()
"""
    _run_powershell(script)


def _create_cmd_fallback() -> None:
    """Запасной автозапуск через .cmd, если ярлык создать не удалось."""
    target, arguments, workdir = _resolve_launch()
    path = cmd_fallback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if arguments:
        launch = f'start "" "{target}" {arguments}'
    else:
        launch = f'start "" "{target}"'
    content = (
        "@echo off\r\n"
        f'cd /d "{workdir}"\r\n'
        f"{launch}\r\n"
    )
    path.write_text(content, encoding="utf-8")


def _set_registry_run(enabled: bool) -> None:
    """Включает или выключает запись CtrlNote в реестре Run."""
    path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    if enabled:
        target, arguments, _workdir = _resolve_launch()
        if arguments:
            value = f'"{target}" {arguments}'
        else:
            value = f'"{target}"'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, value)
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, RUN_VALUE_NAME)
        except FileNotFoundError:
            pass


def enable_autostart() -> None:
    """Включает автозапуск: ярлык (или .cmd) + запись в реестре."""
    try:
        _create_shortcut()
        fallback = cmd_fallback_path()
        if fallback.exists():
            fallback.unlink()
    except OSError:
        _create_cmd_fallback()

    try:
        _set_registry_run(True)
    except OSError:
        pass

    if not is_autostart_enabled():
        raise OSError("Не удалось создать автозапуск")


def disable_autostart() -> None:
    """Выключает автозапуск: удаляет ярлыки и запись в реестре."""
    for path in (shortcut_path(), cmd_fallback_path()):
        try:
            if path.exists():
                path.unlink()
        except OSError as exc:
            raise OSError(f"Не удалось удалить {path.name}: {exc}") from exc
    try:
        _set_registry_run(False)
    except OSError as exc:
        raise OSError(f"Не удалось убрать автозапуск из реестра: {exc}") from exc


def set_autostart(enabled: bool) -> None:
    """Включает или выключает автозапуск по флагу из настроек."""
    if enabled:
        enable_autostart()
    else:
        disable_autostart()
