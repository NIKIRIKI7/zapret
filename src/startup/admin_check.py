# admin_utils.py - Cross-platform admin check
import os
import sys
from log import log

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")


def is_admin():
    """Проверяет, запущено ли приложение с правами администратора."""
    if IS_LINUX:
        return os.geteuid() == 0
    if IS_WINDOWS:
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False
    return False


def ensure_admin_rights():
    """Убеждается, что приложение запущено с правами администратора."""
    # Если уже есть права админа - просто возвращаем True
    if is_admin():
        log("✅ Приложение запущено с правами администратора", level="INFO")
        return True

    # Проверяем, не был ли уже сделан запрос на повышение прав
    if "--elevated" in sys.argv:
        if IS_LINUX:
            log("⚠️ Не удалось получить права root", level="⚠ WARNING")
            return False
        if IS_WINDOWS:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None,
                "Не удалось получить права администратора.\n"
                "Попробуйте запустить приложение от имени администратора вручную:\n\n"
                "1. Нажмите правой кнопкой на файле программы\n"
                "2. Выберите 'Запуск от имени администратора'",
                "Zapret - Ошибка получения прав",
                0x10  # MB_ICONERROR
            )
            return False

    log("⚠️ Приложение запущено БЕЗ прав администратора", level="⚠ WARNING")

    if IS_LINUX:
        # Linux: try pkexec (PolicyKit)
        try:
            import subprocess
            args = sys.argv[:] + ["--elevated"]
            # Запускаем через pkexec и выходим из текущего (не-root) процесса
            subprocess.Popen(["pkexec", sys.executable] + args)
            sys.exit(0)
        except Exception as e:
            log(f"Ошибка вызова pkexec: {e}", "ERROR")
            return False

    if IS_WINDOWS:
        import ctypes

        # Показываем диалог
        result = ctypes.windll.user32.MessageBoxW(
            None,
            "Zapret требует права администратора для корректной работы.\n\n"
            "Нажмите OK для перезапуска с правами администратора.",
            "Zapret - Требуются права администратора",
            0x41  # MB_OKCANCEL | MB_ICONINFORMATION
        )

        if result == 1:  # OK
            try:
                # Формируем параметры
                args = sys.argv[1:] + ["--elevated"]
                params = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)

                # Получаем путь к исполняемому файлу
                if getattr(sys, 'frozen', False):
                    exe_path = sys.executable
                else:
                    exe_path = sys.executable
                    script_path = os.path.abspath(sys.argv[0])
                    params = f'"{script_path}" {params}'

                log(f"Запуск с правами администратора: {exe_path} {params}", level="INFO")

                # ShellExecuteW для запуска с правами администратора
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    exe_path,
                    params,
                    None,
                    1  # SW_SHOWNORMAL
                )

                if ret > 32:
                    return False  # Сигнал для выхода из текущего процесса
                else:
                    ctypes.windll.user32.MessageBoxW(
                        None,
                        "Не удалось запустить приложение с правами администратора.\n"
                        "Возможно, UAC заблокировал запрос.",
                        "Zapret - Ошибка",
                        0x10  # MB_ICONERROR
                    )

            except Exception as e:
                log(f"Ошибка при запуске с правами администратора: {e}", level="❌ ERROR")
                ctypes.windll.user32.MessageBoxW(
                    None,
                    f"Ошибка при попытке получить права администратора:\n{str(e)}",
                    "Zapret - Ошибка",
                    0x10  # MB_ICONERROR
                )

    return False
