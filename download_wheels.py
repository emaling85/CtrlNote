"""
Скачивает готовые пакеты (.whl) в папку wheels.

Удобно для офлайн-установки зависимостей на Windows.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

# Куда складывать скачанные .whl файлы
WHEELS = Path(__file__).resolve().parent / "wheels"
WHEELS.mkdir(exist_ok=True)

# Список пакетов для офлайн-установки
PACKAGES = [
    "sounddevice",
    "numpy",
    "faster-whisper",
    "ctranslate2",
    "huggingface_hub",
    "tokenizers",
    "tqdm",
    "filelock",
    "fsspec",
    "requests",
    "PyYAML",
    "typing_extensions",
    "httpx",
    "anyio",
    "idna",
    "certifi",
    "charset-normalizer",
    "urllib3",
    "sniffio",
    "httpcore",
    "hf-xet",
    "cffi",
    "pycparser",
]


def tag() -> str:
    """Метка версии Python, например cp312."""
    return f"cp{sys.version_info.major}{sys.version_info.minor}"


def is_compatible(filename: str, py_tag: str) -> bool:
    """Подходит ли wheel для Windows и текущего Python."""
    name = filename.lower()
    if not name.endswith(".whl"):
        return False
    if "macosx" in name or "manylinux" in name or "musllinux" in name:
        return False
    if "win32" in name and "win_amd64" not in name:
        return False
    if "win_amd64" not in name and "none-any" not in name and "py2.py3-none-any" not in name:
        if "py3-none-win_amd64" not in name and "none-win_amd64" not in name:
            return False
    if "none-any" in name or "py2.py3-none-any" in name or "py3-none-any" in name:
        return True
    if "py3-none-win" in name:
        return True
    if py_tag in name:
        return True
    if "abi3" in name:
        m = re.search(r"cp(\d+)", name)
        if m:
            return int(py_tag[2:]) >= int(m.group(1))
    return False


def pick_url(files: list[dict], py_tag: str) -> str | None:
    """Выбирает лучшую ссылку на wheel под текущую систему."""
    wheels = [f for f in files if is_compatible(f.get("filename", ""), py_tag)]
    wheels.sort(
        key=lambda f: (
            0 if py_tag in f["filename"] and "win_amd64" in f["filename"] else
            1 if "win_amd64" in f["filename"] else
            2,
            f["filename"],
        )
    )
    return wheels[0]["url"] if wheels else None


def main() -> int:
    """Скачивает все пакеты из списка (или имена из аргументов командной строки)."""
    py_tag = tag()
    print(f"Python tag: {py_tag}")
    pkgs = sys.argv[1:] or PACKAGES
    for pkg in pkgs:
        print(f"\n=== {pkg} ===")
        with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=60) as resp:
            data = json.load(resp)
        url = pick_url(data.get("urls", []), py_tag)
        if not url:
            for ver, files in sorted(data.get("releases", {}).items(), reverse=True):
                url = pick_url(files, py_tag)
                if url:
                    print(f"Using version {ver}")
                    break
        if not url:
            print(f"ERROR: no compatible wheel for {pkg}")
            continue
        name = url.rsplit("/", 1)[-1]
        dest = WHEELS / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"Skip existing {name}")
            continue
        print(f"Downloading {name} ...")
        urllib.request.urlretrieve(url, dest)
        print(f"  -> {dest.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
