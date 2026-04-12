# single_instance.py — Cross-platform single instance management

import sys

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

if IS_WINDOWS:
    import ctypes

    ERROR_ALREADY_EXISTS = 183
    _kernel32 = ctypes.windll.kernel32

    def create_mutex(name: str):
        """
        Пытаемся создать именованный mutex (Windows).
        Возвращает (handle, already_running: bool)
        """
        _kernel32.SetLastError(0)
        handle = _kernel32.CreateMutexW(None, False, name)
        last_error = _kernel32.GetLastError()
        already_running = last_error == ERROR_ALREADY_EXISTS

        if not handle:
            return None, False

        return handle, already_running

    def release_mutex(handle):
        if handle:
            _kernel32.ReleaseMutex(handle)
            _kernel32.CloseHandle(handle)

else:
    # Linux: use fcntl file locking
    import os
    import fcntl

    _lock_file = None

    def create_mutex(name: str):
        """
        Пытаемся создать блокировку файла (Linux).
        Возвращает (file_handle, already_running: bool)
        """
        global _lock_file
        lock_path = os.path.join(
            os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
            f"{name}.lock"
        )
        try:
            _lock_file = open(lock_path, 'w')
            # LOCK_EX - эксклюзивная, LOCK_NB - не блокирующая
            fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return _lock_file, False
        except BlockingIOError:
            return None, True
        except OSError:
            return None, True

    def release_mutex(handle):
        global _lock_file
        if handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_UN)
                handle.close()
                if _lock_file and hasattr(_lock_file, 'name'):
                    try:
                        os.remove(_lock_file.name)
                    except OSError:
                        pass
            except Exception:
                pass
            finally:
                _lock_file = None
