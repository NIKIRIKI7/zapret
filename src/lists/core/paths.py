"""Канонические пути для файлов списков рядом с программой."""

from __future__ import annotations

import os

from config.config import MAIN_DIRECTORY


def get_lists_dir() -> str:
    """Возвращает папку `lists` рядом с программой."""
    return os.path.join(MAIN_DIRECTORY, "lists")

def get_list_path(file_name: str) -> str:
    """Возвращает путь файла из папки `lists`."""
    return os.path.join(get_lists_dir(), file_name)


def get_list_base_path(list_name: str) -> str:
    """Возвращает путь файла `<name>.base.txt` из папки `lists`."""
    return get_list_path(f"{list_name}.base.txt")


def get_list_user_path(list_name: str) -> str:
    """Возвращает путь файла `<name>.user.txt` из папки `lists`."""
    return get_list_path(f"{list_name}.user.txt")


def get_list_final_path(list_name: str) -> str:
    """Возвращает путь итогового файла `<name>.txt` из папки `lists`."""
    return get_list_path(f"{list_name}.txt")
