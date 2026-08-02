"""CtrlNote Setup wizard — installs app to LocalAppData."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


APP_NAME = "CtrlNote"
DEFAULT_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME


def _payload_zip() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app.zip"  # type: ignore[attr-defined]
    # Dev: zip next to this file or under dist/
    here = Path(__file__).resolve().parent
    for candidate in (
        here / "app.zip",
        here / "dist" / "installer" / "app.zip",
        here.parent / "dist" / "installer" / "app.zip",
    ):
        if candidate.exists():
            return candidate
    raise FileNotFoundError("app.zip not found — run build_installer.py first")


def _create_shortcut(lnk: Path, target: Path, workdir: Path, icon: Path | None) -> None:
    import base64
    import subprocess

    def q(s: str) -> str:
        return "'" + s.replace("'", "''") + "'"

    icon_line = ""
    if icon and icon.exists():
        icon_line = f"$s.IconLocation = {q(str(icon) + ',0')}"

    script = f"""
$ErrorActionPreference = 'Stop'
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut({q(str(lnk))})
$s.TargetPath = {q(str(target))}
$s.WorkingDirectory = {q(str(workdir))}
$s.Description = 'CtrlNote'
{icon_line}
$s.Save()
"""
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        check=False,
        capture_output=True,
    )


def install(
    dest: Path,
    *,
    desktop: bool = True,
    start_menu: bool = True,
    autostart: bool = False,
    progress=None,
) -> Path:
    dest = dest.expanduser().resolve()
    zpath = _payload_zip()

    def report(msg: str) -> None:
        if progress:
            progress(msg)

    report("Распаковка…")
    if dest.exists():
        # Keep config.json if present
        cfg = dest / "config.json"
        cfg_backup = None
        if cfg.exists():
            cfg_backup = Path(tempfile.gettempdir()) / "ctrlnote-config-backup.json"
            shutil.copy2(cfg, cfg_backup)
        shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True, exist_ok=True)
        if cfg_backup and cfg_backup.exists():
            shutil.copy2(cfg_backup, dest / "config.json")
            cfg_backup.unlink(missing_ok=True)
    else:
        dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zpath, "r") as zf:
        zf.extractall(dest)

    exe = dest / "CtrlNote.exe"
    if not exe.exists():
        # zip may contain a top-level CtrlNote/ folder
        nested = dest / "CtrlNote" / "CtrlNote.exe"
        if nested.exists():
            # flatten
            tmp = dest.parent / (dest.name + "_tmp_flatten")
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)
            shutil.move(str(dest / "CtrlNote"), str(tmp))
            shutil.rmtree(dest, ignore_errors=True)
            shutil.move(str(tmp), str(dest))
            exe = dest / "CtrlNote.exe"

    if not exe.exists():
        raise FileNotFoundError("CtrlNote.exe not found after extract")

    icon = dest / "icon.ico"
    if not icon.exists():
        icon = exe

    report("Ярлыки…")
    if start_menu:
        sm = (
            Path(os.environ["APPDATA"])
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "CtrlNote.lnk"
        )
        sm.parent.mkdir(parents=True, exist_ok=True)
        _create_shortcut(sm, exe, dest, icon if icon.suffix == ".ico" else None)

    if desktop:
        desk = Path.home() / "Desktop" / "CtrlNote.lnk"
        _create_shortcut(desk, exe, dest, icon if icon.suffix == ".ico" else None)

    if autostart:
        report("Автозапуск…")
        try:
            # Prefer installing into place first, then enable via same logic as app
            sys.path.insert(0, str(dest))
            # Use registry + startup from our bundled approach without importing app:
            run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "CtrlNote", 0, winreg.REG_SZ, f'"{exe}"')
            startup = (
                Path(os.environ["APPDATA"])
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs"
                / "Startup"
                / "CtrlNote.lnk"
            )
            _create_shortcut(startup, exe, dest, icon if icon.suffix == ".ico" else None)
        except OSError:
            pass

    report("Готово")
    return exe


def main() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("Установка CtrlNote")
    root.geometry("460x320")
    root.resizable(False, False)

    dest_var = tk.StringVar(value=str(DEFAULT_DIR))
    desktop_var = tk.BooleanVar(value=True)
    start_var = tk.BooleanVar(value=True)
    auto_var = tk.BooleanVar(value=True)
    status_var = tk.StringVar(value="Установит CtrlNote и создаст ярлыки.")

    try:
        # Window icon if available next to setup
        ico = Path(sys.executable).with_name("icon.ico") if getattr(sys, "frozen", False) else Path(__file__).parent / "assets" / "icon.ico"
        if not ico.exists():
            ico = Path(__file__).resolve().parent / "assets" / "icon.ico"
        if ico.exists():
            root.iconbitmap(str(ico))
    except Exception:
        pass

    frm = ttk.Frame(root, padding=16)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="CtrlNote Setup", font=("Segoe UI", 14, "bold")).pack(anchor="w")
    ttk.Label(frm, text="Быстрые заметки в Obsidian", foreground="#555").pack(anchor="w", pady=(0, 12))

    path_row = ttk.Frame(frm)
    path_row.pack(fill="x", pady=(0, 8))
    ttk.Label(path_row, text="Папка:").pack(side="left")
    ttk.Entry(path_row, textvariable=dest_var).pack(side="left", fill="x", expand=True, padx=6)

    def browse() -> None:
        chosen = filedialog.askdirectory(initialdir=dest_var.get())
        if chosen:
            dest_var.set(str(Path(chosen) / APP_NAME))

    ttk.Button(path_row, text="Обзор", command=browse, width=8).pack(side="right")

    ttk.Checkbutton(frm, text="Ярлык на рабочем столе", variable=desktop_var).pack(anchor="w")
    ttk.Checkbutton(frm, text="Ярлык в меню Пуск", variable=start_var).pack(anchor="w")
    ttk.Checkbutton(frm, text="Запускать вместе с Windows", variable=auto_var).pack(anchor="w")

    ttk.Label(frm, textvariable=status_var, foreground="#333").pack(anchor="w", pady=(16, 8))

    btns = ttk.Frame(frm)
    btns.pack(fill="x", side="bottom")

    def do_install() -> None:
        dest = Path(dest_var.get().strip())
        if not dest_var.get().strip():
            messagebox.showwarning("CtrlNote", "Укажите папку установки")
            return
        try:
            status_var.set("Закройте CtrlNote, если он запущен…")
            root.update_idletasks()
            exe = install(
                dest,
                desktop=desktop_var.get(),
                start_menu=start_var.get(),
                autostart=auto_var.get(),
                progress=lambda m: (status_var.set(m), root.update_idletasks()),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("CtrlNote", f"Ошибка установки:\n{exc}")
            status_var.set("Ошибка")
            return

        if messagebox.askyesno("CtrlNote", "Установка завершена.\nЗапустить сейчас?"):
            os.startfile(str(exe))  # noqa: S606
        root.destroy()

    ttk.Button(btns, text="Выход", command=root.destroy).pack(side="right")
    ttk.Button(btns, text="Установить", command=do_install).pack(side="right", padx=(0, 8))

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
