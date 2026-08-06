"""
Сборка установщика CtrlNote-Setup.exe.

Упаковывает dist/CtrlNote в zip и вшивает его в мастер установки.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST_APP = ROOT / "dist" / "CtrlNote"
OUT_DIR = ROOT / "dist" / "installer"
ZIP_PATH = OUT_DIR / "app.zip"
SETUP_NAME = "CtrlNote-Setup"


def _zip_app() -> None:
    """Упаковывает собранное приложение в app.zip для установщика."""
    if not (DIST_APP / "CtrlNote.exe").exists():
        raise SystemExit(
            f"Нет {DIST_APP / 'CtrlNote.exe'}\nСначала: build_exe.bat"
        )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    print(f"Zipping {DIST_APP} -> {ZIP_PATH} …")
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in DIST_APP.rglob("*"):
            if path.is_file():
                arc = path.relative_to(DIST_APP).as_posix()
                zf.write(path, arc)
    print(f"Zip size: {ZIP_PATH.stat().st_size // (1024 * 1024)} MB")


def main() -> int:
    """Собирает CtrlNote-Setup.exe с вложенным app.zip."""
    _zip_app()

    pyinstaller = ROOT / ".venv" / "Scripts" / "pyinstaller.exe"
    if not pyinstaller.exists():
        print("PyInstaller not found in .venv")
        return 1

    icon = ROOT / "assets" / "icon.ico"
    sep = ";" if sys.platform == "win32" else ":"
    # Убираем старые файлы setup, чтобы не было конфликта имён
    for stale in (ROOT / "dist" / f"{SETUP_NAME}.exe", ROOT / "build" / SETUP_NAME):
        if stale.is_file():
            stale.unlink()
        elif stale.is_dir():
            shutil.rmtree(stale, ignore_errors=True)

    cmd = [
        str(pyinstaller),
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        SETUP_NAME,
        f"--icon={icon}",
        f"--add-data={ZIP_PATH}{sep}.",
        str(ROOT / "setup_wizard.py"),
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    built = ROOT / "dist" / f"{SETUP_NAME}.exe"
    if not built.exists():
        print("Setup exe not found", file=sys.stderr)
        return 1

    final = OUT_DIR / f"{SETUP_NAME}.exe"
    shutil.copy2(built, final)
    # Иконка рядом с setup — красивее в Проводнике
    if icon.exists():
        shutil.copy2(icon, OUT_DIR / "icon.ico")

    print(f"\nOK: {final}")
    print("Скинь другу этот один файл — он установит CtrlNote.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
