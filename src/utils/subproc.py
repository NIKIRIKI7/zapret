"""
run_hidden – единый «тихий» запуск процессов (без всплывающего окна)
Работает даже если вызывают с shell=True или передают строку команды.
"""

from __future__ import annotations
import os, subprocess, sys, shlex
from typing import Sequence, Union
from functools import lru_cache


import ctypes

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

# WinAPI функции для получения системных путей
if IS_WINDOWS and hasattr(ctypes, "windll"):
    _kernel32 = ctypes.windll.kernel32
else:
    _kernel32 = None


def get_system32_path() -> str:
    """
    Возвращает путь к System32 через WinAPI GetSystemDirectoryW (Windows).
    На Linux возвращает /usr/bin.
    """
    if _kernel32 is not None:
        buf = ctypes.create_unicode_buffer(260)
        length = _kernel32.GetSystemDirectoryW(buf, 260)
        if length > 0:
            return buf.value
    # Fallback через переменные окружения
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if system_root:
        return os.path.join(system_root, "System32")
    # Linux path
    return "/usr/bin"


@lru_cache(maxsize=1)
def get_windows_path() -> str:
    """
    Возвращает путь к Windows через WinAPI GetWindowsDirectoryW (Windows).
    На Linux возвращает '/'.
    """
    if _kernel32 is not None:
        buf = ctypes.create_unicode_buffer(260)
        length = _kernel32.GetWindowsDirectoryW(buf, 260)
        if length > 0:
            return buf.value
    return "/"


@lru_cache(maxsize=1)
def get_syswow64_path() -> str:
    """
    Возвращает путь к SysWOW64 (32-битные программы на 64-битной Windows).
    На Linux возвращает '/usr/lib32'.
    """
    win_path = get_windows_path()
    if win_path != "/":
        return os.path.join(win_path, "SysWOW64")
    return "/usr/lib32"


def get_system_exe(exe_name: str) -> str:
    """
    Возвращает полный путь к системному исполняемому файлу.
    Пример: get_system_exe("tasklist.exe") -> "D:\\Windows\\System32\\tasklist.exe"
    """
    return os.path.join(get_system32_path(), exe_name)

# Максимальный набор флагов для полного скрытия окон (Windows only).
# NOTE: `CREATE_NEW_CONSOLE` can cause a visible console window (or "ghost" artifacts)
# on some systems when combined with translucency/frameless Qt windows.
# We keep `CREATE_NO_WINDOW` + `DETACHED_PROCESS` for reliably hidden execution.
# На Linux эти флаги не используются.
if IS_WINDOWS:
    WIN_FLAGS = (
        (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | 0x00000008  # CREATE_BREAKAWAY_FROM_JOB
        )
    )
else:
    WIN_FLAGS = 0

WIN_OEM   = "cp866"
UTF8      = "utf-8"


def _default_encoding() -> str:
    return WIN_OEM if IS_WINDOWS else UTF8


def _hidden_startupinfo() -> subprocess.STARTUPINFO | None:
    """Создаёт STARTUPINFO для скрытия окна (только Windows)."""
    if not IS_WINDOWS or not hasattr(subprocess, "STARTUPINFO"):
        return None
    si = subprocess.STARTUPINFO()
    # Используем только существующие константы из subprocess
    si.dwFlags |= (subprocess.STARTF_USESHOWWINDOW |
                   subprocess.STARTF_USESTDHANDLES)
    si.wShowWindow = subprocess.SW_HIDE
    return si


def _prepare_cmd(cmd, use_shell: bool):
    """
    Если caller хочет shell=True / передал строку,
    превращаем это в ['cmd','/Q','/C', ...] + shell=False (Windows),
    чтобы всё равно прятать окно.
    На Linux не меняем команду.
    """
    if not IS_WINDOWS:
        return cmd, use_shell      # на Linux не меняем

    cmd_exe = get_system_exe("cmd.exe")

    if use_shell:
        if isinstance(cmd, str):
            return [cmd_exe, '/Q', '/C', cmd], False
        else:               # список + shell=True
            return [cmd_exe, '/Q', '/C', *cmd], False

    if isinstance(cmd, str):       # shell=False, но строка → тоже оборачиваем
        return [cmd_exe, '/Q', '/C', cmd], False

    return cmd, use_shell


def run_hidden(cmd: Union[str, Sequence[str]],
               *,
               wait: bool = False,
               capture_output: bool = False,
               timeout: int | None = None,
               text: bool | None = None,
               encoding: str | None = None,
               errors: str = "replace",
               shell: bool = False,
               cwd: str | None = None,
               env: dict | None = None,
               **kw):
    """
    Параметры совпадают с subprocess.run/Popen.
    На Windows shell=True игнорируется – команда оборачивается вручную.
    """

    # --- подготовка команды / shell ---
    cmd, shell = _prepare_cmd(cmd, shell)

    # --- Windows: прячем окно ---
    if IS_WINDOWS:
        kw.setdefault("creationflags", WIN_FLAGS)
        kw.setdefault("startupinfo", _hidden_startupinfo())
        
        # Если не захватываем вывод, перенаправляем в DEVNULL
        if not capture_output:
            kw.setdefault("stdin",  subprocess.DEVNULL)
            kw.setdefault("stdout", subprocess.DEVNULL)
            kw.setdefault("stderr", subprocess.DEVNULL)
        
        # Устанавливаем переменные окружения для скрытия окон дочерних процессов
        if env is None:
            env = os.environ.copy()
        else:
            env = env.copy()
        
        # Переменные для скрытия консолей
        env.update({
            '__COMPAT_LAYER': 'RunAsInvoker',
            'PYTHONWINDOWMODE': 'hide',
            'PROMPT': '$G',  # Минимальный prompt
            'COMSPEC': get_system_exe("cmd.exe"),  # Полный путь к cmd.exe
        })
        kw['env'] = env

    # --- добавляем cwd если указан ---
    if cwd:
        kw['cwd'] = cwd

    # --- нужно ли run() ---
    need_run = wait or capture_output
    if capture_output:
        need_run = True
        kw["stdout"] = subprocess.PIPE
        kw["stderr"] = subprocess.PIPE

    if need_run:
        kw["text"]     = text if text is not None else True
        kw["encoding"] = encoding or _default_encoding()
        kw["errors"]   = errors
        if timeout is not None:
            kw["timeout"] = timeout

    # --- запуск ---
    try:
        if need_run:
            return subprocess.run(cmd, shell=shell, **kw)
        else:
            return subprocess.Popen(cmd, shell=shell, **kw)
    except Exception as e:
        # Если не удалось с агрессивными флагами, пробуем с базовыми
        if IS_WINDOWS and "creationflags" in kw:
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            if need_run:
                return subprocess.run(cmd, shell=shell, **kw)
            else:
                return subprocess.Popen(cmd, shell=shell, **kw)
        raise
