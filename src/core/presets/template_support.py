from __future__ import annotations

from .z2_template_runtime import (
    clear_all_deleted_presets,
    get_builtin_base_from_copy_name,
    get_category_default_syndata,
    get_default_category_settings,
    get_default_template_content,
    get_deleted_preset_names,
    get_template_canonical_name,
    get_template_content,
    mark_preset_deleted,
    overwrite_templates_to_presets,
)
from .v1_template_runtime import (
    clear_all_deleted_presets_v1,
    get_builtin_base_from_copy_name_v1,
    get_builtin_preset_content_v1,
    get_default_template_content_v1,
    get_deleted_preset_names_v1,
    get_template_canonical_name_v1,
    get_template_content_v1,
    mark_preset_deleted_v1,
    overwrite_v1_templates_to_presets,
)


def resolve_reset_template(launch_method: str, preset_name: str) -> str:
    method = str(launch_method or "").strip().lower()
    if method == "direct_zapret2":
        content = get_template_content(preset_name)
        if not content:
            base = get_builtin_base_from_copy_name(preset_name)
            if base:
                content = get_template_content(base)
        if not content:
            content = get_default_template_content()
        return str(content or "")

    content = get_template_content_v1(preset_name)
    if not content:
        base = get_builtin_base_from_copy_name_v1(preset_name)
        if base:
            content = get_template_content_v1(base)
    if not content:
        content = get_default_template_content_v1()
    if not content:
        content = get_builtin_preset_content_v1("Default")
    return str(content or "")


def reset_all_templates(launch_method: str) -> tuple[int, int, list[str]]:
    method = str(launch_method or "").strip().lower()
    if method == "direct_zapret2":
        return overwrite_templates_to_presets()

    return overwrite_v1_templates_to_presets()


def restore_deleted_templates(launch_method: str) -> None:
    method = str(launch_method or "").strip().lower()
    if method == "direct_zapret2":
        from .z2_template_runtime import ensure_templates_copied_to_presets

        clear_all_deleted_presets()
        ensure_templates_copied_to_presets()
        return

    from .v1_template_runtime import ensure_v1_templates_copied_to_presets

    clear_all_deleted_presets_v1()
    ensure_v1_templates_copied_to_presets()


def template_canonical_name(engine: str, template_origin: str) -> str | None:
    value = str(template_origin or "").strip()
    if not value:
        return None
    try:
        if str(engine or "").strip().lower() == "winws2":
            return get_template_canonical_name(value)
        if str(engine or "").strip().lower() == "winws1":
            return get_template_canonical_name_v1(value)
    except Exception:
        return None
    return None


def get_default_target_settings_v2(category_key: str | None = None) -> dict:
    if category_key is None:
        return {
            "enabled": True,
            "blob": "tls_google",
            "tls_mod": "none",
            "autottl_delta": -2,
            "autottl_min": 3,
            "autottl_max": 20,
            "tcp_flags_unset": "none",
            "out_range": 8,
            "out_range_mode": "d",
            "send_enabled": True,
            "send_repeats": 2,
            "send_ip_ttl": 0,
            "send_ip6_ttl": 0,
            "send_ip_id": "none",
            "send_badsum": False,
        }

    all_defaults = get_default_category_settings()
    if category_key not in all_defaults:
        return get_default_target_settings_v2(None)
    return get_category_default_syndata(category_key, protocol="tcp")


def get_deleted_template_names(launch_method: str) -> set[str]:
    method = str(launch_method or "").strip().lower()
    if method == "direct_zapret2":
        return set(get_deleted_preset_names() or ())

    return set(get_deleted_preset_names_v1() or ())


def mark_deleted_template(launch_method: str, template_name: str) -> bool:
    method = str(launch_method or "").strip().lower()
    name = str(template_name or "").strip()
    if not name:
        return False
    if method == "direct_zapret2":
        return bool(mark_preset_deleted(name))

    return bool(mark_preset_deleted_v1(name))
