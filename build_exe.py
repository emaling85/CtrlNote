"""
Сборка CtrlNote.exe (режим onedir — быстрее стартует, чем один большой файл).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    """Собирает папку dist/CtrlNote с CtrlNote.exe через PyInstaller."""
    pyinstaller = ROOT / ".venv" / "Scripts" / "pyinstaller.exe"
    if not pyinstaller.exists():
        print("PyInstaller not found. Install with:")
        print(r"  .\.venv\Scripts\python.exe -m pip install pyinstaller")
        return 1

    icon = ROOT / "assets" / "icon.ico"
    assets_sep = ";" if sys.platform == "win32" else ":"
    # onedir: не распаковывается во временную папку при каждом запуске — быстрее старт
    cmd = [
        str(pyinstaller),
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        "CtrlNote",
        f"--icon={icon}",
        f"--add-data={ROOT / 'assets'}{assets_sep}assets",
        "--collect-all",
        "customtkinter",
        "--collect-all",
        "darkdetect",
        "--collect-all",
        "faster_whisper",
        "--collect-submodules",
        "ctranslate2",
        "--hidden-import",
        "pystray._win32",
        "--hidden-import",
        "PIL._tkinter_finder",
        "--hidden-import",
        "sounddevice",
        "--hidden-import",
        "av",
        "--hidden-import",
        "onnxruntime",
        "--hidden-import",
        "tokenizers",
        "--hidden-import",
        "huggingface_hub",
        "--hidden-import",
        "paint_window",
        "--hidden-import",
        "markdown_edit",
        "--hidden-import",
        "onboarding",
        "--hidden-import",
        "ui_icon",
        "--hidden-import",
        "vault_paths",
        "--hidden-import",
        "i18n",
        "--hidden-import",
        "clipboard_image",
        "--hidden-import",
        "voice",
        "--hidden-import",
        "capture_window",
        str(ROOT / "main.py"),
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    exe = ROOT / "dist" / "CtrlNote" / "CtrlNote.exe"
    # Копируем иконки рядом с exe — для ярлыков и Проводника
    for name in ("icon.ico", "icon.png", "icon-tray.png"):
        src = ROOT / "assets" / name
        if src.exists() and exe.parent.is_dir():
            shutil.copy2(src, exe.parent / name)

    if exe.exists():
        print(f"\nOK: {exe}")
        print("Fast start: onedir (folder dist\\CtrlNote\\).")
        print("Install: install.bat  ->  %LOCALAPPDATA%\\CtrlNote")
        print("Close old CtrlNote and re-enable autostart in settings.")
        return 0

    print("Build finished but CtrlNote.exe not found in dist/CtrlNote/", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
