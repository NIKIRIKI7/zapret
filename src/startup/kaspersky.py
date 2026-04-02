# startup/kaspersky.py
from __future__ import annotations
import os
import sys

from app_notifications import advisory_notification, notification_action


def _resolve_kaspersky_paths() -> tuple[str, str]:
    """Возвращает путь к exe и рабочую папку приложения."""
    if getattr(sys, "frozen", False):
        exe_path = os.path.abspath(sys.executable)
        base_dir = os.path.dirname(exe_path)
    else:
        exe_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "zapret.pyw")
        )
        base_dir = os.path.dirname(exe_path)
    return exe_path, base_dir

def _check_kaspersky_antivirus() -> bool:
    """
    Проверяет наличие антивируса Касперского в системе.
    
    Returns:
        bool: True если Касперский обнаружен, False если нет
    """
    #return True # для тестирования
    try:
        import subprocess
        import os
        
        # Проверяем наличие процессов Касперского
        kaspersky_processes = [
            'avp.exe', 'kavfs.exe', 'klnagent.exe', 'ksde.exe',
            'kavfswp.exe', 'kavfswh.exe', 'kavfsslp.exe'
        ]
        
        # Получаем список запущенных процессов через psutil (быстрее и надежнее)
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name']
                    if proc_name and proc_name.lower() in kaspersky_processes:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        
        # Проверяем папки установки Касперского
        kaspersky_paths = [
            r'C:\Program Files\Kaspersky Lab',
            r'C:\Program Files (x86)\Kaspersky Lab',
            r'C:\Program Files\Kaspersky Security',
            r'C:\Program Files (x86)\Kaspersky Security'
        ]
        
        for path in kaspersky_paths:
            if os.path.exists(path) and os.path.isdir(path):
                try:
                    # Проверяем, что папка не пустая
                    dir_contents = os.listdir(path)
                    if dir_contents:
                        # Дополнительно проверяем наличие исполняемых файлов или подпапок
                        for item in dir_contents:
                            item_path = os.path.join(path, item)
                            if os.path.isdir(item_path) or item.lower().endswith(('.exe', '.dll')):
                                return True
                except (PermissionError, OSError):
                    # Если нет доступа к папке, но она существует - считаем что Касперский есть
                    return True
        
        # Если ни один процесс не найден и папки пустые/не найдены, считаем что Касперского нет
        return False
        
    except Exception:
        # В случае ошибки считаем, что Касперского нет
        return False

def _check_kaspersky_warning_disabled():
    """
    Проверяет, отключено ли предупреждение о Kaspersky в реестре.
    
    Returns:
        bool: True если предупреждение отключено, False если нет
    """
    try:
        import winreg
        
        # Путь к ключу реестра
        key_path = r"Software\ZapretReg2"
        value_name = "DisableKasperskyWarning"
        
        # Пытаемся открыть ключ
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                return value == 1
        except (FileNotFoundError, OSError):
            return False
            
    except ImportError:
        # Если winreg недоступен (не Windows), возвращаем False
        return False

def _set_kaspersky_warning_disabled(disabled: bool):
    """
    Сохраняет в реестре настройку отключения предупреждения о Kaspersky.
    
    Args:
        disabled: True для отключения предупреждения, False для включения
    """
    try:
        import winreg
        
        # Путь к ключу реестра
        key_path = r"Software\ZapretReg2"
        value_name = "DisableKasperskyWarning"
        
        # Создаем или открываем ключ
        try:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, value_name, 0, winreg.REG_DWORD, 1 if disabled else 0)
        except Exception as e:
            print(f"Ошибка при записи в реестр: {e}")
            
    except ImportError:
        # Если winreg недоступен (не Windows), ничего не делаем
        pass


def disable_kaspersky_warning_forever() -> None:
    """Отключает дальнейшие предупреждения о Kaspersky."""
    _set_kaspersky_warning_disabled(True)


def build_kaspersky_notification() -> dict | None:
    """Возвращает нормализованное неблокирующее событие для центра уведомлений."""
    if _check_kaspersky_warning_disabled():
        return None

    exe_path, base_dir = _resolve_kaspersky_paths()
    return advisory_notification(
        level="warning",
        title="Обнаружен Kaspersky",
        content=(
            "Обнаружен антивирус Kaspersky.\n"
            "Чтобы Zapret работал стабильнее, лучше добавить программу в исключения.\n"
            f"Папка: {base_dir}\n"
            f"Файл: {exe_path}\n"
            "Без исключения антивирус может мешать запуску и работе программы."
        ),
        source="startup.kaspersky",
        queue="startup",
        duration=20000,
        dedupe_key="startup.kaspersky",
        buttons=[
            notification_action(
                "copy_text",
                "Копировать папку",
                value=base_dir,
                feedback_label="Путь к папке",
            ),
            notification_action(
                "copy_text",
                "Копировать exe",
                value=exe_path,
                feedback_label="Путь к exe",
            ),
            notification_action("disable_kaspersky_warning", "Не напоминать"),
        ],
    )
