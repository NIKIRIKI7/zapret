from __future__ import annotations

from pathlib import Path
import re
from typing import Optional

from log import log
from ui.theme import get_theme_tokens


_DEFAULT_PRESET_ICON_COLOR = "#5caee8"
_HEX_COLOR_RGB_RE = re.compile(r"^#(?:[0-9a-fA-F]{6})$")
_HEX_COLOR_RGBA_RE = re.compile(r"^#(?:[0-9a-fA-F]{8})$")


def normalize_preset_icon_color(value: Optional[str]) -> str:
    raw = str(value or "").strip()
    if _HEX_COLOR_RGB_RE.fullmatch(raw):
        return raw.lower()
    if _HEX_COLOR_RGBA_RE.fullmatch(raw):
        lowered = raw.lower()
        return f"#{lowered[1:7]}"
    try:
        return get_theme_tokens().accent_hex
    except Exception:
        return _DEFAULT_PRESET_ICON_COLOR


def on_store_changed(page) -> None:
    mark_presets_structure_changed(page)


def mark_presets_structure_changed(page) -> None:
    page._ui_dirty = True
    if page._bulk_reset_running:
        return
    if page.isVisible():
        page._schedule_presets_reload(0)


def on_ui_state_changed(page, _state, changed_fields: frozenset[str]) -> None:
    if "preset_structure_revision" in changed_fields:
        mark_presets_structure_changed(page)


def on_store_updated(page, file_name_or_name: str) -> None:
    if page._bulk_reset_running:
        return

    refreshed = page._read_single_preset_list_metadata_light(file_name_or_name)
    if refreshed is None:
        page._ui_dirty = True
        if page.isVisible():
            page._schedule_presets_reload(0)
        return

    normalized_file_name, metadata = refreshed
    previous_metadata = dict(page._cached_presets_metadata.get(normalized_file_name) or {})
    page._cached_presets_metadata[normalized_file_name] = metadata
    page._sync_watched_preset_files()
    if page.isVisible():
        if page._try_apply_single_preset_metadata_update(
            normalized_file_name,
            previous_metadata=previous_metadata,
            next_metadata=metadata,
        ):
            return
        page._refresh_presets_view_from_cache()
    else:
        page._ui_dirty = True


def current_search_query(page) -> str:
    try:
        if page._preset_search_input is not None:
            return str(page._preset_search_input.text() or "").strip().lower()
    except Exception:
        pass
    return ""


def capture_presets_view_state(page) -> dict[str, object]:
    state = {
        "current_file_name": "",
        "scroll_value": 0,
    }
    try:
        current_index = page.presets_list.currentIndex()
        if current_index.isValid():
            file_role = getattr(type(page._presets_model), "FileNameRole", None)
            if file_role is not None:
                state["current_file_name"] = str(current_index.data(file_role) or "")
    except Exception:
        pass
    try:
        scrollbar = page.presets_list.verticalScrollBar()
        if scrollbar is not None:
            state["scroll_value"] = int(scrollbar.value())
    except Exception:
        pass
    return state


def restore_presets_view_state(page, state: dict[str, object]) -> None:
    target_file_name = str((state or {}).get("current_file_name") or "").strip()
    if target_file_name:
        page._set_current_preset_index(target_file_name)
    try:
        scrollbar = page.presets_list.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(int((state or {}).get("scroll_value") or 0))
    except Exception:
        pass


def try_apply_single_preset_metadata_update(
    page,
    normalized_file_name: str,
    *,
    previous_metadata: dict[str, object],
    next_metadata: dict[str, object],
) -> bool:
    model = page._presets_model
    if model is None or model.find_preset_row(normalized_file_name) < 0:
        return False

    previous_display_name = str(previous_metadata.get("display_name") or normalized_file_name).strip()
    next_display_name = str(next_metadata.get("display_name") or normalized_file_name).strip()
    if previous_display_name != next_display_name:
        return False

    query = page._current_search_query()
    if query and query not in next_display_name.lower():
        return False

    active_file_name = page._get_selected_source_preset_file_name_light()
    updated = model.update_preset_row(
        normalized_file_name,
        name=next_display_name,
        description=str(next_metadata.get("description") or ""),
        date=str(next_metadata.get("modified_display") or ""),
        is_active=bool(normalized_file_name and normalized_file_name == active_file_name),
        is_builtin=bool(next_metadata.get("is_builtin", False)),
        icon_color=normalize_preset_icon_color(str(next_metadata.get("icon_color") or "")),
    )
    if updated:
        try:
            page.presets_list.viewport().update()
        except Exception:
            pass
    return updated


def on_store_switched(page, _name: str) -> None:
    if page._bulk_reset_running:
        return
    marker_changed = page._apply_active_preset_marker()
    if marker_changed and not page._ui_dirty:
        return
    if not page._ui_dirty and page._cached_presets_metadata and not marker_changed:
        return
    page._ui_dirty = True
    if page.isVisible():
        page.refresh_presets_view_if_possible()


def start_watching_presets(page) -> None:
    try:
        if page._watcher_active:
            return

        presets_dir = page._get_presets_dir_light()
        presets_dir.mkdir(parents=True, exist_ok=True)

        if not page._file_watcher:
            from PyQt6.QtCore import QFileSystemWatcher

            page._file_watcher = QFileSystemWatcher(page)
            page._file_watcher.directoryChanged.connect(page._on_presets_dir_changed)
            page._file_watcher.fileChanged.connect(page._on_preset_file_changed)

        dir_path = str(presets_dir)
        if dir_path not in page._file_watcher.directories():
            page._file_watcher.addPath(dir_path)

        page._sync_watched_preset_files()
        page._watcher_active = True
    except Exception as e:
        log(f"Ошибка запуска мониторинга пресетов: {e}", "DEBUG")


def stop_watching_presets(page) -> None:
    try:
        if not page._watcher_active:
            return
        if page._file_watcher:
            directories = page._file_watcher.directories()
            files = page._file_watcher.files()
            if directories:
                page._file_watcher.removePaths(directories)
            if files:
                page._file_watcher.removePaths(files)
        page._watcher_active = False
    except Exception as e:
        log(f"Ошибка остановки мониторинга пресетов: {e}", "DEBUG")


def on_presets_dir_changed(page, path: str) -> None:
    try:
        log(f"Обнаружены изменения в папке пресетов: {path}", "DEBUG")
        page._schedule_presets_reload()
    except Exception as e:
        log(f"Ошибка обработки изменений папки пресетов: {e}", "DEBUG")


def on_preset_file_changed(page, path: str) -> None:
    try:
        changed_path = Path(path)
        if page._file_watcher is not None and changed_path.exists():
            normalized_path = str(changed_path)
            if normalized_path not in page._file_watcher.files():
                page._file_watcher.addPath(normalized_path)

        file_name = changed_path.name
        if file_name:
            page._on_store_updated(file_name)
    except Exception as e:
        log(f"Ошибка обработки изменений файла пресета: {e}", "DEBUG")


def schedule_presets_reload(page, delay_ms: int = 500) -> None:
    try:
        page._watcher_reload_timer.stop()
        page._watcher_reload_timer.start(delay_ms)
    except Exception as e:
        log(f"Ошибка планирования обновления пресетов: {e}", "DEBUG")


def reload_presets_from_watcher(page) -> None:
    if not page.isVisible():
        return
    try:
        current_file_names = set(page._cached_presets_metadata.keys())
        next_entries = page._list_preset_entries_light()
        next_file_names = {
            str(entry.get("file_name") or "").strip()
            for entry in next_entries
            if str(entry.get("file_name") or "").strip()
        }
        page._sync_watched_preset_files(next_file_names)
        if current_file_names == next_file_names and current_file_names:
            return
    except Exception:
        pass
    page._load_presets()


def sync_watched_preset_files(page, file_names: set[str] | None = None) -> None:
    watcher = page._file_watcher
    if watcher is None:
        return

    try:
        presets_dir = page._get_presets_dir_light()
        if file_names is None:
            file_names = {
                str(file_name or "").strip()
                for file_name in page._cached_presets_metadata.keys()
                if str(file_name or "").strip()
            }

        desired_paths = {
            str(presets_dir / file_name)
            for file_name in file_names
            if file_name
        }
        current_paths = set(watcher.files() or [])

        remove_paths = sorted(current_paths - desired_paths)
        add_paths = sorted(
            path for path in (desired_paths - current_paths)
            if Path(path).exists()
        )

        if remove_paths:
            watcher.removePaths(remove_paths)
        if add_paths:
            watcher.addPaths(add_paths)
    except Exception as e:
        log(f"Ошибка синхронизации watcher файлов пресетов: {e}", "DEBUG")


def load_presets(page) -> None:
    page._ui_dirty = False
    try:
        import time

        started_at = time.perf_counter()
        all_presets = page._load_preset_list_metadata_light()
        page._cached_presets_metadata = dict(all_presets)
        page._sync_watched_preset_files(set(all_presets.keys()))
        page._rebuild_presets_rows(all_presets, started_at=started_at)
    except Exception as e:
        log(f"Ошибка загрузки пресетов: {e}", "ERROR")


def refresh_presets_view_if_possible(page) -> None:
    if not page._ui_initialized:
        page._ui_dirty = True
        return
    if page._cached_presets_metadata:
        page._ui_dirty = False
        page._refresh_presets_view_from_cache()
        return
    page._load_presets()


def refresh_presets_view_from_cache(page) -> None:
    if not page._cached_presets_metadata:
        page._load_presets()
        return
    page._rebuild_presets_rows(page._cached_presets_metadata)
