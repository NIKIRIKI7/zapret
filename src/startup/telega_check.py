# startup/telega_check.py
"""
Обнаружение поддельного клиента «Telega Desktop» —
неофициальная модификация Telegram, которая может перехватывать переписку.
"""
from __future__ import annotations
import os

from app_notifications import advisory_notification, notification_action


def _check_telega_installed() -> str | None:
    """
    Проверяет наличие «Telega Desktop» в системе.

    Returns:
        Путь к обнаруженному файлу/папке, или None если не найдено.
    """
    try:
        appdata_roaming = os.environ.get("APPDATA", "")
        appdata_local = os.environ.get("LOCALAPPDATA", "")
        user_profile = os.environ.get("USERPROFILE", "")

        # Папки и exe, которые может создать Telega Desktop
        check_paths = []

        for base in (appdata_roaming, appdata_local):
            if not base:
                continue
            check_paths += [
                os.path.join(base, "Telega Desktop", "Telega.exe"),
                os.path.join(base, "Telega Desktop"),
                os.path.join(base, "TelegaDesktop", "Telega.exe"),
                os.path.join(base, "TelegaDesktop"),
            ]

        # Ярлыки в меню «Пуск»
        if appdata_roaming:
            start_menu = os.path.join(
                appdata_roaming, "Microsoft", "Windows", "Start Menu", "Programs"
            )
            check_paths += [
                os.path.join(start_menu, "Telega Desktop", "Telega.lnk"),
                os.path.join(start_menu, "Telega Desktop"),
                os.path.join(start_menu, "TelegaDesktop", "Telega.lnk"),
                os.path.join(start_menu, "TelegaDesktop"),
            ]

        # Ярлык на рабочем столе
        if user_profile:
            desktop = os.path.join(user_profile, "Desktop")
            check_paths += [
                os.path.join(desktop, "Telega.lnk"),
                os.path.join(desktop, "Telega Desktop.lnk"),
            ]

        # Program Files (на случай системной установки)
        for pf in (r"C:\Program Files", r"C:\Program Files (x86)"):
            check_paths += [
                os.path.join(pf, "Telega Desktop", "Telega.exe"),
                os.path.join(pf, "Telega Desktop"),
            ]

        for path in check_paths:
            if os.path.exists(path):
                return path

        # Дополнительно: проверяем запущенные процессы
        try:
            import psutil
            for proc in psutil.process_iter(["name"]):
                try:
                    name = proc.info["name"]
                    if name and name.lower() == "telega.exe":
                        return f"Процесс: {name}"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

        return None
    except Exception:
        return None


def _check_telega_warning_disabled() -> bool:
    """Проверяет, отключено ли предупреждение о Telega в реестре."""
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\ZapretReg2", 0, winreg.KEY_READ
        ) as key:
            value, _ = winreg.QueryValueEx(key, "DisableTelegaWarning")
            return value == 1
    except Exception:
        return False


def _set_telega_warning_disabled(disabled: bool) -> None:
    """Сохраняет в реестре настройку отключения предупреждения о Telega."""
    try:
        import winreg
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, r"Software\ZapretReg2", 0, winreg.KEY_WRITE
        ) as key:
            winreg.SetValueEx(key, "DisableTelegaWarning", 0, winreg.REG_DWORD, 1 if disabled else 0)
    except Exception:
        pass


def disable_telega_warning_forever() -> None:
    """Отключает дальнейшие предупреждения о Telega Desktop."""
    _set_telega_warning_disabled(True)


def build_telega_notification(found_path: str = "") -> dict | None:
    """Возвращает нормализованное неблокирующее событие для центра уведомлений."""
    if _check_telega_warning_disabled():
        return None

    path_line = f"\nОбнаружено: {found_path}" if found_path else ""
    return advisory_notification(
        level="error",
        title="Обнаружена Telega Desktop",
        content=(
            "Обнаружена программа Telega Desktop.\n"
            "Это неофициальная модификация Telegram, которая может читать переписку."
            f"{path_line}\n"
            "Рекомендуется удалить её, поставить официальный Telegram и завершить сторонние сессии."
        ),
        source="deferred.telega",
        queue="startup",
        duration=20000,
        dedupe_key="deferred.telega",
        buttons=[
            notification_action(
                "open_url",
                "Открыть сайт Telegram",
                value="https://desktop.telegram.org",
            ),
            notification_action("disable_telega_warning", "Не напоминать"),
        ],
    )
