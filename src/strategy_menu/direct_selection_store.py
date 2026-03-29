from __future__ import annotations

from log import log
from .launch_method_store import get_strategy_launch_method

_direct_selections_cache = None
_direct_selections_cache_time = 0
_direct_selections_cache_method = None
_direct_selections_cache_preset_mtime = None
DIRECT_SELECTIONS_CACHE_TTL = 5.0


def invalidate_direct_selections_cache():
    """Сбрасывает кэш выборов стратегий."""
    global _direct_selections_cache_time, _direct_selections_cache_method, _direct_selections_cache_preset_mtime
    _direct_selections_cache_time = 0
    _direct_selections_cache_method = None
    _direct_selections_cache_preset_mtime = None


def get_direct_strategy_selections() -> dict:
    """
    Возвращает сохраненные выборы стратегий для прямого запуска.
    """
    import time
    global _direct_selections_cache, _direct_selections_cache_time, _direct_selections_cache_preset_mtime, _direct_selections_cache_method

    method = get_strategy_launch_method()

    cache_mtime = None
    if method == "direct_zapret1":
        try:
            from core.services import get_direct_flow_coordinator

            preset_path = get_direct_flow_coordinator().get_selected_source_path("direct_zapret1")
            cache_mtime = preset_path.stat().st_mtime if preset_path.exists() else None
        except Exception:
            cache_mtime = None
    elif method == "direct_zapret2":
        try:
            from core.services import get_direct_flow_coordinator

            preset_path = get_direct_flow_coordinator().get_selected_source_path("direct_zapret2")
            cache_mtime = preset_path.stat().st_mtime if preset_path.exists() else None
        except Exception:
            cache_mtime = None

    current_time = time.time()
    if (
        _direct_selections_cache is not None
        and current_time - _direct_selections_cache_time < DIRECT_SELECTIONS_CACHE_TTL
        and _direct_selections_cache_method == method
        and _direct_selections_cache_preset_mtime == cache_mtime
    ):
        return _direct_selections_cache.copy()

    try:
        selections: dict[str, str] = {}
        default_selections: dict[str, str] = {}

        if method == "direct_zapret2":
            try:
                from core.presets.direct_facade import DirectPresetFacade

                selections = DirectPresetFacade.from_launch_method("direct_zapret2").get_strategy_selections() or {}
            except Exception as e:
                log(f"Ошибка чтения selected source preset для выбора стратегий direct_zapret2: {e}", "DEBUG")
                selections = {}
        elif method == "direct_zapret1":
            try:
                from core.presets.direct_facade import DirectPresetFacade

                selections = DirectPresetFacade.from_launch_method("direct_zapret1").get_strategy_selections() or {}
            except Exception as e:
                log(f"Ошибка чтения selected source preset для выбора стратегий direct_zapret1: {e}", "DEBUG")
                selections = {}
        elif method == "direct_zapret2_orchestra":
            try:
                from .strategies_registry import registry
                from preset_orchestra_zapret2 import PresetManager, ensure_default_preset_exists

                ensure_default_preset_exists()
                preset_manager = PresetManager()
                preset_selections = preset_manager.get_strategy_selections() or {}
                default_selections = registry.get_default_selections()
                selections = {k: "none" for k in registry.get_all_target_keys()}
                selections.update({k: (v or "none") for k, v in preset_selections.items()})
            except Exception as e:
                log(f"Ошибка чтения preset-zapret2-orchestra.txt для выбора стратегий: {e}", "DEBUG")
                from .strategies_registry import registry

                selections = {k: "none" for k in registry.get_all_target_keys()}
        else:
            from .strategies_registry import registry

            default_selections = registry.get_default_selections()
            selections = dict(default_selections)

        for key, default_value in default_selections.items():
            if key not in selections:
                if method == "direct_zapret2_orchestra":
                    selections[key] = "none"
                elif method in ("direct_zapret1", "direct_zapret2"):
                    continue
                else:
                    selections[key] = default_value

        _direct_selections_cache = selections
        _direct_selections_cache_time = current_time
        _direct_selections_cache_method = method
        _direct_selections_cache_preset_mtime = cache_mtime
        return selections
    except Exception as e:
        log(f"Ошибка загрузки выборов стратегий: {e}", "❌ ERROR")
        import traceback
        log(traceback.format_exc(), "DEBUG")
        if method in ("direct_zapret1", "direct_zapret2"):
            return {}
        from .strategies_registry import registry
        return registry.get_default_selections()


def set_direct_strategy_selections(selections: dict) -> bool:
    """Сохраняет выборы стратегий для прямого запуска."""
    try:
        method = get_strategy_launch_method()
        if method == "direct_zapret2":
            from core.presets.direct_facade import DirectPresetFacade

            facade = DirectPresetFacade.from_launch_method("direct_zapret2")
            payload = {
                target_key: strategy_id
                for target_key, strategy_id in (selections or {}).items()
                if str(target_key or "").strip()
            }
            facade.set_strategy_selections(payload, save_and_sync=True)
            invalidate_direct_selections_cache()
            log("Выборы стратегий сохранены (selected source preset direct_zapret2)", "DEBUG")
            return True

        if method == "direct_zapret1":
            from core.presets.direct_facade import DirectPresetFacade

            facade = DirectPresetFacade.from_launch_method("direct_zapret1")
            payload = {
                target_key: strategy_id
                for target_key, strategy_id in (selections or {}).items()
                if str(target_key or "").strip()
            }
            success = bool(facade.set_strategy_selections(payload, save_and_sync=True))
            invalidate_direct_selections_cache()
            log("Выборы стратегий сохранены (selected source preset direct_zapret1)", "DEBUG")
            return success

        if method == "direct_zapret2_orchestra":
            from .strategies_registry import registry
            from preset_orchestra_zapret2 import PresetManager, ensure_default_preset_exists

            if not ensure_default_preset_exists():
                return False

            preset_manager = PresetManager()
            payload = {
                target_key: (str((selections or {}).get(target_key) or "none").strip() or "none")
                for target_key in registry.get_all_target_keys()
            }
            preset_manager.set_strategy_selections(payload, save_and_sync=True)
            invalidate_direct_selections_cache()
            log("Выборы стратегий сохранены (preset-zapret2-orchestra.txt)", "DEBUG")
            return True

        return False
    except Exception as e:
        log(f"Ошибка сохранения выборов: {e}", "❌ ERROR")
        return False


def get_direct_strategy_for_target(target_key: str) -> str:
    """Получает выбранную стратегию для конкретного target."""
    method = get_strategy_launch_method()
    if method in ("direct_zapret2", "direct_zapret1", "direct_zapret2_orchestra"):
        selections = get_direct_strategy_selections()
        return selections.get(target_key, "none") or "none"

    from .strategies_registry import registry

    target_info = registry.get_target_info(target_key)
    if target_info:
        return target_info.default_strategy
    return "none"


def set_direct_strategy_for_target(target_key: str, strategy_id: str) -> bool:
    """Сохраняет выбранную стратегию для target."""
    method = get_strategy_launch_method()

    if method == "direct_zapret2":
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret2").set_strategy_selection(
                target_key,
                strategy_id,
                save_and_sync=True,
            )
            invalidate_direct_selections_cache()
            return True
        except Exception as e:
            log(f"Ошибка сохранения стратегии в selected source preset direct_zapret2: {e}", "DEBUG")
            return False

    if method == "direct_zapret1":
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret1").set_strategy_selection(
                target_key,
                strategy_id,
                save_and_sync=True,
            )
            invalidate_direct_selections_cache()
            return True
        except Exception as e:
            log(f"Ошибка сохранения стратегии в selected source preset direct_zapret1: {e}", "DEBUG")
            return False

    if method == "direct_zapret2_orchestra":
        try:
            from preset_orchestra_zapret2 import PresetManager, ensure_default_preset_exists

            if not ensure_default_preset_exists():
                return False

            preset_manager = PresetManager()
            preset_manager.set_strategy_selection(target_key, strategy_id or "none", save_and_sync=True)
            invalidate_direct_selections_cache()
            return True
        except Exception as e:
            log(f"Ошибка сохранения стратегии в preset-zapret2-orchestra.txt: {e}", "DEBUG")
            return False

    return False
