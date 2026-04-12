from __future__ import annotations


def connect_main_window_page_signals(window) -> None:
    """Wire up page signals for MainWindow.

    Kept out of ui.main_window so the window class stays focused on
    composition/navigation instead of event wiring.
    """
    try:
        store = window.app_context.preset_store
        store.preset_switched.connect(window._preset_runtime_coordinator.handle_preset_switched)
        store.preset_identity_changed.connect(window._preset_runtime_coordinator.handle_preset_identity_changed)
    except Exception:
        pass

    try:
        store_v1 = window.app_context.preset_store_v1
        store_v1.preset_switched.connect(window._preset_runtime_coordinator.handle_preset_switched)
        store_v1.preset_identity_changed.connect(window._preset_runtime_coordinator.handle_preset_identity_changed)
    except Exception:
        pass

    try:
        window._preset_runtime_coordinator.setup_active_preset_file_watcher()
    except Exception:
        pass

    try:
        from config.reg import get_smooth_scroll_enabled
        window._on_smooth_scroll_changed(get_smooth_scroll_enabled())
    except Exception:
        pass

    try:
        from config.reg import get_editor_smooth_scroll_enabled

        window._on_editor_smooth_scroll_changed(get_editor_smooth_scroll_enabled())
    except Exception:
        pass
