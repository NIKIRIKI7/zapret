"""
Утилита для остановки процессов.
Windows: через Windows API + psutil
Linux: через os.kill / pkill
"""

import os
import sys
try:
    import psutil  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - local test environments may not ship psutil
    class _PsutilStub:
        class NoSuchProcess(Exception):
            pass

        class AccessDenied(Exception):
            pass

        class TimeoutExpired(Exception):
            pass

        @staticmethod
        def process_iter(*_args, **_kwargs):
            return []

        class Process:
            def __init__(self, *_args, **_kwargs):
                raise _PsutilStub.NoSuchProcess()

    psutil = _PsutilStub()
from log import log
from typing import List, Optional

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    # Windows API константы
    PROCESS_TERMINATE = 0x0001
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SYNCHRONIZE = 0x00100000

    # WaitForSingleObject константы
    WAIT_OBJECT_0 = 0x00000000
    WAIT_TIMEOUT = 0x00000102
    WAIT_FAILED = 0xFFFFFFFF
    INFINITE = 0xFFFFFFFF

    if hasattr(ctypes, "windll"):
        kernel32 = ctypes.windll.kernel32

        OpenProcess = kernel32.OpenProcess
        OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        OpenProcess.restype = wintypes.HANDLE

        TerminateProcess = kernel32.TerminateProcess
        TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        TerminateProcess.restype = wintypes.BOOL

        WaitForSingleObject = kernel32.WaitForSingleObject
        WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        WaitForSingleObject.restype = wintypes.DWORD

        CloseHandle = kernel32.CloseHandle
        CloseHandle.argtypes = [wintypes.HANDLE]
        CloseHandle.restype = wintypes.BOOL
    else:  # pragma: no cover - import safety for non-Windows environments
        kernel32 = None
        OpenProcess = None
        TerminateProcess = None
        WaitForSingleObject = None
        CloseHandle = None
else:
    # Linux stubs
    kernel32 = None
    OpenProcess = None
    TerminateProcess = None
    WaitForSingleObject = None
    CloseHandle = None


def kill_process_by_pid(pid: int, force: bool = True, wait_timeout_ms: int = 3000) -> bool:
    """
    Завершает процесс по PID.
    
    Windows: через Windows API с fallback на psutil
    Linux: через os.kill / signal
    """
    # Linux: use os.kill
    if IS_LINUX:
        import signal
        try:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
            log(f"✅ Процесс PID={pid} завершён сигналом {sig.name}", "DEBUG")
            return True
        except ProcessLookupError:
            log(f"Процесс PID={pid} уже завершён", "DEBUG")
            return True
        except PermissionError:
            log(f"❌ Нет прав для завершения процесса PID={pid} (требуются права root)", "WARNING")
            return False
        except Exception as e:
            log(f"❌ Ошибка завершения процесса PID={pid}: {e}", "WARNING")
            return False

    # Windows: сначала пробуем через Win API с расширенными правами
    try:
        if OpenProcess is None or TerminateProcess is None or WaitForSingleObject is None or CloseHandle is None:
            raise RuntimeError("WinAPI unavailable")
        # Открываем процесс с максимальными правами
        h_process = OpenProcess(
            PROCESS_TERMINATE | PROCESS_QUERY_INFORMATION | SYNCHRONIZE,
            False,
            pid
        )

        if h_process:
            try:
                # Завершаем процесс (код выхода = 1)
                exit_code = 1
                result = TerminateProcess(h_process, exit_code)

                if result:
                    # Ждём реального завершения процесса
                    wait_result = WaitForSingleObject(h_process, wait_timeout_ms)

                    if wait_result == WAIT_OBJECT_0:
                        log(f"✅ Процесс PID={pid} завершён через Win API (подтверждено)", "DEBUG")
                        return True
                    elif wait_result == WAIT_TIMEOUT:
                        log(f"⚠ Процесс PID={pid}: TerminateProcess успешен, но процесс не завершился за {wait_timeout_ms}мс", "WARNING")
                        # Не возвращаем True - попробуем через psutil
                    else:
                        log(f"⚠ Процесс PID={pid}: WaitForSingleObject вернул {wait_result}", "WARNING")

            finally:
                # Всегда закрываем handle
                CloseHandle(h_process)

    except Exception as e:
        log(f"Win API не сработал для PID={pid}: {e}", "DEBUG")

    # Fallback на psutil (работает с любыми привилегиями)
    try:
        proc = psutil.Process(pid)
        proc_name = proc.name()

        if force:
            proc.kill()  # SIGKILL
        else:
            proc.terminate()  # SIGTERM

        # Ждём завершения через psutil
        try:
            proc.wait(timeout=wait_timeout_ms / 1000)
            log(f"✅ Процесс {proc_name} (PID={pid}) завершён через psutil (подтверждено)", "DEBUG")
            return True
        except psutil.TimeoutExpired:
            log(f"⚠ Процесс {proc_name} (PID={pid}) не завершился за {wait_timeout_ms}мс", "WARNING")
            return False

    except psutil.NoSuchProcess:
        log(f"Процесс PID={pid} уже завершён", "DEBUG")
        return True
    except psutil.AccessDenied:
        log(f"❌ Нет прав для завершения процесса PID={pid} (требуются права администратора)", "WARNING")
        return False
    except Exception as e:
        log(f"❌ Ошибка завершения процесса PID={pid}: {e}", "WARNING")
        return False


def kill_process_by_name(process_name: str, kill_all: bool = True) -> int:
    """
    Завершает все процессы с указанным именем.
    
    Windows: через psutil
    Linux: через pkill
    """
    if IS_LINUX:
        import subprocess
        try:
            # pkill -f matches against full command line
            cmd = ['pkill', '-9', '-f', process_name]
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            if result.returncode == 0:
                log(f"✅ Завершено процессов {process_name} через pkill", "INFO")
                return 1
            return 0
        except FileNotFoundError:
            # pkill not available, fallback to psutil
            pass
        except Exception as e:
            log(f"Ошибка pkill для {process_name}: {e}", "WARNING")

    killed_count = 0
    process_name_lower = process_name.lower()

    try:
        # Ищем все процессы с указанным именем через psutil
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_name = proc.info['name']
                if proc_name and proc_name.lower() == process_name_lower:
                    pid = proc.info['pid']

                    if kill_process_by_pid(pid):
                        killed_count += 1

                        if not kill_all:
                            break

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception as e:
        log(f"Ошибка поиска процесса {process_name}: {e}", "WARNING")

    if killed_count > 0:
        log(f"Завершено {killed_count} процессов {process_name}", "INFO")
    else:
        log(f"Процессы {process_name} не найдены или уже завершены", "DEBUG")

    return killed_count


def kill_winws_all(max_retries: int = 3, retry_delay: float = 0.5) -> bool:
    """
    Завершает все процессы winws/nfqws.
    """
    import time

    # Platform-specific process names
    if IS_LINUX:
        process_names = ["nfqws", "nfqws2"]
    else:
        process_names = ["winws.exe", "winws2.exe"]

    for attempt in range(1, max_retries + 1):
        total_killed = 0

        for proc_name in process_names:
            total_killed += kill_process_by_name(proc_name, kill_all=True)

        if total_killed > 0:
            log(f"✅ Завершено {total_killed} процессов (попытка {attempt})", "INFO")

        # Проверяем, что процессы действительно завершены
        time.sleep(0.2)

        remaining = []
        for proc_name in process_names:
            remaining.extend(get_process_pids(proc_name))

        if not remaining:
            if total_killed > 0:
                log(f"✅ Всего завершено {total_killed} процессов (подтверждено)", "INFO")
            else:
                log("Процессы не найдены", "DEBUG")
            return True

        # Есть ещё живые процессы
        remaining_count = len(remaining)
        log(f"⚠ Осталось {remaining_count} процессов после попытки {attempt}", "WARNING")

        if attempt < max_retries:
            log(f"Повторная попытка через {retry_delay}с...", "DEBUG")
            time.sleep(retry_delay)

    # После всех попыток ещё раз проверяем
    remaining = []
    for proc_name in process_names:
        remaining.extend(get_process_pids(proc_name))

    if remaining:
        log(f"❌ Не удалось завершить процессы: PIDs={remaining}", "ERROR")
        return False

    return True


def is_process_running(process_name: str) -> bool:
    """
    Быстрая проверка запущен ли процесс.
    """
    if IS_LINUX:
        import subprocess
        try:
            result = subprocess.run(['pgrep', '-f', process_name], 
                                    capture_output=True, timeout=3)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Fallback to psutil
            pass

    process_name_lower = process_name.lower()

    try:
        for proc in psutil.process_iter(['name']):
            try:
                proc_name = proc.info['name']
                if proc_name and proc_name.lower() == process_name_lower:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        log(f"Ошибка проверки процесса {process_name}: {e}", "DEBUG")

    return False


def get_process_pids(process_name: str) -> List[int]:
    """
    Возвращает список PID всех процессов с указанным именем.
    
    Args:
        process_name: Имя процесса
        
    Returns:
        Список PID процессов
    """
    pids = []
    process_name_lower = process_name.lower()
    
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_name = proc.info['name']
                if proc_name and proc_name.lower() == process_name_lower:
                    pids.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        log(f"Ошибка получения PID {process_name}: {e}", "DEBUG")
    
    return pids


def kill_process_tree(pid: int) -> bool:
    """
    Завершает процесс и все его дочерние процессы.

    Args:
        pid: ID родительского процесса

    Returns:
        True если процесс завершён
    """
    try:
        parent = psutil.Process(pid)

        # Сначала завершаем дочерние процессы
        children = parent.children(recursive=True)
        for child in children:
            try:
                kill_process_by_pid(child.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Затем завершаем родительский процесс
        return kill_process_by_pid(pid)

    except psutil.NoSuchProcess:
        log(f"Процесс PID={pid} уже завершён", "DEBUG")
        return False
    except Exception as e:
        log(f"Ошибка завершения дерева процессов PID={pid}: {e}", "WARNING")
        return False


def get_taskkill_path() -> str:
    """
    Получает полный путь к taskkill.exe.
    Ищет в System32 на диске где установлена Windows.

    Returns:
        Полный путь к taskkill.exe или 'taskkill' если не найден
    """
    import os

    # 1. Через переменную среды SystemRoot
    sys_root = os.getenv("SystemRoot")
    if sys_root:
        taskkill_path = os.path.join(sys_root, "System32", "taskkill.exe")
        if os.path.exists(taskkill_path):
            return taskkill_path

    # 2. Через Win API GetSystemWindowsDirectoryW
    try:
        GetSystemWindowsDirectoryW = ctypes.windll.kernel32.GetSystemWindowsDirectoryW
        GetSystemWindowsDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.DWORD]
        GetSystemWindowsDirectoryW.restype = wintypes.DWORD

        buf = ctypes.create_unicode_buffer(260)
        if GetSystemWindowsDirectoryW(buf, len(buf)):
            taskkill_path = os.path.join(buf.value, "System32", "taskkill.exe")
            if os.path.exists(taskkill_path):
                return taskkill_path
    except Exception:
        pass

    # 3. Fallback - просто taskkill (надеемся что в PATH)
    return "taskkill"


def force_kill_via_taskkill(process_name: str) -> bool:
    """
    Принудительное завершение процесса через taskkill /F /T.
    Используется как последняя мера когда Win API и psutil не справились.

    Args:
        process_name: Имя процесса (например "winws2.exe")

    Returns:
        True если команда выполнена успешно
    """
    import subprocess

    taskkill_exe = get_taskkill_path()

    try:
        result = subprocess.run(
            [taskkill_exe, '/F', '/T', '/IM', process_name],
            capture_output=True,
            text=True,
            encoding='cp866',
            creationflags=0x08000000 if IS_WINDOWS else 0,  # CREATE_NO_WINDOW
            timeout=10
        )

        if result.returncode == 0:
            log(f"✅ Процесс {process_name} завершён через taskkill /F /T", "INFO")
            return True
        elif "не найден" in result.stderr.lower() or "not found" in result.stderr.lower():
            log(f"Процесс {process_name} не найден для taskkill", "DEBUG")
            return True  # Процесса нет - это успех
        else:
            log(f"taskkill для {process_name} вернул код {result.returncode}: {result.stderr}", "WARNING")
            return False

    except subprocess.TimeoutExpired:
        log(f"taskkill для {process_name} превысил таймаут", "WARNING")
        return False
    except Exception as e:
        log(f"Ошибка taskkill для {process_name}: {e}", "WARNING")
        return False


def kill_via_wmi(process_name: str) -> bool:
    """
    Завершение процесса через WMI (Windows Management Instrumentation).
    Работает когда другие методы не помогают.

    Args:
        process_name: Имя процесса (например "winws.exe")

    Returns:
        True если команда выполнена успешно
    """
    import subprocess

    try:
        # wmic process where name="winws.exe" delete
        result = subprocess.run(
            ['wmic', 'process', 'where', f'name="{process_name}"', 'delete'],
            capture_output=True,
            text=True,
            encoding='cp866',
            creationflags=0x08000000 if IS_WINDOWS else 0,  # CREATE_NO_WINDOW
            timeout=15
        )

        # wmic возвращает 0 даже если процесс не найден
        if "No Instance" in result.stdout or "нет экземпляров" in result.stdout.lower():
            log(f"WMI: процесс {process_name} не найден", "DEBUG")
            return True

        if result.returncode == 0:
            log(f"✅ Процесс {process_name} завершён через WMI", "INFO")
            return True
        else:
            log(f"WMI для {process_name} вернул код {result.returncode}: {result.stderr}", "DEBUG")
            return False

    except subprocess.TimeoutExpired:
        log(f"WMI для {process_name} превысил таймаут", "WARNING")
        return False
    except Exception as e:
        log(f"Ошибка WMI для {process_name}: {e}", "DEBUG")
        return False


def kill_winws_force() -> bool:
    """
    Агрессивное завершение всех процессов winws/nfqws.
    """
    import time

    # Platform-specific process names
    if IS_LINUX:
        process_names = ["nfqws", "nfqws2"]
    else:
        process_names = ["winws.exe", "winws2.exe"]

    # Quick check - exit if no processes running
    all_pids = []
    for proc_name in process_names:
        all_pids.extend(get_process_pids(proc_name))

    if not all_pids:
        log("Процессы не найдены", "DEBUG")
        return True

    # 1. Try normal kill
    kill_winws_all(max_retries=2, retry_delay=0.3)

    # 2. Check remaining
    remaining = []
    for proc_name in process_names:
        remaining.extend(get_process_pids(proc_name))

    if not remaining:
        return True

    # 3. Linux: try pkill -9 as fallback
    if IS_LINUX:
        import subprocess
        log(f"⚠ Осталось {len(remaining)} процессов, применяем pkill -9", "WARNING")
        for proc_name in process_names:
            try:
                subprocess.run(['pkill', '-9', '-f', proc_name], 
                               capture_output=True, timeout=5)
            except Exception:
                pass
        time.sleep(0.3)
    else:
        # Windows: try taskkill
        log(f"⚠ Осталось {len(remaining)} процессов, применяем taskkill", "WARNING")
        for proc_name in process_names:
            force_kill_via_taskkill(proc_name)
        time.sleep(0.3)

    # 4. Final check
    remaining = []
    for proc_name in process_names:
        remaining.extend(get_process_pids(proc_name))

    if remaining:
        log(f"❌ Не удалось завершить процессы: PIDs={remaining}", "ERROR")
        return False

    log("✅ Процессы завершены", "INFO")
    return True
