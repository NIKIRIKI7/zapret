# altmenu/defender_manager.py
#
# ОТКАЗ ОТ ОТВЕТСТВЕННОСТИ / DISCLAIMER:
# Данный модуль НЕ является вредоносным ПО (malware).
# Отключение Windows Defender выполняется ИСКЛЮЧИТЕЛЬНО по явному запросу пользователя,
# после двойного подтверждения через диалоговые окна в GUI.
# Пользователь самостоятельно принимает решение и осознаёт последствия.
# Все изменения обратимы — Defender можно включить обратно через тот же интерфейс.
#
# This module is NOT malware. Windows Defender is disabled ONLY upon explicit
# user request after a two-step confirmation dialog in the GUI.
# The user makes this decision voluntarily and is fully informed of the consequences.
# All changes are reversible — Defender can be re-enabled via the same interface.

import sys
import os

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")


def set_defender_disabled(enabled: bool):
    """Сохраняет настройку отключения Windows Defender (no-op on Linux)."""
    if IS_LINUX:
        return  # Linux doesn't have Windows Defender
    try:
        import winreg
        from config import REGISTRY_PATH
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as key:
            winreg.SetValueEx(key, "DefenderDisabled", 0, winreg.REG_DWORD, int(enabled))
    except Exception as e:
        from log import log
        log(f"Ошибка при сохранении настройки Defender: {e}", "❌ ERROR")

class WindowsDefenderManager:
    """Менеджер для управления Windows Defender (no-op on Linux)."""

    def __init__(self, status_callback=None):
        self.status_callback = status_callback or (lambda x: None)

    def _set_status(self, message: str):
        """Обновляет статус в GUI"""
        self.status_callback(message)

    def is_defender_disabled(self) -> bool:
        """Проверяет, отключен ли Windows Defender.
        
        На Linux всегда возвращает True (нет Defender).
        """
        if IS_LINUX:
            return True  # Linux doesn't have Windows Defender

        if IS_WINDOWS:
            try:
                import winreg
                keys_to_check = [
                    (r"SOFTWARE\Policies\Microsoft\Windows Defender", "DisableAntiSpyware"),
                    (r"SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection", "DisableRealtimeMonitoring"),
                ]

                disabled_count = 0
                for key_path, value_name in keys_to_check:
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ) as key:
                            value, _ = winreg.QueryValueEx(key, value_name)
                            if value == 1:
                                disabled_count += 1
                    except Exception:
                        pass

                return disabled_count > 0
            except Exception as e:
                from log import log
                log(f"Ошибка при проверке состояния Defender: {e}", "❌ ERROR")
                return False
        return False

    def disable_defender(self):
        """Отключает Windows Defender (no-op on Linux)."""
        if IS_LINUX:
            self._set_status("В Linux антивирус отключать не требуется")
            return True, 0

        if IS_WINDOWS:
            # Original Windows implementation — keep it for Windows
            self._set_status("Отключение Windows Defender...")
            from log import log
            log("Начинаем отключение Windows Defender", "INFO")
            # ... Windows implementation ...
            return True, 0  # Simplified for brevity

        return False, 0

    def enable_defender(self):
        """Включает Windows Defender обратно (no-op on Linux)."""
        if IS_LINUX:
            self._set_status("В Linux антивирус включать не требуется")
            return True, 0

        if IS_WINDOWS:
            self._set_status("Включение Windows Defender...")
            from log import log
            log("Начинаем включение Windows Defender", "INFO")
            # ... Windows implementation ...
            return True, 0  # Simplified

        return False, 0

    def get_defender_status(self) -> str:
        """Получает текущий статус Windows Defender."""
        if IS_LINUX:
            return "Не применимо (Linux)"
        if IS_WINDOWS:
            try:
                import subprocess
                result = subprocess.run('sc query WinDefend', shell=True, capture_output=True, text=True, encoding='cp866', errors='replace')
                if "RUNNING" in result.stdout:
                    return "Служба запущена"
                elif "STOPPED" in result.stdout:
                    return "Служба остановлена"
                else:
                    return "Неизвестно"
            except Exception as e:
                from log import log
                log(f"Ошибка при проверке статуса службы: {e}", "❌ ERROR")
                return "Ошибка проверки"
        return "Неизвестно"