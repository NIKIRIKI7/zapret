from __future__ import annotations

from pathlib import Path

from ui.pages.orchestra_zapret2.preset_subpage_base import OrchestraPresetSubpageBase


class OrchestraZapret2PresetDetailPage(OrchestraPresetSubpageBase):
    def _default_title(self) -> str:
        return "Пресет Оркестра Zapret 2"

    def _get_preset_path(self, name: str) -> Path:
        from preset_orchestra_zapret2 import get_preset_path

        return get_preset_path(name)

    def _preset_hierarchy_scope_key(self) -> str | None:
        return "preset_orchestra_zapret2"
