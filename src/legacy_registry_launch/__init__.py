"""Legacy registry/orchestra launch helpers.

This package exists for code that still assembles launch args from
registry-driven target selections. Ordinary direct_zapret1/direct_zapret2 flow
must not depend on this package.
"""

from .builder_common import (
    calculate_required_filters,
    get_active_targets_count,
    get_strategy_display_name,
    validate_target_strategies,
)
from .selection_store import (
    get_direct_strategy_for_target,
    get_direct_strategy_selections,
    invalidate_direct_selections_cache,
    set_direct_strategy_for_target,
    set_direct_strategy_selections,
)
from .port_filters import (
    FILTERS,
    build_filter_to_targets_map,
    build_target_to_filters_map,
    get_filter_for_target,
    get_targets_for_filter,
    log_filter_category_map,
)
from .strategy_loader import load_categories, load_strategies_as_dict
from .strategies_registry import (
    TargetInfo,
    get_current_strategy_set,
    get_default_selections,
    get_strategies_registry,
    get_tab_names,
    get_tab_tooltips,
    get_target_info,
    get_target_strategies,
    get_target_icon,
    registry,
    reload_targets,
)
from .zapret1_strategy_builder import combine_strategies_v1
from .zapret2_strategy_builder import HARDCODED_BLOBS, combine_strategies_v2

__all__ = [
    "calculate_required_filters",
    "get_active_targets_count",
    "get_strategy_display_name",
    "validate_target_strategies",
    "get_direct_strategy_for_target",
    "get_direct_strategy_selections",
    "invalidate_direct_selections_cache",
    "set_direct_strategy_for_target",
    "set_direct_strategy_selections",
    "FILTERS",
    "build_filter_to_targets_map",
    "build_target_to_filters_map",
    "get_filter_for_target",
    "get_targets_for_filter",
    "log_filter_category_map",
    "load_categories",
    "load_strategies_as_dict",
    "TargetInfo",
    "get_current_strategy_set",
    "get_default_selections",
    "get_strategies_registry",
    "get_tab_names",
    "get_tab_tooltips",
    "get_target_info",
    "get_target_strategies",
    "get_target_icon",
    "registry",
    "reload_targets",
    "combine_strategies_v1",
    "combine_strategies_v2",
    "HARDCODED_BLOBS",
]
