# lists/hostlists_manager.py
"""Менеджер hostlist-файлов.

Файлы в папке приложения (рядом с Zapret.exe):
- `lists/other.base.txt` : база (системный шаблон; пересоздаётся автоматически)
- `lists/other.user.txt` : пользовательский файл (редактируется пользователем)
- `lists/other.txt`      : итоговый файл для движка (base + user), генерируется автоматически

Шаблон базы хранится в `lists_template/other.txt` рядом с программой.
Для защиты от обновлений/portable-сценариев пользовательский файл дополнительно
копируется в `lists_backup/other.user.txt` рядом с программой.

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
from lists.core.files import (
    normalize_newlines,
    prepare_user_file,
    read_text_file,
    read_text_file_safe,
    sync_user_backup,
    write_text_file,
)
from lists.core.paths import get_list_backup_path, get_list_template_path
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


def _count_effective_entries(path: str) -> int:
    return len(_read_effective_entries(path))


def ensure_other_template_updated() -> bool:
    """Гарантирует валидный системный шаблон other.txt в lists_template."""
    try:
        template_path = get_list_template_path("other.txt")

        if _count_effective_entries(template_path) > 0:
            return True

        fallback_content = "\n".join(sorted(set(_fallback_base_domains()))) + "\n"
        write_text_file(template_path, fallback_content)
        log("Создан аварийный шаблон other.txt", "WARNING")
        return True

    except Exception as e:
        log(f"Ошибка обновления шаблона other.txt: {e}", "ERROR")
        return False


def get_base_domains() -> list[str]:
    """Возвращает базовые домены из шаблона или аварийного минимума."""
    template_domains = _read_effective_entries(get_list_template_path("other.txt"))
    if template_domains:
        return template_domains

    log("WARNING: Не найден валидный шаблон other.txt, использую аварийный минимум", "WARNING")
    return _fallback_base_domains()


def get_base_domains_set() -> set[str]:
    """Возвращает set базовых доменов (lowercase)."""
    return {d.strip().lower() for d in get_base_domains() if d and d.strip()}


def get_user_domains() -> list[str]:
    """Возвращает effective-строки (без комментариев) из other.user.txt."""
    return _read_effective_entries(OTHER_USER_PATH)


def build_other_template_content() -> str:
    """Формирует содержимое системного шаблона other.txt."""
    template_path = get_list_template_path("other.txt")
    if os.path.exists(template_path):
        try:
            content = read_text_file(template_path)
            if _read_effective_entries(template_path):
                return normalize_newlines(content)
        except Exception:
            pass

    domains = sorted(set(_fallback_base_domains()))
    return "\n".join(domains) + "\n"

def _write_base_file_from_template() -> bool:
    """Writes OTHER_BASE_PATH from the current template (raw)."""
    try:
        if not ensure_other_template_updated():
            return False

        template_content = read_text_file_safe(get_list_template_path("other.txt"))
        if template_content is None:
            template_content = "\n".join(get_base_domains()) + "\n"
        write_text_file(OTHER_BASE_PATH, template_content)
        return True

    except Exception as e:
        log(f"Ошибка обновления other.base.txt: {e}", "ERROR")
        return False


def rebuild_other_files() -> bool:
    """Пересобирает other.base.txt, other.user.txt (если отсутствует) и other.txt."""
    try:
        if not ensure_other_template_updated():
            return False
        if not prepare_user_file(
            OTHER_USER_PATH,
            get_list_backup_path("other.user.txt"),
            restored_message="other.user.txt восстановлен из backup",
            error_message="Ошибка подготовки other.user.txt",
            log_func=log,
        ):
            return False
        if not _write_base_file_from_template():
            return False
        try:
            write_combined_file(OTHER_PATH, get_base_domains(), _read_effective_entries(OTHER_USER_PATH))
        except Exception as e:
            log(f"Ошибка генерации other.txt: {e}", "ERROR")
            return False

        sync_user_backup(OTHER_USER_PATH, get_list_backup_path("other.user.txt"))
        return _count_effective_entries(OTHER_PATH) > 0

    except Exception as e:
        log(f"Ошибка rebuild_other_files: {e}", "ERROR")
        return False


def reset_other_file_from_template() -> bool:
    """Очищает other.user.txt и пересобирает other.txt из базы."""
    try:
        if not ensure_other_template_updated():
            return False

        write_text_file(OTHER_USER_PATH, "")
        sync_user_backup(OTHER_USER_PATH, get_list_backup_path("other.user.txt"))

        ok = rebuild_other_files()
        if ok:
            log("other.user.txt очищен, other.txt пересобран из шаблона", "SUCCESS")
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
