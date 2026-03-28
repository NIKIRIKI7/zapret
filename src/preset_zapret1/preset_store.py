# preset_zapret1/preset_store.py
"""Central in-memory preset store for Zapret 1."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from log import log


class PresetStoreV1(QObject):
    """Central in-memory preset store for Zapret 1 presets."""

    presets_changed = pyqtSignal()
    preset_switched = pyqtSignal(str)  # file_name
    preset_updated = pyqtSignal(str)  # file_name

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._presets_by_file_name: Dict[str, "PresetV1"] = {}
        self._loaded = False
        self._active_file_name: Optional[str] = None

    def get_preset_by_file_name(self, file_name: str) -> Optional["PresetV1"]:
        self._ensure_loaded()
        return self._presets_by_file_name.get(str(file_name or "").strip())

    def get_preset_file_names(self) -> List[str]:
        self._ensure_loaded()
        return sorted(self._presets_by_file_name.keys(), key=lambda s: s.lower())

    def get_display_name(self, file_name: str) -> str:
        self._ensure_loaded()
        return self._display_name_for_file_name(file_name)

    def get_active_preset_file_name(self) -> Optional[str]:
        self._ensure_loaded()
        return self._active_file_name

    def refresh(self) -> None:
        self._do_full_load()
        self.presets_changed.emit()

    def notify_preset_saved(self, file_name: str) -> None:
        self._ensure_loaded()
        target_file_name = str(file_name or "").strip()
        self._reload_single_preset(target_file_name)
        self.preset_updated.emit(target_file_name)

    def notify_presets_changed(self) -> None:
        self._do_full_load()
        self.presets_changed.emit()

    def notify_preset_switched(self, file_name: str) -> None:
        target_file_name = str(file_name or "").strip() or None
        self._active_file_name = target_file_name
        self.preset_switched.emit(target_file_name or "")

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._do_full_load()

    def _do_full_load(self) -> None:
        from core.services import get_app_paths, get_preset_repository, get_selection_service
        from .preset_storage import _load_preset_from_path_v1

        self._presets_by_file_name.clear()
        documents = get_preset_repository().list_presets("winws1")
        for document in documents:
            file_name = str(document.manifest.file_name or "").strip()
            if not file_name:
                continue
            try:
                preset_path = get_app_paths().engine_paths("winws1").ensure_directories().presets_dir / file_name
                preset = _load_preset_from_path_v1(preset_path, Path(file_name).stem)
                if preset is not None:
                    try:
                        setattr(preset, "_source_file_name", file_name)
                    except Exception:
                        pass
                    self._presets_by_file_name[file_name] = preset
            except Exception as e:
                log(f"PresetStoreV1: error loading preset '{file_name}': {e}", "DEBUG")
        try:
            self._active_file_name = get_selection_service().get_selected_file_name("winws1")
        except Exception:
            self._active_file_name = None
        self._loaded = True
        log(f"PresetStoreV1: loaded {len(self._presets_by_file_name)} presets", "DEBUG")

    def _reload_single_preset(self, file_name: str) -> None:
        from core.services import get_app_paths
        from .preset_storage import _load_preset_from_path_v1
        target_file_name = str(file_name or "").strip()
        if not target_file_name:
            return
        try:
            preset_path = get_app_paths().engine_paths("winws1").ensure_directories().presets_dir / target_file_name
            preset = _load_preset_from_path_v1(preset_path, Path(target_file_name).stem)
            if preset is not None:
                try:
                    setattr(preset, "_source_file_name", target_file_name)
                except Exception:
                    pass
                self._presets_by_file_name[target_file_name] = preset
            else:
                self._presets_by_file_name.pop(target_file_name, None)
        except Exception as e:
            log(f"PresetStoreV1: error reloading preset '{target_file_name}': {e}", "DEBUG")

    def _display_name_for_file_name(self, file_name: str | None) -> str:
        candidate = str(file_name or "").strip()
        preset = self._presets_by_file_name.get(candidate)
        if preset is not None:
            return str(getattr(preset, "name", "") or "").strip() or Path(candidate).stem
        return Path(candidate).stem if candidate else ""


def get_preset_store_v1() -> PresetStoreV1:
    """Returns the shared PresetStoreV1 from core services."""
    from core.services import get_preset_store_v1 as _get_preset_store_v1_service

    return _get_preset_store_v1_service()
