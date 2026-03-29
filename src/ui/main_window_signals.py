from __future__ import annotations

from ui.page_names import PageName


def connect_main_window_page_signals(window) -> None:
    """Wire up page signals for MainWindow.

    Kept out of ui.main_window so the window class stays focused on
    composition/navigation instead of event wiring.
    """
    window.start_clicked = window.home_page.start_btn.clicked
    window.stop_clicked = window.home_page.stop_btn.clicked
    # theme_changed replaced by display_mode_changed (theme selection removed)
    if hasattr(window.appearance_page, 'display_mode_changed'):
        window.display_mode_changed = window.appearance_page.display_mode_changed
    elif hasattr(window.appearance_page, 'theme_changed'):
        window.display_mode_changed = window.appearance_page.theme_changed

    # Zapret 2 Direct signals
    if hasattr(window, 'zapret2_strategies_page') and hasattr(window.zapret2_strategies_page, 'strategy_selected'):
        window.zapret2_strategies_page.strategy_selected.connect(window._on_strategy_selected_from_page)

    if hasattr(window, 'zapret2_strategies_page') and hasattr(window.zapret2_strategies_page, 'open_category_detail'):
        window.zapret2_strategies_page.open_category_detail.connect(window._on_open_category_detail)

    if hasattr(window, 'strategy_detail_page'):
        if hasattr(window.strategy_detail_page, 'back_clicked'):
            window.strategy_detail_page.back_clicked.connect(window._on_strategy_detail_back)
        if hasattr(window.strategy_detail_page, 'navigate_to_root'):
            window.strategy_detail_page.navigate_to_root.connect(
                lambda: window.show_page(PageName.ZAPRET2_DIRECT_CONTROL)
            )
        if hasattr(window.strategy_detail_page, 'strategy_selected'):
            window.strategy_detail_page.strategy_selected.connect(window._on_strategy_detail_selected)
        if hasattr(window.strategy_detail_page, 'filter_mode_changed'):
            window.strategy_detail_page.filter_mode_changed.connect(window._on_strategy_detail_filter_mode_changed)

    if hasattr(window, 'zapret2_orchestra_strategies_page') and hasattr(window.zapret2_orchestra_strategies_page, 'strategy_selected'):
        window.zapret2_orchestra_strategies_page.strategy_selected.connect(window._on_strategy_selected_from_page)

    window.autostart_page.autostart_enabled.connect(window._on_autostart_enabled)
    window.autostart_page.autostart_disabled.connect(window._on_autostart_disabled)
    window.autostart_page.navigate_to_dpi_settings.connect(window._navigate_to_dpi_settings)

    # Connect display mode change to autostart page theme refresh
    if hasattr(window.appearance_page, 'display_mode_changed'):
        window.appearance_page.display_mode_changed.connect(
            lambda _mode: window.autostart_page.on_theme_changed()
        )
    elif hasattr(window.appearance_page, 'theme_changed'):
        window.appearance_page.theme_changed.connect(window.autostart_page.on_theme_changed)

    # Connect background preset change
    if hasattr(window.appearance_page, 'background_preset_changed'):
        window.appearance_page.background_preset_changed.connect(window._on_background_preset_changed)

    window.control_page.start_btn.clicked.connect(window._proxy_start_click)
    window.control_page.stop_winws_btn.clicked.connect(window._proxy_stop_click)
    window.control_page.stop_and_exit_btn.clicked.connect(window._proxy_stop_and_exit)
    window.control_page.test_btn.clicked.connect(window._proxy_test_click)
    window.control_page.folder_btn.clicked.connect(window._proxy_folder_click)

    try:
        page = getattr(window, "zapret2_direct_control_page", None)
        if page is not None:
            page.start_btn.clicked.connect(window._proxy_start_click)
            page.stop_winws_btn.clicked.connect(window._proxy_stop_click)
            page.stop_and_exit_btn.clicked.connect(window._proxy_stop_and_exit)
            page.test_btn.clicked.connect(window._proxy_test_click)
            page.folder_btn.clicked.connect(window._proxy_folder_click)
            if hasattr(page, 'navigate_to_presets'):
                page.navigate_to_presets.connect(
                    lambda: window.show_page(PageName.ZAPRET2_USER_PRESETS))
            if hasattr(page, 'navigate_to_direct_launch'):
                page.navigate_to_direct_launch.connect(
                    lambda: window.show_page(PageName.ZAPRET2_DIRECT))
            if hasattr(page, 'navigate_to_blobs'):
                page.navigate_to_blobs.connect(
                    lambda: window.show_page(PageName.BLOBS))
            if hasattr(page, 'direct_mode_changed'):
                page.direct_mode_changed.connect(window._on_direct_mode_changed)
    except Exception:
        pass

    try:
        page = getattr(window, "orchestra_zapret2_control_page", None)
        if page is not None:
            page.start_btn.clicked.connect(window._proxy_start_click)
            page.stop_winws_btn.clicked.connect(window._proxy_stop_click)
            page.stop_and_exit_btn.clicked.connect(window._proxy_stop_and_exit)
            page.test_btn.clicked.connect(window._proxy_test_click)
            page.folder_btn.clicked.connect(window._proxy_folder_click)
            if hasattr(page, 'navigate_to_presets'):
                page.navigate_to_presets.connect(
                    lambda: window.show_page(PageName.ZAPRET2_ORCHESTRA_USER_PRESETS)
                )
            if hasattr(page, 'navigate_to_direct_launch'):
                page.navigate_to_direct_launch.connect(
                    lambda: window.show_page(PageName.ZAPRET2_ORCHESTRA)
                )
            if hasattr(page, 'navigate_to_blobs'):
                page.navigate_to_blobs.connect(
                    lambda: window.show_page(PageName.BLOBS)
                )
    except Exception:
        pass

    # Zapret 1 Direct Control page — start/stop buttons + navigation
    try:
        z1_page = getattr(window, "zapret1_direct_control_page", None)
        if z1_page is not None:
            if hasattr(z1_page, 'start_btn'):
                z1_page.start_btn.clicked.connect(window._proxy_start_click)
            if hasattr(z1_page, 'stop_winws_btn'):
                z1_page.stop_winws_btn.clicked.connect(window._proxy_stop_click)
            if hasattr(z1_page, 'stop_and_exit_btn'):
                z1_page.stop_and_exit_btn.clicked.connect(window._proxy_stop_and_exit)
            if hasattr(z1_page, 'test_btn'):
                z1_page.test_btn.clicked.connect(window._proxy_test_click)
            if hasattr(z1_page, 'folder_btn'):
                z1_page.folder_btn.clicked.connect(window._proxy_folder_click)
            if hasattr(z1_page, 'navigate_to_strategies'):
                z1_page.navigate_to_strategies.connect(
                    lambda: window.show_page(PageName.ZAPRET1_DIRECT))
            if hasattr(z1_page, 'navigate_to_presets'):
                z1_page.navigate_to_presets.connect(
                    lambda: window.show_page(PageName.ZAPRET1_USER_PRESETS))
    except Exception:
        pass

    # Back nav from subpages (Мои пресеты / Прямой запуск / Блобы → Управление)
    for _back_attr in ("zapret2_user_presets_page", "zapret2_strategies_page", "blobs_page"):
        _back_page = getattr(window, _back_attr, None)
        if _back_page is not None and hasattr(_back_page, "back_clicked"):
            try:
                _back_page.back_clicked.connect(window._show_active_zapret2_control_page)
            except Exception:
                pass

    _orch_back_page = getattr(window, "orchestra_zapret2_user_presets_page", None)
    if _orch_back_page is not None and hasattr(_orch_back_page, "back_clicked"):
        try:
            _orch_back_page.back_clicked.connect(
                lambda: window.show_page(PageName.ZAPRET2_ORCHESTRA_CONTROL)
            )
        except Exception:
            pass

    if hasattr(window.home_page, 'premium_link_btn'):
        window.home_page.premium_link_btn.clicked.connect(window._open_subscription_dialog)

    window.home_page.navigate_to_control.connect(window._navigate_to_control)
    window.home_page.navigate_to_strategies.connect(window._navigate_to_strategies)
    window.home_page.navigate_to_autostart.connect(window.show_autostart_page)
    window.home_page.navigate_to_premium.connect(window._open_subscription_dialog)
    if hasattr(window.home_page, 'navigate_to_dpi_settings'):
        window.home_page.navigate_to_dpi_settings.connect(
            lambda: window.show_page(PageName.DPI_SETTINGS))

    if hasattr(window.appearance_page, 'subscription_btn'):
        window.appearance_page.subscription_btn.clicked.connect(window._open_subscription_dialog)

    if hasattr(window.appearance_page, 'background_refresh_needed'):
        window.appearance_page.background_refresh_needed.connect(window._on_background_refresh_needed)

    if hasattr(window.appearance_page, 'opacity_changed'):
        window.appearance_page.opacity_changed.connect(window._on_opacity_changed)

    if hasattr(window.appearance_page, 'mica_changed'):
        window.appearance_page.mica_changed.connect(window._on_mica_changed)

    if hasattr(window.appearance_page, 'animations_changed'):
        window.appearance_page.animations_changed.connect(window._on_animations_changed)

    if hasattr(window.appearance_page, 'smooth_scroll_changed'):
        window.appearance_page.smooth_scroll_changed.connect(window._on_smooth_scroll_changed)

    if hasattr(window.appearance_page, 'ui_language_changed'):
        window.appearance_page.ui_language_changed.connect(window._on_ui_language_changed)

    if hasattr(window.about_page, 'premium_btn'):
        window.about_page.premium_btn.clicked.connect(window._open_subscription_dialog)

    if hasattr(window.about_page, 'update_btn'):
        window.about_page.update_btn.clicked.connect(lambda: window.show_page(PageName.SERVERS))

    if hasattr(window.premium_page, 'subscription_updated'):
        window.premium_page.subscription_updated.connect(window._on_subscription_updated)

    window.dpi_settings_page.launch_method_changed.connect(window._on_launch_method_changed)
    if hasattr(window, 'orchestra_page'):
        window.orchestra_page.clear_learned_requested.connect(window._on_clear_learned_requested)

    try:
        from preset_zapret2.preset_store import get_preset_store
        store = get_preset_store()
        store.preset_switched.connect(window._preset_runtime_coordinator.handle_preset_switched)
    except Exception:
        pass

    try:
        from preset_orchestra_zapret2.preset_store import get_preset_store

        orchestra_store = get_preset_store()
        orchestra_store.preset_switched.connect(window._preset_runtime_coordinator.handle_preset_switched)
    except Exception:
        pass

    try:
        from preset_zapret1.preset_store import get_preset_store_v1
        store_v1 = get_preset_store_v1()
        store_v1.preset_switched.connect(window._preset_runtime_coordinator.handle_preset_switched)
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
