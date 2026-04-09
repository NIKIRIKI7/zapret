from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from log import log


class AutostartCheckWorker(QThread):
    """Быстрая фоновая проверка статуса автозапуска."""

    finished = pyqtSignal(bool)

    def run(self):
        try:
            result = self._check_autostart()
            self.finished.emit(result)
        except Exception as e:
            log(f"AutostartCheckWorker error: {e}", "WARNING")
            self.finished.emit(False)

    def _check_autostart(self) -> bool:
        try:
            from autostart.registry_check import AutostartRegistryChecker

            return bool(AutostartRegistryChecker.is_autostart_enabled())
        except Exception:
            return False
