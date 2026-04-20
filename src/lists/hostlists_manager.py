# lists/hostlists_manager.py
"""Менеджер hostlist-файлов.

Файлы в папке приложения (рядом с Zapret.exe):
- `lists/other.base.txt` : системная база (автоматически поддерживается приложением)
- `lists/other.user.txt` : пользовательский файл (редактируется пользователем)
- `lists/other.txt`      : итоговый файл для движка (base + user), генерируется автоматически

Примечание:
Поддерживается только новая модель:
- `other.base.txt` как системная база;
- `other.user.txt` как пользовательский файл;
- `other.txt` как автоматически собираемый итоговый файл для движка.
"""

from __future__ import annotations

import os

from log.log import log
from lists.core.builders import write_combined_file
from lists.core.embedded_defaults import get_other_base_text
from lists.core.files import (
    prepare_user_file,
    write_text_file,
)
from lists.core.paths import get_list_base_path, get_list_final_path, get_list_user_path

OTHER_PATH = get_list_final_path("other")
OTHER_BASE_PATH = get_list_base_path("other")
OTHER_USER_PATH = get_list_user_path("other")


def _fallback_base_domains() -> list[str]:
    return ["youtube.com", "googlevideo.com", "discord.com", "discord.gg"]


def _read_effective_entries(path: str) -> list[str]:
    """Reads non-empty lines excluding comments (#), lowercased."""
    if not os.path.exists(path):
        return []

    result: list[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip().lower()
                if not line or line.startswith("#"):
                    continue
                result.append(line)
    except Exception:
        return []
    return result


def _read_effective_entries_from_text(text: str) -> list[str]:
    result: list[str] = []
    for raw in str(text or "").splitlines():
        line = raw.strip().lower()
        if not line or line.startswith("#"):
            continue
        result.append(line)
    return result


def _count_effective_entries(path: str) -> int:
    return len(_read_effective_entries(path))


def get_base_domains() -> list[str]:
    """Возвращает базовые домены из текущей системной базы или встроенного списка."""
    base_domains = _read_effective_entries(OTHER_BASE_PATH)
    if base_domains:
        return base_domains

    embedded_domains = _read_effective_entries_from_text(get_other_base_text())
    if embedded_domains:
        return embedded_domains

    log("WARNING: Не удалось загрузить встроенную базу other, использую аварийный минимум", "WARNING")
    return _fallback_base_domains()


def get_base_domains_set() -> set[str]:
    """Возвращает set базовых доменов (lowercase)."""
    return {d.strip().lower() for d in get_base_domains() if d and d.strip()}


def get_user_domains() -> list[str]:
    """Возвращает effective-строки (без комментариев) из other.user.txt."""
    return _read_effective_entries(OTHER_USER_PATH)


def build_other_base_content() -> str:
    """Формирует каноническое содержимое системной базы other.base.txt."""
    embedded_text = str(get_other_base_text() or "")
    if _read_effective_entries_from_text(embedded_text):
        return embedded_text

    domains = sorted(set(_fallback_base_domains()))
    return "\n".join(domains) + "\n"


def _write_base_file() -> bool:
    """Перезаписывает other.base.txt из встроенной системной базы."""
    try:
        write_text_file(OTHER_BASE_PATH, build_other_base_content())
        return True

    except Exception as e:
        log(f"Ошибка обновления other.base.txt: {e}", "ERROR")
        return False


def rebuild_other_files() -> bool:
    """Пересобирает other.base.txt, other.user.txt и other.txt."""
    try:
        if not prepare_user_file(OTHER_USER_PATH, error_message="Ошибка подготовки other.user.txt", log_func=log):
            return False
        if not _write_base_file():
            return False
        try:
            write_combined_file(OTHER_PATH, get_base_domains(), _read_effective_entries(OTHER_USER_PATH))
        except Exception as e:
            log(f"Ошибка генерации other.txt: {e}", "ERROR")
            return False
        return _count_effective_entries(OTHER_PATH) > 0

    except Exception as e:
        log(f"Ошибка rebuild_other_files: {e}", "ERROR")
        return False


def reset_other_user_file() -> bool:
    """Очищает other.user.txt и пересобирает other.txt из системной базы."""
    try:
        write_text_file(OTHER_USER_PATH, "")
        ok = rebuild_other_files()
        if ok:
            log("other.user.txt очищен, other.txt пересобран из системной базы", "SUCCESS")
        return ok

    except Exception as e:
        log(f"Ошибка сброса my hostlist: {e}", "ERROR")
        return False


def ensure_hostlists_exist() -> bool:
    """Проверяет hostlist-файлы и создает other.txt при необходимости."""
    return rebuild_other_files()


def startup_hostlists_check() -> bool:
    """Проверка hostlist-файлов при запуске программы."""
    try:
        log("=== Проверка хостлистов при запуске ===", "HOSTLISTS")

        ok = rebuild_other_files()
        if ok:
            total = _count_effective_entries(OTHER_PATH)
            user = _count_effective_entries(OTHER_USER_PATH)
            log(f"other.txt: {total} строк, user: {user}", "INFO")
        else:
            log("Хостлисты не готовы", "WARNING")

        return ok

    except Exception as e:
        log(f"Ошибка при проверке хостлистов: {e}", "ERROR")
        return False
