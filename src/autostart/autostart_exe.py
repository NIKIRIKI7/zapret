"""
Канонический автозапуск приложения.

Windows: Планировщик заданий (schtasks)
Linux: XDG Autostart (.desktop file)
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any, Callable, Optional

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

# Linux: use XDG autostart
if IS_LINUX:
    from autostart.xdg_autostart import get_xdg_autostart_manager


def _log(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("[%H:%M:%S]")
    print(f"{timestamp} [{level}] {message}")


# Linux: delegate to XDG autostart
if IS_LINUX:
    def is_autostart_enabled() -> bool:
        """Check if XDG autostart is enabled."""
        return get_xdg_autostart_manager().is_enabled()

    def enable_autostart(status_callback: Optional[Callable] = None) -> bool:
        """Enable XDG autostart."""
        success = get_xdg_autostart_manager().enable()
        if status_callback:
            status_callback("Autostart enabled" if success else "Failed to enable autostart")
        return success

    def disable_autostart(status_callback: Optional[Callable] = None) -> bool:
        """Disable XDG autostart."""
        success = get_xdg_autostart_manager().disable()
        if status_callback:
            status_callback("Autostart disabled" if success else "Failed to disable autostart")
        return success

else:
    # Windows: use schtasks
    from utils import get_system_exe

    TASK_NAME = "ZapretGUI_AutoStart"

    def _run_schtasks(args: list[str], *, check_output: bool = True) -> Any:
        cmd = [get_system_exe("schtasks.exe")] + args

        for encoding in ("utf-8", "cp866", "cp1251"):
            try:
                return subprocess.run(
                    cmd,
                    capture_output=check_output,
                    text=True,
                    encoding=encoding,
                    errors="replace",
                    timeout=30,
                )
            except (UnicodeDecodeError, subprocess.TimeoutExpired):
                continue
            except Exception:
                continue

        try:
            return subprocess.run(cmd, capture_output=check_output, timeout=30)
        except Exception as exc:
            class ErrorResult:
                returncode = -1
                stdout = ""
                stderr = str(exc)

        return ErrorResult()

    def setup_autostart_for_exe(
        status_cb: Optional[Callable[[str], None]] = None,
    ) -> bool:
        def _status(message: str):
            if status_cb:
                status_cb(message)

        try:
            import subprocess
            from .autostart_remove import clear_autostart_task

            exe_path = sys.executable
            _log("Включаем канонический автозапуск GUI", "INFO")

            # Перед созданием новой задачи убираем только её текущую каноническую версию.
            clear_autostart_task(status_cb=_status)

            create_args = [
                "/Create",
                "/TN",
                TASK_NAME,
                "/TR",
                f'"{exe_path}" --tray',
                "/SC",
                "ONLOGON",
                "/RL",
                "HIGHEST",
                "/F",
            ]
            result = _run_schtasks(create_args)

            if result.returncode != 0:
                error_msg = getattr(result, "stderr", "Неизвестная ошибка")
                _log(f"Ошибка создания задачи автозапуска: {error_msg}", "❌ ERROR")
                _status("Не удалось создать задачу автозапуска")
                return False

            _log(f"Создана задача автозапуска: {TASK_NAME}", "INFO")
            _status("Автозапуск программы включён")
            return True
        except Exception as exc:
            _log(f"setup_autostart_for_exe: {exc}", "❌ ERROR")
            _status(f"Ошибка: {exc}")
            return False

    def is_autostart_enabled() -> bool:
        import subprocess
        try:
            result = _run_schtasks(["/Query", "/TN", TASK_NAME])
            return result.returncode == 0
        except Exception:
            return False
