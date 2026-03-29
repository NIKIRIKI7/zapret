from __future__ import annotations

from ui.page_names import PageName


def refresh_page_if_possible(window, page_name: PageName) -> None:
    page = window._ensure_page(page_name)
    if page is None:
        return
    loader = getattr(page, "_load_presets", None)
    if callable(loader):
        try:
            loader()
        except Exception:
            pass


def show_active_zapret2_user_presets_page(window) -> None:
    try:
        from strategy_menu import get_strategy_launch_method

        method = (get_strategy_launch_method() or "").strip().lower()
    except Exception:
        method = ""

    if method == "direct_zapret2_orchestra":
        refresh_page_if_possible(window, PageName.ZAPRET2_ORCHESTRA_USER_PRESETS)
        window.show_page(PageName.ZAPRET2_ORCHESTRA_USER_PRESETS)
    else:
        refresh_page_if_possible(window, PageName.ZAPRET2_USER_PRESETS)
        window.show_page(PageName.ZAPRET2_USER_PRESETS)


def show_zapret1_user_presets_page(window) -> None:
    refresh_page_if_possible(window, PageName.ZAPRET1_USER_PRESETS)
    window.show_page(PageName.ZAPRET1_USER_PRESETS)


def refresh_active_zapret2_user_presets_page(window) -> None:
    try:
        from strategy_menu import get_strategy_launch_method

        method = (get_strategy_launch_method() or "").strip().lower()
    except Exception:
        method = ""
    target = PageName.ZAPRET2_ORCHESTRA_USER_PRESETS if method == "direct_zapret2_orchestra" else PageName.ZAPRET2_USER_PRESETS
    refresh_page_if_possible(window, target)


def refresh_zapret1_user_presets_page(window) -> None:
    refresh_page_if_possible(window, PageName.ZAPRET1_USER_PRESETS)


def open_zapret2_preset_detail(window, preset_name: str) -> None:
    page = window._ensure_page(PageName.ZAPRET2_PRESET_DETAIL)
    if page is None:
        return
    if hasattr(page, "set_preset_file_name"):
        page.set_preset_file_name(preset_name)
    window.show_page(PageName.ZAPRET2_PRESET_DETAIL)


def open_zapret1_preset_detail(window, preset_name: str) -> None:
    page = window._ensure_page(PageName.ZAPRET1_PRESET_DETAIL)
    if page is None:
        return
    if hasattr(page, "set_preset_file_name"):
        page.set_preset_file_name(preset_name)
    window.show_page(PageName.ZAPRET1_PRESET_DETAIL)


def open_zapret2_preset_folders(window) -> None:
    window._ensure_page(PageName.ZAPRET2_PRESET_FOLDERS)
    window.show_page(PageName.ZAPRET2_PRESET_FOLDERS)


def open_zapret1_preset_folders(window) -> None:
    window._ensure_page(PageName.ZAPRET1_PRESET_FOLDERS)
    window.show_page(PageName.ZAPRET1_PRESET_FOLDERS)


def redirect_to_strategies_page_for_method(window, method: str) -> None:
    current = None
    try:
        current = window.stackedWidget.currentWidget() if hasattr(window, "stackedWidget") else None
    except Exception:
        current = None

    strategies_context_pages = set()
    for attr in (
        "dpi_settings_page", "zapret2_user_presets_page", "zapret2_strategies_page",
        "orchestra_zapret2_user_presets_page", "zapret2_orchestra_strategies_page",
        "orchestra_zapret2_control_page", "zapret1_direct_control_page",
        "zapret1_strategies_page", "zapret1_user_presets_page", "strategy_detail_page",
        "orchestra_strategy_detail_page",
    ):
        page = getattr(window, attr, None)
        if page is not None:
            strategies_context_pages.add(page)

    if current is not None and current not in strategies_context_pages:
        return

    if method == "orchestra":
        target_page = PageName.ORCHESTRA
    elif method == "direct_zapret2_orchestra":
        target_page = PageName.ZAPRET2_ORCHESTRA_CONTROL
    elif method == "direct_zapret2":
        target_page = PageName.ZAPRET2_DIRECT_CONTROL
    elif method == "direct_zapret1":
        target_page = PageName.ZAPRET1_DIRECT_CONTROL
    else:
        target_page = PageName.CONTROL

    window.show_page(target_page)
