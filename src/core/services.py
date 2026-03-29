from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .direct_flow import DirectFlowCoordinator
from .paths import AppPaths
from .presets.repository import PresetRepository
from .presets.selection_service import PresetSelectionService


@lru_cache(maxsize=1)
def get_app_paths() -> AppPaths:
    from config import get_zapret_userdata_dir

    root = Path(get_zapret_userdata_dir()).resolve()
    return AppPaths(user_root=root, local_root=root)


@lru_cache(maxsize=1)
def get_preset_repository() -> PresetRepository:
    return PresetRepository(get_app_paths())


@lru_cache(maxsize=1)
def get_selection_service() -> PresetSelectionService:
    return PresetSelectionService(get_app_paths(), get_preset_repository())


@lru_cache(maxsize=1)
def get_direct_flow_coordinator() -> DirectFlowCoordinator:
    return DirectFlowCoordinator()


@lru_cache(maxsize=1)
def get_preset_store():
    from .presets.runtime_store import DirectRuntimePresetStore

    return DirectRuntimePresetStore("winws2")


@lru_cache(maxsize=1)
def get_preset_store_v1():
    from .presets.runtime_store import DirectRuntimePresetStore

    return DirectRuntimePresetStore("winws1")


def reset_cached_services() -> None:
    get_direct_flow_coordinator.cache_clear()
    get_selection_service.cache_clear()
    get_preset_repository.cache_clear()
    get_app_paths.cache_clear()
    get_preset_store.cache_clear()
    get_preset_store_v1.cache_clear()
