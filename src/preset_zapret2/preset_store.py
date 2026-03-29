# preset_zapret2/preset_store.py
"""
Lazy preset store.

Provides a single source of truth for all preset data across the application.
All UI pages and backend modules should use this store instead of creating
independent PresetManager instances.

Features:
- Lightweight manifest metadata for all presets
- Parsed preset objects loaded only on demand
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
    """Lazy preset store.

    Keeps manifest metadata for the whole library and parses an individual
    preset only when that exact file is requested.
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

        # {file_name: PresetManifest}
        self._manifests_by_file_name: Dict[str, object] = {}
        # {file_name: Preset}
        self._presets_by_file_name: Dict[str, "Preset"] = {}
        # Flag: initial load done?
        self._loaded = False

        # Cached selected source preset identity from direct core state.
        self._selected_source_file_name: Optional[str] = None

    # ── Public API: Read ─────────────────────────────────────────────────

    def get_preset_by_file_name(self, file_name: str) -> Optional["Preset"]:
        self._ensure_loaded()
        target_file_name = str(file_name or "").strip()
        if not target_file_name or target_file_name not in self._manifests_by_file_name:
            return None
        preset = self._presets_by_file_name.get(target_file_name)
        if preset is not None:
            return preset
        return self._reload_single_preset(target_file_name)

    def get_preset_file_names(self) -> List[str]:
        self._ensure_loaded()
        return sorted(self._manifests_by_file_name.keys(), key=lambda s: s.lower())

    def get_display_name(self, file_name: str) -> str:
        self._ensure_loaded()
        candidate = str(file_name or "").strip()
        manifest = self._manifests_by_file_name.get(candidate)
        if manifest is not None:
            return str(getattr(manifest, "name", "") or "").strip() or Path(candidate).stem
        return Path(candidate).stem if candidate else ""

    def get_selected_source_preset_file_name(self) -> Optional[str]:
        self._ensure_loaded()
        return self._selected_source_file_name

    # ── Public API: Mutate ───────────────────────────────────────────────

    def refresh(self) -> None:
        """
        Full metadata reload from disk. Clears parsed cache.
        Emits presets_changed after reload.
        """
        self._reload_manifests(clear_cache=True)
        self.presets_changed.emit()

    def notify_preset_saved(self, file_name: str) -> None:
        """
        Called after a preset file is saved/modified on disk.
        Refreshes metadata and re-reads that single preset only if needed.
        Emits preset_updated.
        """
        self._ensure_loaded()
        target_file_name = str(file_name or "").strip()
        self._reload_manifests(clear_cache=False)
        if target_file_name:
            if target_file_name in self._presets_by_file_name or target_file_name in self._manifests_by_file_name:
                self._reload_single_preset(target_file_name)
            else:
                self._presets_by_file_name.pop(target_file_name, None)
        self.preset_updated.emit(target_file_name)

    def notify_presets_changed(self) -> None:
        """
        Called after an operation that changes the preset list
        (create, delete, rename, duplicate, import).
        Refreshes manifest metadata, clears parsed cache and emits presets_changed.
        """
        self._reload_manifests(clear_cache=True)
        self.presets_changed.emit()

    def notify_preset_switched(self, file_name: str) -> None:
        """
        Called after the selected source preset is switched.
        Updates the cached selected file_name and emits preset_switched.
        """
        target_file_name = str(file_name or "").strip() or None
        self._selected_source_file_name = target_file_name
        self.preset_switched.emit(target_file_name or "")

    # ── Internal ─────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        """Loads manifest metadata on first access."""
        if not self._loaded:
            self._reload_manifests(clear_cache=False)

    def _reload_manifests(self, *, clear_cache: bool) -> None:
        from core.services import get_preset_repository, get_selection_service

        manifests_by_file_name: Dict[str, object] = {}
        for manifest in get_preset_repository().list_manifests("winws2"):
            file_name = str(getattr(manifest, "file_name", "") or "").strip()
            if file_name:
                manifests_by_file_name[file_name] = manifest

        self._manifests_by_file_name = manifests_by_file_name
        if clear_cache:
            self._presets_by_file_name.clear()
        else:
            self._presets_by_file_name = {
                file_name: preset
                for file_name, preset in self._presets_by_file_name.items()
                if file_name in self._manifests_by_file_name
            }

        try:
            self._selected_source_file_name = get_selection_service().get_selected_file_name("winws2")
        except Exception:
            self._selected_source_file_name = None
        self._loaded = True

        log(
            f"PresetStore: manifests loaded {len(self._manifests_by_file_name)}, "
            f"parsed cache {len(self._presets_by_file_name)}",
            "DEBUG",
        )

    def _reload_single_preset(self, file_name: str) -> Optional["Preset"]:
        """Re-reads a single preset from disk into the store."""
        from core.services import get_app_paths
        from .preset_storage import _load_preset_from_path

        target_file_name = str(file_name or "").strip()
        if not target_file_name:
            return None
        if target_file_name not in self._manifests_by_file_name:
            self._presets_by_file_name.pop(target_file_name, None)
            return None

        try:
            preset_path = get_app_paths().engine_paths("winws2").ensure_directories().presets_dir / target_file_name
            preset = _load_preset_from_path(preset_path)
            if preset is not None:
                try:
                    setattr(preset, "_source_file_name", target_file_name)
                except Exception:
                    pass
                self._presets_by_file_name[target_file_name] = preset
                return preset
            else:
                # Preset was deleted or became unreadable
                self._presets_by_file_name.pop(target_file_name, None)
        except Exception as e:
            log(f"PresetStore: error reloading preset '{target_file_name}': {e}", "DEBUG")
        return None


def get_preset_store() -> PresetStore:
    """Returns the shared PresetStore from core services."""
    from core.services import get_preset_store as _get_preset_store_service

    return _get_preset_store_service()
