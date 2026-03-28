# preset_zapret2/preset_store.py
"""
Central in-memory preset store.

Provides a single source of truth for all preset data across the application.
All UI pages and backend modules should use this store instead of creating
independent PresetManager instances.

Features:
- All presets loaded into memory once, refreshed only when files change
- Qt signals for preset lifecycle events (change, switch, create, delete)
- Shared access via core.services.get_preset_store()

Usage:
    from preset_zapret2.preset_store import get_preset_store

    store = get_preset_store()

    # Read presets (from memory, instant)
    file_names = store.get_preset_file_names()
    preset = store.get_preset_by_file_name("Default.txt")

    # Listen for changes
    store.presets_changed.connect(my_handler)
    store.preset_switched.connect(on_switched)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from log import log


class PresetStore(QObject):
    """
    Central in-memory preset store.

    Holds all parsed Preset objects in memory.
    Emits Qt signals when preset data changes.
    """

    # ── Signals ──────────────────────────────────────────────────────────
    # Emitted when the preset list or content changes (add/delete/rename/import/reset).
    presets_changed = pyqtSignal()

    # Emitted when the selected source preset is switched. Argument: new preset file_name.
    preset_switched = pyqtSignal(str)

    # Emitted when a single preset's content is updated (save/sync). Argument: preset file_name.
    preset_updated = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        # {file_name: Preset}
        self._presets_by_file_name: Dict[str, "Preset"] = {}
        # Flag: initial load done?
        self._loaded = False

        # Cached selected source preset identity from direct core state.
        self._active_file_name: Optional[str] = None

    # ── Public API: Read ─────────────────────────────────────────────────

    def get_preset_by_file_name(self, file_name: str) -> Optional["Preset"]:
        self._ensure_loaded()
        return self._presets_by_file_name.get(str(file_name or "").strip())

    def get_preset_file_names(self) -> List[str]:
        self._ensure_loaded()
        return sorted(self._presets_by_file_name.keys(), key=lambda s: s.lower())

    def get_display_name(self, file_name: str) -> str:
        self._ensure_loaded()
        return self._display_name_for_file_name(file_name)

    def get_selected_source_preset_file_name(self) -> Optional[str]:
        self._ensure_loaded()
        return self._active_file_name

    # ── Public API: Mutate ───────────────────────────────────────────────

    def refresh(self) -> None:
        """
        Full reload from disk. Clears all in-memory state and re-reads.
        Emits presets_changed after reload.
        """
        self._do_full_load()
        self.presets_changed.emit()

    def notify_preset_saved(self, file_name: str) -> None:
        """
        Called after a preset file is saved/modified on disk.
        Re-reads that single preset and emits preset_updated.
        """
        self._ensure_loaded()
        target_file_name = str(file_name or "").strip()
        self._reload_single_preset(target_file_name)
        self.preset_updated.emit(target_file_name)

    def notify_presets_changed(self) -> None:
        """
        Called after an operation that changes the preset list
        (create, delete, rename, duplicate, import).
        Performs a full reload and emits presets_changed.
        """
        self._do_full_load()
        self.presets_changed.emit()

    def notify_preset_switched(self, file_name: str) -> None:
        """
        Called after the selected source preset is switched.
        Updates the cached selected file_name and emits preset_switched.
        """
        target_file_name = str(file_name or "").strip() or None
        self._active_file_name = target_file_name
        self.preset_switched.emit(target_file_name or "")

    # ── Internal ─────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        """Loads all presets from disk on first access."""
        if not self._loaded:
            self._do_full_load()

    def _do_full_load(self) -> None:
        """Reads all presets from disk into memory."""
        from core.services import get_app_paths, get_preset_repository, get_selection_service
        from .preset_storage import _load_preset_from_path

        self._presets_by_file_name.clear()
        documents = get_preset_repository().list_presets("winws2")
        for document in documents:
            file_name = str(document.manifest.file_name or "").strip()
            if not file_name:
                continue
            try:
                preset_path = get_app_paths().engine_paths("winws2").ensure_directories().presets_dir / file_name
                preset = _load_preset_from_path(preset_path, Path(file_name).stem)
                if preset is not None:
                    try:
                        setattr(preset, "_source_file_name", file_name)
                    except Exception:
                        pass
                    self._presets_by_file_name[file_name] = preset
            except Exception as e:
                log(f"PresetStore: error loading preset '{file_name}': {e}", "DEBUG")

        try:
            self._active_file_name = get_selection_service().get_selected_file_name("winws2")
        except Exception:
            self._active_file_name = None
        self._loaded = True

        log(f"PresetStore: loaded {len(self._presets_by_file_name)} presets", "DEBUG")

    def _reload_single_preset(self, file_name: str) -> None:
        """Re-reads a single preset from disk into the store."""
        from core.services import get_app_paths
        from .preset_storage import _load_preset_from_path

        target_file_name = str(file_name or "").strip()
        if not target_file_name:
            return

        try:
            preset_path = get_app_paths().engine_paths("winws2").ensure_directories().presets_dir / target_file_name
            preset = _load_preset_from_path(preset_path, Path(target_file_name).stem)
            if preset is not None:
                try:
                    setattr(preset, "_source_file_name", target_file_name)
                except Exception:
                    pass
                self._presets_by_file_name[target_file_name] = preset
            else:
                # Preset was deleted or became unreadable
                self._presets_by_file_name.pop(target_file_name, None)
        except Exception as e:
            log(f"PresetStore: error reloading preset '{target_file_name}': {e}", "DEBUG")

    def _display_name_for_file_name(self, file_name: str | None) -> str:
        candidate = str(file_name or "").strip()
        preset = self._presets_by_file_name.get(candidate)
        if preset is not None:
            return str(getattr(preset, "name", "") or "").strip() or Path(candidate).stem
        return Path(candidate).stem if candidate else ""


def get_preset_store() -> PresetStore:
    """Returns the shared PresetStore from core services."""
    from core.services import get_preset_store as _get_preset_store_service

    return _get_preset_store_service()
