# launcher_common/builder_factory.py
"""
Factory module for strategy lists.
Выбирает между V1 и V2 реализациями в зависимости от режима.

For backwards compatibility, maintains the same API:
- combine_strategies(**kwargs) - main entry point
- calculate_required_filters(...)
- get_strategy_display_name(...)
- get_active_targets_count(...)
- validate_target_strategies(...)
"""

from log import log
from strategy_menu import get_strategy_launch_method

# Re-export common utilities for backwards compatibility
from .builder_common import (
    calculate_required_filters,
    _apply_settings,
    _clean_spaces,
    get_strategy_display_name,
    get_active_targets_count,
    validate_target_strategies
)

# Import both implementations
from zapret1_launcher.strategy_builder import combine_strategies_v1
from zapret2_launcher.strategy_builder import combine_strategies_v2


def _combine_direct_source_preset(launch_method: str) -> dict:
    """Собирает прямой запуск из выбранного source preset, без legacy builders."""
    from core.presets.direct_facade import DirectPresetFacade
    from core.services import get_direct_flow_coordinator

    method = str(launch_method or "").strip().lower()
    profile = get_direct_flow_coordinator().ensure_launch_profile(method, require_filters=False)
    facade = DirectPresetFacade.from_launch_method(method)
    selections = facade.get_strategy_selections() or {}
    active_targets = sum(1 for strategy_id in selections.values() if (strategy_id or "none") != "none")

    log(f"combine_strategies: using selected source preset for {method}: {profile.launch_config_path}", "DEBUG")

    return {
        "name": profile.display_name,
        "description": profile.display_name,
        "version": "source-preset",
        "provider": "direct_preset_core",
        "author": "DirectPresetCore",
        "updated": "2026",
        "all_sites": True,
        "args": f"@{profile.launch_config_path}",
        "_is_builtin": False,
        "_is_preset_file": True,
        "_direct_source_preset": True,
        "_is_v1": method == "direct_zapret1",
        "_is_orchestra": False,
        "_active_targets": active_targets,
    }


def combine_strategies(**kwargs) -> dict:
    """
    Возвращает итоговую конфигурацию запуска для текущего режима.

    Для direct_zapret1/direct_zapret2 больше не строит запуск из category selections:
    в этих режимах источником истины является выбранный source preset.

    Returns:
        dict с ключами:
        - args: командная строка
        - name: отображаемое имя
        - _active_targets: количество активных target'ов
        - _is_orchestra: флаг оркестратора (только V2)
    """
    launch_method = get_strategy_launch_method()

    if launch_method in {"direct_zapret1", "direct_zapret2"}:
        return _combine_direct_source_preset(launch_method)

    # direct_zapret2_orchestra и orchestra пока остаются на legacy V2 builder.
    is_orchestra = launch_method == "direct_zapret2_orchestra"
    log(f"combine_strategies: using V2 (winws2.exe), orchestra={is_orchestra}", "DEBUG")
    return combine_strategies_v2(is_orchestra=is_orchestra, **kwargs)
