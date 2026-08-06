"""
Мастер установки CtrlNote.

Распаковывает программу в LocalAppData и создаёт ярлыки на рабочем столе / в Пуске.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


APP_NAME = "CtrlNote"
DEFAULT_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME


def _safe_extractall(zf: zipfile.ZipFile, dest: Path) -> None:
    """Распаковывает zip только внутрь папки установки (защита от Zip Slip)."""
    dest = dest.resolve()
    for info in zf.infolist():
        name = info.filename
        if not name or name.endswith("/"):
            # Записи-папки в zip — тоже проверяем
            rel = name.rstrip("/")
            if not rel:
                continue
        else:
            rel = name
        member = Path(rel)
        if member.is_absolute() or ".." in member.parts:
            raise ValueError(f"Unsafe zip member rejected: {name!r}")
        target = (dest / member).resolve()
        try:
            target.relative_to(dest)
        except ValueError as exc:
            raise ValueError(f"Zip member escapes install dir: {name!r}") from exc
    zf.extractall(dest)


def _payload_zip() -> Path:
    """Находит app.zip с файлами программы (в setup.exe или рядом)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "app.zip"  # type: ignore[attr-defined]
    # В разработке: zip рядом с файлом или в dist/
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
    """Создаёт ярлык Windows (.lnk) через PowerShell."""
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


def _normalize_install_dest(dest: Path) -> Path:
    """Нормализует папку установки: всегда .../CtrlNote, без опасных корней."""
    dest = dest.expanduser()
    if dest.name.lower() != APP_NAME.lower():
        dest = dest / APP_NAME
    dest = dest.resolve()
    # Запрещаем слишком короткие пути (например C:\Users)
    if len(dest.parts) < 3:
        raise ValueError(
            f"Install folder is too high in the drive tree.\n"
            f"Choose a path like {DEFAULT_DIR}"
        )
    forbidden_names = {"windows", "system32", "program files", "program files (x86)"}
    if any(p.lower() in forbidden_names for p in dest.parts):
        raise ValueError("Cannot install into Windows system folders")
    return dest


def install(
    dest: Path,
    *,
    desktop: bool = True,
    start_menu: bool = True,
    autostart: bool = False,
    progress=None,
) -> Path:
    """Устанавливает CtrlNote в папку dest и создаёт ярлыки."""
    dest = _normalize_install_dest(dest)
    zpath = _payload_zip()

    def report(msg: str) -> None:
        if progress:
            progress(msg)

    report("Extracting…")
    if dest.exists():
        # Сохраняем старый config.json при переустановке
        cfg = dest / "config.json"
        cfg_backup = None
        if cfg.exists():
            # Временное имя бэкапа (не фиксированное)
            _fd, _tmp_name = tempfile.mkstemp(prefix="ctrlnote-cfg-", suffix=".json")
            os.close(_fd)
            cfg_backup = Path(_tmp_name)
            shutil.copy2(cfg, cfg_backup)
        shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True, exist_ok=True)
        if cfg_backup and cfg_backup.exists():
            shutil.copy2(cfg_backup, dest / "config.json")
            try:
                cfg_backup.write_bytes(b"\x00" * cfg_backup.stat().st_size)
            except OSError:
                pass
            cfg_backup.unlink(missing_ok=True)
    else:
        dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zpath, "r") as zf:
        _safe_extractall(zf, dest)

    exe = dest / "CtrlNote.exe"
    if not exe.exists():
        # В zip может быть вложенная папка CtrlNote/
        nested = dest / "CtrlNote" / "CtrlNote.exe"
        if nested.exists():
            # Расплющиваем структуру папок
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

    report("Shortcuts…")
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
        report("Autostart…")
        try:
            # Сначала ставим программу на место, потом включаем автозапуск
            sys.path.insert(0, str(dest))
            # Автозапуск через реестр и ярлык без импорта основного приложения:
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

    report("Done")
    return exe


def main() -> int:
    """Окно установщика: выбор папки и опций, кнопка «Установить»."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title("CtrlNote Setup")
    root.geometry("460x320")
    root.resizable(False, False)

    dest_var = tk.StringVar(value=str(DEFAULT_DIR))
    desktop_var = tk.BooleanVar(value=True)
    start_var = tk.BooleanVar(value=True)
    auto_var = tk.BooleanVar(value=True)
    status_var = tk.StringVar(value="Installs CtrlNote and creates shortcuts.")

    try:
        # Иконка окна, если есть рядом с setup
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
    ttk.Label(frm, text="Fast notes into Obsidian", foreground="#555").pack(anchor="w", pady=(0, 12))

    path_row = ttk.Frame(frm)
    path_row.pack(fill="x", pady=(0, 8))
    ttk.Label(path_row, text="Folder:").pack(side="left")
    ttk.Entry(path_row, textvariable=dest_var).pack(side="left", fill="x", expand=True, padx=6)

    def browse() -> None:
        chosen = filedialog.askdirectory(initialdir=dest_var.get())
        if chosen:
            dest_var.set(str(Path(chosen) / APP_NAME))

    ttk.Button(path_row, text="Browse", command=browse, width=8).pack(side="right")

    ttk.Checkbutton(frm, text="Desktop shortcut", variable=desktop_var).pack(anchor="w")
    ttk.Checkbutton(frm, text="Start menu shortcut", variable=start_var).pack(anchor="w")
    ttk.Checkbutton(frm, text="Start with Windows", variable=auto_var).pack(anchor="w")

    ttk.Label(frm, textvariable=status_var, foreground="#333").pack(anchor="w", pady=(16, 8))

    btns = ttk.Frame(frm)
    btns.pack(fill="x", side="bottom")

    def do_install() -> None:
        """Запускает установку по нажатию кнопки."""
        dest = Path(dest_var.get().strip())
        if not dest_var.get().strip():
            messagebox.showwarning("CtrlNote", "Choose an install folder")
            return
        try:
            status_var.set("Close CtrlNote if it is running…")
            root.update_idletasks()
            exe = install(
                dest,
                desktop=desktop_var.get(),
                start_menu=start_var.get(),
                autostart=auto_var.get(),
                progress=lambda m: (status_var.set(m), root.update_idletasks()),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("CtrlNote", f"Install failed:\n{exc}")
            status_var.set("Error")
            return

        if messagebox.askyesno("CtrlNote", "Installation complete.\nLaunch now?"):
            os.startfile(str(exe))  # noqa: S606
        root.destroy()

    ttk.Button(btns, text="Exit", command=root.destroy).pack(side="right")
    ttk.Button(btns, text="Install", command=do_install).pack(side="right", padx=(0, 8))

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
