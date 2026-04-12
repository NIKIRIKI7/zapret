from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import sys
import time

from config import APP_VERSION, IS_WINDOWS, IS_LINUX
from log import log
from startup.admin_check import is_admin
from utils import run_hidden


def _show_message_box(title: str, message: str, *, error: bool = False) -> None:
    """Показывает сообщение — platform-aware.
    
    Windows: ctypes.windll MessageBoxW
    Linux: Qt QMessageBox (если QApplication существует) или print
    """
    if IS_WINDOWS:
        import ctypes
        icon = 0x10 if error else 0x40  # MB_ICONERROR or MB_ICONINFORMATION
        try:
            ctypes.windll.user32.MessageBoxW(None, message, title, icon)
        except Exception:
            print(f"[{title}] {message}")
    else:
        # Linux: try Qt, fallback to print
        try:
            from PyQt6.QtWidgets import QMessageBox, QApplication
            app = QApplication.instance()
            if app is not None:
                icon = QMessageBox.Critical if error else QMessageBox.Information
                msg_box = QMessageBox()
                msg_box.setIcon(icon)
                msg_box.setWindowTitle(title)
                msg_box.setText(message)
                msg_box.exec()
                return
        except Exception:
            pass
        print(f"[{title}] {message}")


def handle_update_mode(argv: list[str] | None = None) -> None:
    args = list(argv or sys.argv)
    if len(args) < 4:
        log("--update: недостаточно аргументов", "❌ ERROR")
        return

    old_exe, new_exe = args[2], args[3]

    for _ in range(10):
        if not os.path.exists(old_exe) or os.access(old_exe, os.W_OK):
            break
        time.sleep(0.5)

    try:
        shutil.copy2(new_exe, old_exe)
        run_hidden([old_exe])
        log("Файл обновления применён", "INFO")
    except Exception as exc:
        log(f"Ошибка в режиме --update: {exc}", "❌ ERROR")
    finally:
        try:
            os.remove(new_exe)
        except FileNotFoundError:
            pass


def shell_bootstrap(argv: list[str] | None = None) -> bool:
    args = list(argv or sys.argv)

    if "--version" in args:
        _show_message_box("Zapret – версия", APP_VERSION)
        sys.exit(0)

    if "--update" in args and len(args) > 3:
        handle_update_mode(args)
        sys.exit(0)

    start_in_tray = "--tray" in args

    # Linux: check root via is_admin() (uses geteuid), no ShellExecuteW needed
    if not is_admin():
        if IS_LINUX:
            # admin_check.ensure_admin_rights() already handles pkexec + sys.exit(0)
            from startup.admin_check import ensure_admin_rights
            ensure_admin_rights()
            # If we get here, pkexec failed or was cancelled
            _show_message_box("Zapret", "Не удалось получить права root.", error=True)
            sys.exit(1)

        if IS_WINDOWS:
            params = subprocess.list2cmdline(list(args[1:]))
            import ctypes
            shell_exec_result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                sys.executable,
                params,
                None,
                1,
            )
            if int(shell_exec_result) <= 32:
                _show_message_box("Zapret", "Не удалось запросить права администратора.", error=True)
            sys.exit(0)

    # Single instance check (platform-aware: Mutex on Windows, fcntl on Linux)
    from startup.single_instance import create_mutex, release_mutex
    from startup.ipc_manager import IPCManager

    mutex_handle, already_running = create_mutex("ZapretSingleInstance")
    if already_running:
        ipc = IPCManager()
        if ipc.send_show_command():
            log("Отправлена команда показать окно запущенному экземпляру", "INFO")
        else:
            _show_message_box(
                "Zapret",
                "Экземпляр Zapret уже запущен, но не удалось показать окно!",
            )
        sys.exit(0)

    atexit.register(lambda: release_mutex(mutex_handle))
    return bool(start_in_tray)
