"""Менеджер IPset файлов.

Файлы в папке приложения:
- `lists/ipset-all.base.txt`  : системная база для ipset-all
- `lists/ipset-all.user.txt`  : пользовательские записи (редактируются из GUI)
- `lists/ipset-all.txt`       : итоговый файл (base + user)
- `lists/ipset-ru.base.txt`   : системная база исключений для --ipset-exclude
- `lists/ipset-ru.user.txt`   : пользовательские исключения (редактируются из GUI)
- `lists/ipset-ru.txt`        : итоговый файл исключений (base + user)

Шаблоны базы хранятся в `lists_template` рядом с программой.
Пользовательские записи дополнительно бэкапятся в
`lists_backup` рядом с программой.

Поддерживаются следующие рабочие модели:
- `ipset-all.base.txt` + `ipset-all.user.txt` -> `ipset-all.txt`
- `ipset-ru.base.txt` + `ipset-ru.user.txt` -> `ipset-ru.txt`
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

from log.log import log
from lists.core.builders import dedup_preserve_order, write_combined_file
from lists.core.files import (
    normalize_newlines,
    prepare_user_file,
    read_text_file,
    read_text_file_safe,
    sync_user_backup,
    write_text_file,
)
from lists.core.paths import get_list_backup_path, get_list_path, get_list_template_path
from lists.core.paths import get_lists_dir

LISTS_FOLDER = get_lists_dir()

IPSET_ALL_PATH = get_list_path("ipset-all.txt")
IPSET_ALL_BASE_PATH = get_list_path("ipset-all.base.txt")
IPSET_ALL_USER_PATH = get_list_path("ipset-all.user.txt")
IPSET_RU_PATH = get_list_path("ipset-ru.txt")
IPSET_RU_BASE_PATH = get_list_path("ipset-ru.base.txt")
IPSET_RU_USER_PATH = get_list_path("ipset-ru.user.txt")


IPSET_ALL_BUILTIN_BASE_TEXT = """
# Cloudflare DNS
1.1.1.1
1.1.1.2
1.1.1.3
1.0.0.1
1.0.0.2
1.0.0.3
"""


_IPSET_RU_BASE_HEADER = """\
# Системная база исключений для --ipset-exclude.
# Этот файл управляется приложением.
#
# Итоговый lists/ipset-ru.txt формируется автоматически как:
#   ipset-ru.base.txt + ipset-ru.user.txt
"""


_BASE_CACHE_PATH: str | None = None
_BASE_CACHE_SIG: tuple[int, int] | None = None
_BASE_CACHE_ENTRIES: list[str] | None = None
_BASE_CACHE_SET: set[str] | None = None


def _file_sig(path: str) -> tuple[int, int] | None:
    try:
        st = os.stat(path)
        return int(st.st_mtime_ns), int(st.st_size)
    except OSError:
        return None


def _invalidate_base_cache() -> None:
    global _BASE_CACHE_PATH, _BASE_CACHE_SIG, _BASE_CACHE_ENTRIES, _BASE_CACHE_SET
    _BASE_CACHE_PATH = None
    _BASE_CACHE_SIG = None
    _BASE_CACHE_ENTRIES = None
    _BASE_CACHE_SET = None


def _is_cached(path: str) -> bool:
    return (
        _BASE_CACHE_PATH == path
        and _BASE_CACHE_ENTRIES is not None
        and _BASE_CACHE_SIG is not None
        and _BASE_CACHE_SIG == _file_sig(path)
    )


def _cache_base(path: str, entries: list[str]) -> None:
    global _BASE_CACHE_PATH, _BASE_CACHE_SIG, _BASE_CACHE_ENTRIES, _BASE_CACHE_SET
    _BASE_CACHE_PATH = path
    _BASE_CACHE_SIG = _file_sig(path)
    _BASE_CACHE_ENTRIES = list(entries)
    _BASE_CACHE_SET = set(entries)


def _has_effective_line(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        if os.path.getsize(path) <= 0:
            return False
    except OSError:
        return False

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if line and not line.startswith("#"):
                    return True
    except Exception:
        return False

    return False


def _builtin_ipset_all_base_ips() -> list[str]:
    ips: list[str] = []
    for line in IPSET_ALL_BUILTIN_BASE_TEXT.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            ips.append(line)
    return ips


def _normalize_ip_entry(text: str) -> str | None:
    line = str(text or "").strip()
    if not line or line.startswith("#"):
        return None

    if "://" in line:
        try:
            parsed = urlparse(line)
            host = parsed.netloc or parsed.path.split("/")[0]
            line = host.split(":")[0]
        except Exception:
            pass

    if "-" in line:
        return None

    if "/" in line:
        try:
            return ipaddress.ip_network(line, strict=False).with_prefixlen
        except Exception:
            return None

    try:
        return str(ipaddress.ip_address(line))
    except Exception:
        return None


def _read_effective_ip_entries(path: str) -> list[str]:
    if not os.path.exists(path):
        return []

    result: list[str] = []
    seen: set[str] = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                norm = _normalize_ip_entry(raw)
                if not norm or norm in seen:
                    continue
                seen.add(norm)
                result.append(norm)
    except Exception:
        return []
    return result


def _count_effective_entries(path: str) -> int:
    return len(_read_effective_ip_entries(path))


def ensure_ipset_all_template_updated() -> bool:
    """Гарантирует валидный системный шаблон ipset-all в lists_template."""
    try:
        template_path = get_list_template_path("ipset-all.txt")

        if _has_effective_line(template_path):
            return True

        fallback_content = "\n".join(_builtin_ipset_all_base_ips()) + "\n"
        write_text_file(template_path, fallback_content)
        log("Создан аварийный шаблон ipset-all.txt", "WARNING")
        return True

    except Exception as e:
        log(f"Ошибка обновления шаблона ipset-all.txt: {e}", "ERROR")
        return False


def get_ipset_all_base_entries() -> list[str]:
    if _is_cached(IPSET_ALL_BASE_PATH):
        return list(_BASE_CACHE_ENTRIES or [])

    if os.path.exists(IPSET_ALL_BASE_PATH):
        base_entries = _read_effective_ip_entries(IPSET_ALL_BASE_PATH)
        if base_entries:
            _cache_base(IPSET_ALL_BASE_PATH, base_entries)
            return list(base_entries)

    template_path = get_list_template_path("ipset-all.txt")
    if _is_cached(template_path):
        return list(_BASE_CACHE_ENTRIES or [])

    template_entries = _read_effective_ip_entries(template_path)
    if template_entries:
        merged_entries = dedup_preserve_order(list(template_entries) + _builtin_ipset_all_base_ips())
        _cache_base(template_path, merged_entries)
        return list(merged_entries)

    return _builtin_ipset_all_base_ips()


def get_ipset_all_base_set() -> set[str]:
    entries = get_ipset_all_base_entries()
    if _BASE_CACHE_ENTRIES == entries and _BASE_CACHE_SET is not None:
        return set(_BASE_CACHE_SET)
    return {x for x in entries if x}


def get_user_ipset_entries() -> list[str]:
    return _read_effective_ip_entries(IPSET_ALL_USER_PATH)


def ensure_ipset_all_user_file() -> bool:
    """Публичный helper: гарантирует наличие ipset-all.user.txt."""
    return prepare_user_file(
        IPSET_ALL_USER_PATH,
        get_list_backup_path("ipset-all.user.txt"),
        restored_message="ipset-all.user.txt восстановлен из backup",
        error_message="Ошибка подготовки ipset-all.user.txt",
        log_func=log,
    )


def _write_ipset_all_base_file_from_template() -> bool:
    """Writes IPSET_ALL_BASE_PATH from template (raw)."""
    try:
        if not ensure_ipset_all_template_updated():
            return False

        template_content = read_text_file_safe(get_list_template_path("ipset-all.txt"))
        if template_content is None:
            merged_content = "\n".join(get_ipset_all_base_entries()) + "\n"
        else:
            normalized_template = normalize_newlines(template_content)
            template_entries = _read_effective_ip_entries(get_list_template_path("ipset-all.txt"))
            template_set = set(template_entries)
            extra_entries = [ip for ip in _builtin_ipset_all_base_ips() if ip not in template_set]
            merged_content = normalized_template
            if extra_entries:
                if merged_content and not merged_content.endswith("\n"):
                    merged_content += "\n"
                if merged_content and not merged_content.endswith("\n\n"):
                    merged_content += "\n"
                merged_content += "\n".join(extra_entries) + "\n"

        write_text_file(IPSET_ALL_BASE_PATH, merged_content)
        _invalidate_base_cache()
        return True

    except Exception as e:
        log(f"Ошибка обновления ipset-all.base.txt: {e}", "ERROR")
        return False


def sync_ipset_all_after_user_change() -> bool:
    """Быстрый sync после правки user-файла.

    Не пересобирает шаблон из source на каждом вызове.
    Используется в GUI-автосохранении, чтобы не блокировать интерфейс.
    """
    try:
        if not ensure_ipset_all_user_file():
            return False

        if not os.path.exists(IPSET_ALL_BASE_PATH) or os.path.getsize(IPSET_ALL_BASE_PATH) <= 0:
            if not _write_ipset_all_base_file_from_template():
                return False

        try:
            write_combined_file(IPSET_ALL_PATH, get_ipset_all_base_entries(), _read_effective_ip_entries(IPSET_ALL_USER_PATH))
        except Exception as e:
            log(f"Ошибка генерации ipset-all.txt: {e}", "ERROR")
            return False

        sync_user_backup(IPSET_ALL_USER_PATH, get_list_backup_path("ipset-all.user.txt"))
        return True

    except Exception as e:
        log(f"Ошибка sync_ipset_all_after_user_change: {e}", "ERROR")
        return False


def rebuild_ipset_all_files() -> bool:
    """Пересобирает ipset-all.base.txt, ipset-all.user.txt (если отсутствует) и ipset-all.txt."""
    try:
        if not ensure_ipset_all_template_updated():
            return False
        if not ensure_ipset_all_user_file():
            return False
        if not _write_ipset_all_base_file_from_template():
            return False
        try:
            write_combined_file(IPSET_ALL_PATH, get_ipset_all_base_entries(), _read_effective_ip_entries(IPSET_ALL_USER_PATH))
        except Exception as e:
            log(f"Ошибка генерации ipset-all.txt: {e}", "ERROR")
            return False

        sync_user_backup(IPSET_ALL_USER_PATH, get_list_backup_path("ipset-all.user.txt"))
        return _count_effective_entries(IPSET_ALL_PATH) > 0

    except Exception as e:
        log(f"Ошибка rebuild_ipset_all_files: {e}", "ERROR")
        return False


def reset_ipset_all_from_template() -> bool:
    """Очищает ipset-all.user.txt и пересобирает ipset-all.txt из базы."""
    try:
        if not ensure_ipset_all_template_updated():
            return False

        write_text_file(IPSET_ALL_USER_PATH, "")
        sync_user_backup(IPSET_ALL_USER_PATH, get_list_backup_path("ipset-all.user.txt"))

        ok = rebuild_ipset_all_files()
        if ok:
            log("ipset-all.user.txt очищен, ipset-all.txt пересобран из шаблона", "SUCCESS")
        return ok

    except Exception as e:
        log(f"Ошибка сброса ipset-all.user.txt: {e}", "ERROR")
        return False


def _get_default_ipset_ru_base_entries() -> list[str]:
    """Системная база ipset-ru (чистая установка)."""
    return []


def _build_ipset_ru_base_content() -> str:
    lines: list[str] = [ln.rstrip() for ln in _IPSET_RU_BASE_HEADER.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    lines.extend(_get_default_ipset_ru_base_entries())
    return "\n".join(lines) + "\n"


def _read_ipset_ru_template_content() -> str | None:
    template_path = get_list_template_path("ipset-ru.txt")
    if not _has_effective_line(template_path):
        return None
    content = read_text_file_safe(template_path)
    if content is None:
        return None
    return normalize_newlines(content)


def _ensure_ipset_ru_base_updated() -> bool:
    try:
        template_content = _read_ipset_ru_template_content()
        expected = template_content if template_content is not None else _build_ipset_ru_base_content()
        current = read_text_file_safe(IPSET_RU_BASE_PATH)

        if normalize_newlines(current or "") != normalize_newlines(expected):
            write_text_file(IPSET_RU_BASE_PATH, expected)
            if current is None:
                log("Создан ipset-ru.base.txt", "INFO")
            else:
                log("Обновлен ipset-ru.base.txt", "DEBUG")

        return True
    except Exception as e:
        log(f"Ошибка подготовки ipset-ru.base.txt: {e}", "ERROR")
        return False


def get_ipset_ru_base_entries() -> list[str]:
    return _read_effective_ip_entries(IPSET_RU_BASE_PATH)


def get_ipset_ru_base_set() -> set[str]:
    return set(get_ipset_ru_base_entries())


def get_user_ipset_ru_entries() -> list[str]:
    return _read_effective_ip_entries(IPSET_RU_USER_PATH)


def ensure_ipset_ru_user_file() -> bool:
    """Публичный helper: гарантирует наличие ipset-ru.user.txt."""
    if not _ensure_ipset_ru_base_updated():
        return False
    return prepare_user_file(
        IPSET_RU_USER_PATH,
        get_list_backup_path("ipset-ru.user.txt"),
        restored_message="ipset-ru.user.txt восстановлен из backup",
        error_message="Ошибка подготовки ipset-ru.user.txt",
        log_func=log,
    )


def sync_ipset_ru_after_user_change() -> bool:
    """Быстрый sync после правки ipset-ru.user.txt."""
    try:
        if not _ensure_ipset_ru_base_updated():
            return False
        if not ensure_ipset_ru_user_file():
            return False
        try:
            write_combined_file(IPSET_RU_PATH, get_ipset_ru_base_entries(), _read_effective_ip_entries(IPSET_RU_USER_PATH))
        except Exception as e:
            log(f"Ошибка генерации ipset-ru.txt: {e}", "ERROR")
            return False
        sync_user_backup(IPSET_RU_USER_PATH, get_list_backup_path("ipset-ru.user.txt"))
        return True
    except Exception as e:
        log(f"Ошибка sync_ipset_ru_after_user_change: {e}", "ERROR")
        return False


def rebuild_ipset_ru_files() -> bool:
    """Пересобирает ipset-ru.base.txt, ipset-ru.user.txt и ipset-ru.txt."""
    try:
        if not _ensure_ipset_ru_base_updated():
            return False
        if not ensure_ipset_ru_user_file():
            return False
        try:
            write_combined_file(IPSET_RU_PATH, get_ipset_ru_base_entries(), _read_effective_ip_entries(IPSET_RU_USER_PATH))
        except Exception as e:
            log(f"Ошибка генерации ipset-ru.txt: {e}", "ERROR")
            return False
        sync_user_backup(IPSET_RU_USER_PATH, get_list_backup_path("ipset-ru.user.txt"))
        return True
    except Exception as e:
        log(f"Ошибка rebuild_ipset_ru_files: {e}", "ERROR")
        return False


def ensure_ipsets_exist() -> bool:
    """Проверяет существование файлов IPsets и создает их если нужно."""
    try:
        os.makedirs(LISTS_FOLDER, exist_ok=True)

        if not rebuild_ipset_all_files():
            log("Не удалось подготовить ipset-all файлы", "WARNING")
            return False

        if not rebuild_ipset_ru_files():
            log("Не удалось подготовить ipset-ru файлы", "WARNING")
            return False

        return True

    except Exception as e:
        log(f"Ошибка создания файлов IPsets: {e}", "❌ ERROR")
        return False


def startup_ipsets_check() -> bool:
    """Проверка IPsets при запуске программы."""
    try:
        log("=== Проверка IPsets при запуске ===", "IPSETS")

        os.makedirs(LISTS_FOLDER, exist_ok=True)

        ipset_all_ok = rebuild_ipset_all_files()
        ipset_ru_ok = rebuild_ipset_ru_files()

        if ipset_all_ok and ipset_ru_ok:
            total_all = _count_effective_entries(IPSET_ALL_PATH)
            user_all = _count_effective_entries(IPSET_ALL_USER_PATH)
            total_ru = _count_effective_entries(IPSET_RU_PATH)
            user_ru = _count_effective_entries(IPSET_RU_USER_PATH)
            log(f"ipset-all.txt: {total_all} строк, user: {user_all}", "INFO")
            log(f"ipset-ru.txt: {total_ru} строк, user: {user_ru}", "INFO")
            return True

        log(
            f"Проблемы с IPset файлами: ipset-all={ipset_all_ok}, ipset-ru={ipset_ru_ok}",
            "WARNING",
        )
        return False

    except Exception as e:
        log(f"❌ Ошибка при проверке IPsets: {e}", "ERROR")
        return False
