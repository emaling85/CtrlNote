"""
Сборка релиза: оба установщика подряд.

    python build_release.py
    → dist/release/CtrlNote-Setup.exe
    → dist/release/CtrlNote-Trader-Setup.exe
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
RELEASE_DIR = ROOT / "dist" / "release"


def run(*args: str) -> None:
    print("\n>>>", " ".join(args), flush=True)
    result = subprocess.run([str(PYTHON), *args], cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    for edition, setup in (("standard", "CtrlNote-Setup"), ("trader", "CtrlNote-Trader-Setup")):
        run("build_exe.py", "--edition", edition)
        run("build_installer.py")
        built = ROOT / "dist" / "installer" / f"{setup}.exe"
        shutil.copy2(built, RELEASE_DIR / built.name)
        print(f"OK: {RELEASE_DIR / built.name} ({built.stat().st_size // (1024 * 1024)} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
