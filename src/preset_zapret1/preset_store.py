# preset_zapret1/preset_store.py
"""Lazy preset store for Zapret 1."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from log import log


class PresetStoreV1(QObject):
    """Lazy preset store for Zapret 1 presets.

    Keeps lightweight manifest metadata for the whole library and loads a
    parsed preset model only when a concrete file is requested.
    """

    presets_changed = pyqtSignal()
    preset_switched = pyqtSignal(str)  # file_name
    preset_updated = pyqtSignal(str)  # file_name

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._manifests_by_file_name: Dict[str, object] = {}
        self._presets_by_file_name: Dict[str, "PresetV1"] = {}
        self._loaded = False
        self._selected_source_file_name: Optional[str] = None

    def get_preset_by_file_name(self, file_name: str) -> Optional["PresetV1"]:
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

    def refresh(self) -> None:
        self._reload_manifests(clear_cache=True)
        self.presets_changed.emit()

    def notify_preset_saved(self, file_name: str) -> None:
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
        self._reload_manifests(clear_cache=True)
        self.presets_changed.emit()

    def notify_preset_switched(self, file_name: str) -> None:
        target_file_name = str(file_name or "").strip() or None
        self._selected_source_file_name = target_file_name
        self.preset_switched.emit(target_file_name or "")

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._reload_manifests(clear_cache=False)

    def _reload_manifests(self, *, clear_cache: bool) -> None:
        from core.services import get_preset_repository, get_selection_service

        manifests_by_file_name: Dict[str, object] = {}
        for manifest in get_preset_repository().list_manifests("winws1"):
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
            self._selected_source_file_name = get_selection_service().get_selected_file_name("winws1")
        except Exception:
            self._selected_source_file_name = None
        self._loaded = True
        log(
            f"PresetStoreV1: manifests loaded {len(self._manifests_by_file_name)}, "
            f"parsed cache {len(self._presets_by_file_name)}",
            "DEBUG",
        )

    def _reload_single_preset(self, file_name: str) -> Optional["PresetV1"]:
        from core.services import get_app_paths
        from .preset_storage import _load_preset_from_path_v1
        target_file_name = str(file_name or "").strip()
        if not target_file_name:
            return None
        if target_file_name not in self._manifests_by_file_name:
            self._presets_by_file_name.pop(target_file_name, None)
            return None
        try:
            preset_path = get_app_paths().engine_paths("winws1").ensure_directories().presets_dir / target_file_name
            preset = _load_preset_from_path_v1(preset_path)
            if preset is not None:
                try:
                    setattr(preset, "_source_file_name", target_file_name)
                except Exception:
                    pass
                self._presets_by_file_name[target_file_name] = preset
                return preset
            else:
                self._presets_by_file_name.pop(target_file_name, None)
        except Exception as e:
            log(f"PresetStoreV1: error reloading preset '{target_file_name}': {e}", "DEBUG")
        return None


def get_preset_store_v1() -> PresetStoreV1:
    """Returns the shared PresetStoreV1 from core services."""
    from core.services import get_preset_store_v1 as _get_preset_store_v1_service

    return _get_preset_store_v1_service()
