from __future__ import annotations

from pathlib import Path

from ui.pages.preset_subpage_base import PresetSubpageBase


class Zapret2PresetDetailPage(PresetSubpageBase):
    def _default_title(self) -> str:
        return "Пресет Zapret 2"

    def _get_preset_path(self, name: str) -> Path:
        from core.services import get_app_paths

        return get_app_paths().engine_paths("winws2").ensure_directories().presets_dir / str(name or "").strip()

    def _direct_launch_method(self) -> str | None:
        return "direct_zapret2"
