"""Ленивые экспорты Zapret1 UI pages."""

from __future__ import annotations

from importlib import import_module


_PAGE_EXPORTS: dict[str, tuple[str, str]] = {
    "Zapret1DirectControlPage": (".direct_control_page", "Zapret1DirectControlPage"),
    "Zapret1StrategiesPage": (".direct_zapret1_page", "Zapret1StrategiesPage"),
    "Zapret1UserPresetsPage": ("preset_zapret1.ui.user_presets_page", "Zapret1UserPresetsPage"),
    "Zapret1StrategyDetailPage": (".strategy_detail_page_v1", "Zapret1StrategyDetailPage"),
    "Zapret1PresetDetailPage": ("preset_zapret1.ui.preset_detail_page", "Zapret1PresetDetailPage"),
}

__all__ = list(_PAGE_EXPORTS)


def __getattr__(name: str):
    spec = _PAGE_EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = spec
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
