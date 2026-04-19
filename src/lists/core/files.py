"""Общие файловые helper-функции для списков."""

from __future__ import annotations

import os


def normalize_newlines(text: str) -> str:
    """Приводит переводы строк к `\\n` и добавляет финальный перевод строки."""
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    return normalized


def read_text_file(path: str) -> str:
    """Читает текстовый файл как UTF-8."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_text_file_safe(path: str) -> str | None:
    """Пытается прочитать текстовый файл и возвращает `None` при ошибке."""
    try:
        return read_text_file(path)
    except Exception:
        return None


def write_text_file(path: str, content: str) -> None:
    """Записывает текстовый файл в UTF-8 и создаёт родительскую папку при необходимости."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalize_newlines(content))


def ensure_user_file_exists(user_path: str, backup_path: str | None = None) -> tuple[bool, bool]:
    """Гарантирует наличие user-файла и при возможности восстанавливает его из backup.

    Возвращает:
    - `ok`: удалось ли подготовить файл;
    - `restored_from_backup`: был ли файл восстановлен из backup.
    """
    try:
        os.makedirs(os.path.dirname(user_path), exist_ok=True)

        if os.path.exists(user_path):
            return True, False

        if backup_path and os.path.exists(backup_path):
            content = read_text_file_safe(backup_path)
            if content is not None:
                write_text_file(user_path, content)
                return True, True

        write_text_file(user_path, "")
        return True, False
    except Exception:
        return False, False


def prepare_user_file(
    user_path: str,
    backup_path: str | None = None,
    *,
    restored_message: str | None = None,
    error_message: str | None = None,
    log_func=None,
) -> bool:
    """Готовит user-файл, при необходимости восстанавливает его из backup и пишет лог."""
    try:
        ok, restored = ensure_user_file_exists(user_path, backup_path)
        if restored and restored_message and log_func is not None:
            log_func(restored_message, "SUCCESS")
        return ok
    except Exception as exc:
        if error_message and log_func is not None:
            log_func(f"{error_message}: {exc}", "ERROR")
        return False


def sync_user_backup(user_path: str, backup_path: str | None = None) -> None:
    """Сохраняет сырое содержимое user-файла в backup-файл."""
    if not backup_path:
        return

    try:
        content = read_text_file_safe(user_path)
        if content is None:
            return
        write_text_file(backup_path, content)
    except Exception:
        pass
