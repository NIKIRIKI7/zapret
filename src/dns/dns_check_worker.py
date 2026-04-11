from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class DNSCheckWorker(QObject):
    """Worker для выполнения DNS проверки в отдельном потоке."""

    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def is_stop_requested(self) -> bool:
        return self._stop_requested

    def run(self):
        try:
            from dns_checker import DNSChecker

            checker = DNSChecker()
            results = checker.check_dns_poisoning(
                log_callback=self.update_signal.emit,
                should_stop=self.is_stop_requested,
            )
            self.finished_signal.emit(results)
        except Exception as e:
            if not self._stop_requested:
                self.update_signal.emit(f"❌ Ошибка: {str(e)}")
            self.finished_signal.emit({})
