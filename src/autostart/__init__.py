"""Автозапуск ZapretGUI через каноническую задачу `--tray`."""

from .autostart_exe import is_autostart_enabled, setup_autostart_for_exe
from .autostart_remove import clear_autostart_task

__all__ = [
    "setup_autostart_for_exe",
    "is_autostart_enabled",
    "clear_autostart_task",
]
