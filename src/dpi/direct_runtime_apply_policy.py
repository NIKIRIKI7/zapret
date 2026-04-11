from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from log import log

if TYPE_CHECKING:
    from main import LupiDPIApp


def _is_dpi_running(app: "LupiDPIApp") -> bool:
    try:
        controller = getattr(app, "dpi_controller", None)
        if controller is not None:
            return bool(controller.is_running())
    except Exception as e:
        log(f"Ошибка проверки состояния DPI: {e}", "DEBUG")
    return False


def _direct_filter_flags(launch_method: str) -> tuple[str, ...]:
    method = str(launch_method or "").strip().lower()
    if method == "direct_zapret1":
        return ("--wf-tcp=", "--wf-udp=")
    return ("--wf-tcp-out", "--wf-udp-out", "--wf-raw-part")


def _get_selected_direct_preset_path(launch_method: str) -> Path | None:
    method = str(launch_method or "").strip().lower()
    if method not in {"direct_zapret1", "direct_zapret2"}:
        return None
    try:
        from core.services import get_direct_flow_coordinator

        snapshot = get_direct_flow_coordinator().get_startup_snapshot(method, require_filters=False)
        return Path(snapshot.preset_path)
    except Exception:
        return None


def request_direct_runtime_content_apply(
    app: "LupiDPIApp",
    *,
    launch_method: str,
    reason: str,
    target_key: str | None = None,
) -> bool:
    """Apply runtime reaction for edits to the currently selected direct preset."""
    method = str(launch_method or "").strip().lower()
    if method not in {"direct_zapret1", "direct_zapret2"}:
        log(f"Direct runtime apply skipped: unsupported method {method}", "DEBUG")
        return False

    if not hasattr(app, "dpi_controller") or not app.dpi_controller:
        log("Direct runtime apply skipped: dpi_controller not found", "DEBUG")
        return False

    if not _is_dpi_running(app):
        log(f"Direct runtime apply skipped: DPI not running ({method})", "DEBUG")
        return False

    preset_path = _get_selected_direct_preset_path(method)
    if preset_path is None or not preset_path.exists():
        log(f"Direct runtime apply: active preset missing for {method}, stopping DPI", "WARNING")
        app.dpi_controller.stop_dpi_async()
        return True

    try:
        content = preset_path.read_text(encoding="utf-8")
    except Exception as e:
        log(f"Direct runtime apply: failed to read preset for {method}: {e}", "ERROR")
        return False

    if not any(flag in content for flag in _direct_filter_flags(method)):
        log(f"Direct runtime apply: preset has no active filters for {method}, stopping DPI", "INFO")
        app.dpi_controller.stop_dpi_async()
        return True

    target_info = f" [{target_key}]" if target_key else ""
    log(
        f"Direct runtime apply{target_info} ({method}, reason={reason}) - watcher-driven hot-reload should apply changes automatically",
        "INFO",
    )
    return True
