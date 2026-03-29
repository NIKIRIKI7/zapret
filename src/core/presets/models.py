from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PresetManifest:
    file_name: str
    name: str
    template_origin: str | None
    created_at: str
    updated_at: str
    kind: str = "user"
