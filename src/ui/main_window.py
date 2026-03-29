# ui/main_window.py
"""
Главное окно приложения — навигация через qfluentwidgets FluentWindow.

Все страницы добавляются через addSubInterface() вместо ручного SideNavBar + QStackedWidget.
Бизнес-логика (сигналы, обработчики) сохранена без изменений.
"""
from PyQt6.QtCore import QTimer, QCoreApplication, QEventLoop, pyqtSignal, Qt, QModelIndex
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QCompleter
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from importlib import import_module
from typing import Any, cast


try:
    from qfluentwidgets import (
        NavigationItemPosition, FluentIcon,
    )
    try:
        from qfluentwidgets import SearchLineEdit
    except ImportError:
        SearchLineEdit = QLineEdit
    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False
    NavigationItemPosition = cast(Any, None)
    FluentIcon = cast(Any, None)
    SearchLineEdit = QLineEdit

from ui.page_names import PageName, SectionName
from ui.mode_page_scope import (
    get_sidebar_search_pages_for_method,
    should_add_nav_page_on_init,
)
from ui.text_catalog import (
    find_search_entries,
    format_search_result,
    get_nav_page_label,
    normalize_language,
    tr as tr_catalog,
)
from ui.main_window_compat import setup_main_window_compatibility_attrs
from ui.main_window_navigation import (
    open_zapret1_preset_detail,
    open_zapret1_preset_folders,
    open_zapret2_preset_detail,
    open_zapret2_preset_folders,
    redirect_to_strategies_page_for_method,
    refresh_active_zapret2_user_presets_page,
    refresh_page_if_possible,
    refresh_zapret1_user_presets_page,
    show_active_zapret2_user_presets_page,
    show_zapret1_user_presets_page,
)
from ui.main_window_refresh import refresh_main_window_pages_after_preset_switch
from ui.main_window_signals import connect_main_window_page_signals
from core.runtime.preset_runtime_coordinator import (
    PresetRuntimeCoordinator,
    resolve_active_preset_watch_path,
)

# ---------------------------------------------------------------------------
# Page class specs — UNCHANGED from original
# ---------------------------------------------------------------------------

_PAGE_CLASS_SPECS: dict[PageName, tuple[str, str, str]] = {
    PageName.HOME: ("home_page", "ui.pages.home_page", "HomePage"),
    PageName.CONTROL: ("control_page", "ui.pages.control_page", "ControlPage"),
    PageName.ZAPRET2_DIRECT_CONTROL: (
        "zapret2_direct_control_page",
        "ui.pages.zapret2.direct_control_page",
        "Zapret2DirectControlPage",
    ),
    PageName.ZAPRET2_DIRECT: (
        "zapret2_strategies_page",
        "ui.pages.zapret2.direct_zapret2_page",
        "Zapret2StrategiesPageNew",
    ),
    PageName.ZAPRET2_STRATEGY_DETAIL: (
        "strategy_detail_page",
        "ui.pages.zapret2.strategy_detail_page",
        "StrategyDetailPage",
    ),
    PageName.ZAPRET2_PRESET_DETAIL: (
        "zapret2_preset_detail_page",
        "ui.pages.zapret2.preset_detail_page",
        "Zapret2PresetDetailPage",
    ),
    PageName.ZAPRET2_PRESET_FOLDERS: (
        "zapret2_preset_folders_page",
        "ui.pages.zapret2.preset_folders_page",
        "Zapret2PresetFoldersPage",
    ),
    PageName.ZAPRET2_ORCHESTRA: (
        "zapret2_orchestra_strategies_page",
        "ui.pages.zapret2_orchestra_strategies_page",
        "Zapret2OrchestraStrategiesPage",
    ),
    PageName.ZAPRET2_ORCHESTRA_CONTROL: (
        "orchestra_zapret2_control_page",
        "ui.pages.orchestra_zapret2.direct_control_page",
        "OrchestraZapret2DirectControlPage",
    ),
    PageName.ZAPRET2_ORCHESTRA_USER_PRESETS: (
        "orchestra_zapret2_user_presets_page",
        "ui.pages.zapret2.user_presets_page",
        "Zapret2UserPresetsPage",
    ),
    PageName.ZAPRET2_ORCHESTRA_STRATEGY_DETAIL: (
        "orchestra_strategy_detail_page",
        "ui.pages.orchestra_zapret2.strategy_detail_page",
        "OrchestraZapret2StrategyDetailPage",
    ),
    PageName.ZAPRET1_DIRECT_CONTROL: (
        "zapret1_direct_control_page",
        "ui.pages.zapret1.direct_control_page",
        "Zapret1DirectControlPage",
    ),
    PageName.ZAPRET1_DIRECT: (
        "zapret1_strategies_page",
        "ui.pages.zapret1.direct_zapret1_page",
        "Zapret1StrategiesPage",
    ),
    PageName.ZAPRET1_USER_PRESETS: (
        "zapret1_user_presets_page",
        "ui.pages.zapret1.user_presets_page",
        "Zapret1UserPresetsPage",
    ),
    PageName.ZAPRET1_STRATEGY_DETAIL: (
        "zapret1_strategy_detail_page",
        "ui.pages.zapret1.strategy_detail_page_v1",
        "Zapret1StrategyDetailPage",
    ),
    PageName.ZAPRET1_PRESET_DETAIL: (
        "zapret1_preset_detail_page",
        "ui.pages.zapret1.preset_detail_page",
        "Zapret1PresetDetailPage",
    ),
    PageName.ZAPRET1_PRESET_FOLDERS: (
        "zapret1_preset_folders_page",
        "ui.pages.zapret1.preset_folders_page",
        "Zapret1PresetFoldersPage",
    ),
    PageName.HOSTLIST: ("hostlist_page", "ui.pages.hostlist_page", "HostlistPage"),
    PageName.BLOBS: ("blobs_page", "ui.pages.blobs_page", "BlobsPage"),
    PageName.DPI_SETTINGS: ("dpi_settings_page", "ui.pages.dpi_settings_page", "DpiSettingsPage"),
    PageName.ZAPRET2_USER_PRESETS: (
        "zapret2_user_presets_page",
        "ui.pages.zapret2.user_presets_page",
        "Zapret2UserPresetsPage",
    ),
    PageName.NETROGAT: ("netrogat_page", "ui.pages.netrogat_page", "NetrogatPage"),
    PageName.CUSTOM_DOMAINS: ("custom_domains_page", "ui.pages.custom_domains_page", "CustomDomainsPage"),
    PageName.CUSTOM_IPSET: ("custom_ipset_page", "ui.pages.custom_ipset_page", "CustomIpSetPage"),
    PageName.AUTOSTART: ("autostart_page", "ui.pages.autostart_page", "AutostartPage"),
    PageName.NETWORK: ("network_page", "ui.pages.network_page", "NetworkPage"),
    PageName.HOSTS: ("hosts_page", "ui.pages.hosts_page", "HostsPage"),
    PageName.BLOCKCHECK: ("blockcheck_page", "ui.pages.blockcheck_page", "BlockcheckPage"),
    PageName.APPEARANCE: ("appearance_page", "ui.pages.appearance_page", "AppearancePage"),
    PageName.PREMIUM: ("premium_page", "ui.pages.premium_page", "PremiumPage"),
    PageName.LOGS: ("logs_page", "ui.pages.logs_page", "LogsPage"),
    PageName.SERVERS: ("servers_page", "ui.pages.servers_page", "ServersPage"),
    PageName.ABOUT: ("about_page", "ui.pages.about_page", "AboutPage"),
    PageName.SUPPORT: ("support_page", "ui.pages.support_page", "SupportPage"),
    PageName.ORCHESTRA: ("orchestra_page", "ui.pages.orchestra_page", "OrchestraPage"),
    PageName.ORCHESTRA_SETTINGS: (
        "orchestra_settings_page",
        "ui.pages.orchestra",
        "OrchestraSettingsPage",
    ),
    PageName.TELEGRAM_PROXY: (
        "telegram_proxy_page",
        "ui.pages.telegram_proxy_page",
        "TelegramProxyPage",
    ),
}

_PAGE_ALIASES: dict[PageName, PageName] = {
    PageName.IPSET: PageName.HOSTLIST,
    # Legacy routes kept for backward compatibility
    PageName.DIAGNOSTICS_TAB: PageName.BLOCKCHECK,
    PageName.CONNECTION_TEST: PageName.BLOCKCHECK,
    PageName.DNS_CHECK: PageName.BLOCKCHECK,
}

_EAGER_PAGE_NAMES_BASE: tuple[PageName, ...] = (
    PageName.AUTOSTART,
    PageName.DPI_SETTINGS,
    PageName.APPEARANCE,
    PageName.ABOUT,
    PageName.PREMIUM,
)

_EAGER_MODE_ENTRY_PAGE: dict[str, PageName] = {
    "direct_zapret2": PageName.ZAPRET2_DIRECT_CONTROL,
    "direct_zapret2_orchestra": PageName.ZAPRET2_ORCHESTRA_CONTROL,
    "direct_zapret1": PageName.ZAPRET1_DIRECT_CONTROL,
    "orchestra": PageName.ORCHESTRA,
}


# ---------------------------------------------------------------------------
# Navigation icon mapping (SectionName/PageName -> FluentIcon)
# ---------------------------------------------------------------------------
_NAV_ICONS = {
    PageName.HOME: FluentIcon.HOME if HAS_FLUENT else None,
    PageName.CONTROL: FluentIcon.COMMAND_PROMPT if HAS_FLUENT else None,
    PageName.ZAPRET2_DIRECT_CONTROL: FluentIcon.GAME if HAS_FLUENT else None,
    PageName.AUTOSTART: FluentIcon.POWER_BUTTON if HAS_FLUENT else None,
    PageName.NETWORK: FluentIcon.WIFI if HAS_FLUENT else None,
    PageName.HOSTS: FluentIcon.GLOBE if HAS_FLUENT else None,
    PageName.BLOCKCHECK: FluentIcon.CODE if HAS_FLUENT else None,
    PageName.APPEARANCE: FluentIcon.PALETTE if HAS_FLUENT else None,
    PageName.PREMIUM: FluentIcon.HEART if HAS_FLUENT else None,
    PageName.LOGS: FluentIcon.HISTORY if HAS_FLUENT else None,
    PageName.ABOUT: FluentIcon.INFO if HAS_FLUENT else None,
    PageName.DPI_SETTINGS: FluentIcon.SETTING if HAS_FLUENT else None,
    PageName.HOSTLIST: FluentIcon.BOOK_SHELF if HAS_FLUENT else None,
    PageName.BLOBS: FluentIcon.CLOUD if HAS_FLUENT else None,
    PageName.NETROGAT: FluentIcon.REMOVE_FROM if HAS_FLUENT else None,
    PageName.CUSTOM_DOMAINS: FluentIcon.ADD if HAS_FLUENT else None,
    PageName.CUSTOM_IPSET: FluentIcon.ADD if HAS_FLUENT else None,
    PageName.ZAPRET2_USER_PRESETS: FluentIcon.FOLDER if HAS_FLUENT else None,
    PageName.SERVERS: FluentIcon.UPDATE if HAS_FLUENT else None,
    PageName.SUPPORT: FluentIcon.CHAT if HAS_FLUENT else None,
    PageName.ORCHESTRA: FluentIcon.MUSIC if HAS_FLUENT else None,
    PageName.ORCHESTRA_SETTINGS: FluentIcon.SETTING if HAS_FLUENT else None,
    PageName.ZAPRET2_DIRECT: FluentIcon.PLAY if HAS_FLUENT else None,
    PageName.ZAPRET2_ORCHESTRA: FluentIcon.ROBOT if HAS_FLUENT else None,
    PageName.ZAPRET2_ORCHESTRA_CONTROL: FluentIcon.GAME if HAS_FLUENT else None,
    PageName.ZAPRET2_ORCHESTRA_USER_PRESETS: FluentIcon.FOLDER if HAS_FLUENT else None,
    PageName.ZAPRET1_DIRECT_CONTROL: FluentIcon.GAME if HAS_FLUENT else None,
    PageName.ZAPRET1_DIRECT: FluentIcon.PLAY if HAS_FLUENT else None,
    PageName.ZAPRET1_USER_PRESETS: FluentIcon.FOLDER if HAS_FLUENT else None,
    PageName.TELEGRAM_PROXY: FluentIcon.SEND if HAS_FLUENT else None,
}

# Russian labels for navigation
_NAV_LABELS = {
    PageName.HOME: "Главная",
    PageName.CONTROL: "Управление",
    PageName.ZAPRET2_DIRECT_CONTROL: "Управление Zapret 2",
    PageName.AUTOSTART: "Автозапуск",
    PageName.NETWORK: "Сеть",
    PageName.HOSTS: "Редактор файла hosts",
    PageName.BLOCKCHECK: "BlockCheck",
    PageName.APPEARANCE: "Оформление",
    PageName.PREMIUM: "Донат",
    PageName.LOGS: "Логи",
    PageName.ABOUT: "О программе",
    PageName.DPI_SETTINGS: "Сменить режим DPI",
    PageName.HOSTLIST: "Листы",
    PageName.BLOBS: "Блобы",
    PageName.NETROGAT: "Исключения",
    PageName.CUSTOM_DOMAINS: "Мои hostlist",
    PageName.CUSTOM_IPSET: "Мои ipset",
    PageName.ZAPRET2_USER_PRESETS: "Мои пресеты",
    PageName.SERVERS: "Обновления",
    PageName.SUPPORT: "Поддержка",
    PageName.ORCHESTRA: "Оркестратор",
    PageName.ORCHESTRA_SETTINGS: "Настройки оркестратора",
    PageName.ZAPRET2_DIRECT: "Прямой запуск",
    PageName.ZAPRET2_ORCHESTRA: "Прямой запуск",
    PageName.ZAPRET2_ORCHESTRA_CONTROL: "Управление оркестр. Zapret 2",
    PageName.ZAPRET2_ORCHESTRA_USER_PRESETS: "Мои пресеты",
    PageName.ZAPRET1_DIRECT_CONTROL: "Управление Zapret 1",
    PageName.ZAPRET1_DIRECT: "Стратегии Z1",
    PageName.ZAPRET1_USER_PRESETS: "Мои пресеты Z1",
    PageName.TELEGRAM_PROXY: "Telegram Proxy",
}


if HAS_FLUENT:
    class _SidebarSearchNavWidget(QWidget):
        textChanged = pyqtSignal(str)

        def __init__(self, parent: QWidget | None = None):
            super().__init__(parent)
            self._search = SearchLineEdit(self)
            self._completion_timer = QTimer(self)
            self._completion_timer.setSingleShot(True)
            self._completion_timer.timeout.connect(self._show_completions_deferred)
            self._search.setPlaceholderText(tr_catalog("sidebar.search.placeholder"))
            try:
                self._search.setClearButtonEnabled(True)
            except Exception:
                pass
            self._search.textChanged.connect(self.textChanged.emit)

            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 4, 0, 4)
            layout.setSpacing(0)
            layout.addWidget(self._search)

            self.setFixedHeight(40)

        def clear(self) -> None:
            self._search.clear()

        def text(self) -> str:
            return self._search.text()

        def set_placeholder_text(self, text: str) -> None:
            self._search.setPlaceholderText(text or "")

        def set_completer(self, completer: QCompleter) -> None:
            self._search.setCompleter(completer)

        def show_completions(self) -> None:
            # Defer popup interaction to avoid re-entrant completer/model updates
            # from textChanged handlers, which can crash native Qt on Windows.
            if not self.isVisible() or not self._search.isVisible() or not self._search.hasFocus():
                return
            self._completion_timer.start(0)

        def _show_completions_deferred(self) -> None:
            completer = self._search.completer()
            if completer is None:
                return
            if not self._search.text().strip():
                return

            try:
                completion_model = completer.completionModel()
                if completion_model is not None and completion_model.rowCount() <= 0:
                    return
            except Exception:
                pass

            completer.setCompletionPrefix(self._search.text())
            # Avoid direct popup forcing here: on some Windows/Qt stacks it can
            # crash natively during re-entrant completer/model updates.


class MainWindowUI:
    """
    Mixin: creates pages and registers them with FluentWindow navigation.
    """

    def build_ui(self, width: int, height: int):
        """Build UI: create pages and populate FluentWindow navigation sidebar.

        Note: window geometry (size/position) is restored in __init__ via
        restore_window_geometry() before this is called — do NOT resize here,
        that would overwrite the saved geometry.
        """
        self.pages: dict[PageName, QWidget] = {}
        self._page_aliases: dict[PageName, PageName] = dict(_PAGE_ALIASES)
        self._lazy_signal_connections: set[str] = set()
        self._startup_ui_pump_counter = 0
        self._nav_search_query = ""
        self._nav_mode_visibility: dict[PageName, bool] = {}
        self._nav_headers: list[tuple[QWidget, tuple[PageName, ...], str]] = []
        self._sidebar_search_nav_widget = None
        self._sidebar_search_model: QStandardItemModel | None = None
        self._sidebar_search_completer: QCompleter | None = None
        self._sidebar_search_titlebar_attached = False
        self._ui_language = self._resolve_ui_language()
        self._startup_page_init_metrics: list[tuple[str, int]] = []
        self._preset_runtime_coordinator = PresetRuntimeCoordinator(
            self,
            get_launch_method=self._get_current_launch_method_for_preset_runtime,
            get_active_preset_path=resolve_active_preset_watch_path,
            is_dpi_running=lambda: bool(
                hasattr(self, "dpi_controller")
                and self.dpi_controller
                and self.dpi_controller.is_running()
            ),
            restart_dpi_async=lambda: self.dpi_controller.restart_dpi_async(),
            refresh_after_switch=self._refresh_pages_after_preset_switch,
        )

        self._page_signal_bootstrap_complete = False
        self._create_pages()

        # Register pages in navigation sidebar
        self._init_navigation()

        # Wire up signals
        connect_main_window_page_signals(self)
        self._page_signal_bootstrap_complete = True

        # Backward-compat attrs
        setup_main_window_compatibility_attrs(self)
        self._log_startup_page_init_summary()

        # Session memory
        if not hasattr(self, "_direct_zapret2_last_opened_category_key"):
            self._direct_zapret2_last_opened_category_key = None
        if not hasattr(self, "_direct_zapret2_restore_detail_on_open"):
            self._direct_zapret2_restore_detail_on_open = False

    @staticmethod
    def _get_current_launch_method_for_preset_runtime() -> str:
        try:
            from strategy_menu import get_strategy_launch_method

            return str(get_strategy_launch_method() or "").strip().lower()
        except Exception:
            return ""

    def _pump_startup_ui(self, force: bool = False) -> None:
        """Yield to event loop during heavy startup UI composition.

        Qt widgets must be created on the main GUI thread, so we can't move page
        construction to worker threads. Instead, we periodically process pending
        paint/timer events so startup splash animations remain smooth.
        """
        try:
            self._startup_ui_pump_counter = int(getattr(self, "_startup_ui_pump_counter", 0)) + 1
            if not force and (self._startup_ui_pump_counter % 2) != 0:
                return

            app = QCoreApplication.instance()
            if app is None:
                return

            app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents, 8)
        except Exception:
            pass

    def _record_startup_page_init_metric(self, page_name: PageName, elapsed_ms: int) -> None:
        elapsed_i = max(0, int(elapsed_ms))

        metrics = getattr(self, "_startup_page_init_metrics", None)
        if isinstance(metrics, list):
            metrics.append((page_name.name, elapsed_i))

        try:
            from log import log as _log

            level = "⏱ STARTUP" if elapsed_i >= 120 else "DEBUG"
            _log(f"⏱ Startup UI PageInit: {page_name.name} {elapsed_i}ms", level)
        except Exception:
            pass

    def _log_startup_page_init_summary(self) -> None:
        metrics = getattr(self, "_startup_page_init_metrics", None)
        if not isinstance(metrics, list) or not metrics:
            return

        try:
            from log import log as _log

            top = sorted(metrics, key=lambda item: item[1], reverse=True)[:6]
            summary = ", ".join(f"{name}={elapsed}ms" for name, elapsed in top)
            _log(f"⏱ Startup UI PageInit TOP: {summary}", "⏱ STARTUP")
        except Exception:
            pass

    def _get_launch_method(self) -> str:
        try:
            from strategy_menu import get_strategy_launch_method

            method = (get_strategy_launch_method() or "").strip().lower()
        except Exception:
            method = ""
        return method or "direct_zapret2"

    def _add_nav_item(self, page_name: PageName, position) -> None:
        if not HAS_FLUENT:
            return

        if page_name in getattr(self, "_nav_items", {}):
            return

        from log import log as _log

        page = self._ensure_page(page_name)
        if page is None:
            _log(f"[NAV] _add {page_name.name}: page is None - skip", "DEBUG")
            return

        icon = _NAV_ICONS.get(page_name, FluentIcon.APPLICATION)
        text = self._get_nav_label(page_name)

        if page_name == PageName.ZAPRET2_ORCHESTRA_CONTROL and page.__class__.__name__ == "Zapret2DirectControlPage":
            page.setObjectName("Zapret2DirectControlPage_Orchestra")
        elif not page.objectName():
            page.setObjectName(page.__class__.__name__)

        _log(f"[NAV] addSubInterface {page_name.name} objectName={page.objectName()!r}", "DEBUG")
        item = self.addSubInterface(page, icon, text, position=position)
        _log(f"[NAV] addSubInterface {page_name.name} item={item}", "DEBUG")
        if item is not None:
            self._nav_items[page_name] = item
        else:
            _log(f"[NAV] addSubInterface returned None for {page_name.name} - not in _nav_items!", "WARNING")

        self._pump_startup_ui()

    # ------------------------------------------------------------------
    # Navigation setup (FluentWindow sidebar)
    # ------------------------------------------------------------------

    def _init_navigation(self):
        """Populate FluentWindow's NavigationInterface with pages.

        Flat layout — no tree hierarchy, no expand/collapse groups.
        All items are top-level; mode-specific items are simply hidden/shown
        via setVisible() in _sync_nav_visibility() with no parent-size hacks.
        """
        if not HAS_FLUENT:
            return

        POS_SCROLL = NavigationItemPosition.SCROLL
        current_method = self._get_launch_method()

        self._nav_items: dict = {}
        self._nav_search_query = ""
        self._nav_mode_visibility = {}
        self._nav_headers = []
        self._sidebar_search_nav_widget = None
        self._sidebar_search_model = None
        self._sidebar_search_completer = None
        self._sidebar_search_titlebar_attached = False

        def _add(page_name, position=POS_SCROLL):
            if not should_add_nav_page_on_init(page_name, current_method):
                return
            self._add_nav_item(page_name, position)

        nav = self.navigationInterface  # shorthand

        if HAS_FLUENT:
            self._sidebar_search_nav_widget = _SidebarSearchNavWidget()
            self._sidebar_search_nav_widget.textChanged.connect(self._on_sidebar_search_changed)
            self._sidebar_search_nav_widget.set_placeholder_text(
                tr_catalog("sidebar.search.placeholder", language=self._ui_language)
            )
            self._setup_sidebar_search_completer()
            self._attach_sidebar_search_to_titlebar()
            self._update_titlebar_search_width()

        # ── Верхние ──────────────────────────────────────────────────────────
        _add(PageName.HOME)
        _add(PageName.CONTROL)
        _add(PageName.ZAPRET2_DIRECT_CONTROL)
        _add(PageName.ZAPRET2_ORCHESTRA_CONTROL)
        _add(PageName.ZAPRET1_DIRECT_CONTROL)
        _add(PageName.ORCHESTRA)

        # ── Стратегии (под-раздел) ────────────────────────────────────────────
        settings_header_key = "nav.header.settings"
        settings_header = nav.addItemHeader(tr_catalog(settings_header_key, language=self._ui_language), POS_SCROLL)
        settings_pages = (
            PageName.HOSTLIST,
            PageName.ORCHESTRA_SETTINGS,
            PageName.DPI_SETTINGS,
        )
        for page_name in settings_pages:
            _add(page_name)
        self._nav_headers.append((settings_header, settings_pages, settings_header_key))

        # BLOBS removed from nav — accessible via direct_control_page card

        # ── Система ───────────────────────────────────────────────────────────
        system_header_key = "nav.header.system"
        system_header = nav.addItemHeader(tr_catalog(system_header_key, language=self._ui_language), POS_SCROLL)
        system_pages = (PageName.AUTOSTART, PageName.NETWORK, PageName.TELEGRAM_PROXY)
        for page_name in system_pages:
            _add(page_name)
        self._nav_headers.append((system_header, system_pages, system_header_key))

        # ── Диагностика ───────────────────────────────────────────────────────
        diagnostics_header_key = "nav.header.diagnostics"
        diagnostics_header = nav.addItemHeader(tr_catalog(diagnostics_header_key, language=self._ui_language), POS_SCROLL)
        diagnostics_pages = (
            PageName.HOSTS,
            PageName.BLOCKCHECK,
        )
        for page_name in diagnostics_pages:
            _add(page_name)
        self._nav_headers.append((diagnostics_header, diagnostics_pages, diagnostics_header_key))

        # ── Оформление / Донат / Логи ─────────────────────────────────────────
        appearance_header_key = "nav.header.appearance"
        appearance_header = nav.addItemHeader(tr_catalog(appearance_header_key, language=self._ui_language), POS_SCROLL)
        appearance_pages = (
            PageName.APPEARANCE,
            PageName.PREMIUM,
            PageName.LOGS,
            PageName.ABOUT,
        )
        for page_name in appearance_pages:
            _add(page_name)
        self._nav_headers.append((appearance_header, appearance_pages, appearance_header_key))

        # Pages NOT in navigation — reachable only via show_page() / switchTo()
        for hidden in (
            PageName.ZAPRET2_DIRECT,
            PageName.ZAPRET2_ORCHESTRA,
            PageName.ZAPRET2_USER_PRESETS,
            PageName.ZAPRET2_ORCHESTRA_USER_PRESETS,
            PageName.ZAPRET2_STRATEGY_DETAIL,
            PageName.ZAPRET2_PRESET_DETAIL,
            PageName.ZAPRET2_ORCHESTRA_STRATEGY_DETAIL,
            PageName.BLOBS,
            PageName.ZAPRET1_DIRECT,
            PageName.ZAPRET1_USER_PRESETS,
            PageName.ZAPRET1_STRATEGY_DETAIL,
            PageName.ZAPRET1_PRESET_DETAIL,
        ):
            page = self.pages.get(hidden)
            if page is not None:
                if not page.objectName():
                    page.setObjectName(page.__class__.__name__)
                self.stackedWidget.addWidget(page)
                self._pump_startup_ui()

        self.navigationInterface.setMinimumExpandWidth(700)

        # Apply initial visibility immediately — flat items need no parent refresh.
        self._sync_nav_visibility()

    def _attach_sidebar_search_to_titlebar(self) -> None:
        widget = self._sidebar_search_nav_widget
        if widget is None:
            return

        title_bar = getattr(self, "titleBar", None)
        if title_bar is None:
            return

        layout = getattr(title_bar, "hBoxLayout", None)
        if layout is None:
            return

        if widget.parent() is not title_bar:
            widget.setParent(title_bar)

        if layout.indexOf(widget) < 0:
            insert_index = max(0, layout.count() - 1)
            layout.insertWidget(insert_index, widget, 0, Qt.AlignmentFlag.AlignVCenter)

        self._sidebar_search_titlebar_attached = True

    def _update_titlebar_search_width(self) -> None:
        if not bool(getattr(self, "_sidebar_search_titlebar_attached", False)):
            return

        widget = self._sidebar_search_nav_widget
        if widget is None:
            return

        title_bar = getattr(self, "titleBar", None)
        if title_bar is None:
            return

        title_bar_width = int(title_bar.width())
        if title_bar_width <= 0:
            title_bar_width = max(0, int(self.width()) - 46)

        available_width = max(220, title_bar_width - 340)
        target_width = int(title_bar_width * 0.42)
        target_width = max(280, min(560, target_width, available_width))
        widget.setFixedWidth(target_width)

    def _sync_nav_visibility(self, method: str | None = None) -> None:
        """Show/hide mode-specific navigation items.

        With a flat (non-tree) navigation layout this reduces to plain
        setVisible() calls — no parent fixed-size management needed.
        """
        if not getattr(self, '_nav_items', None):
            return

        if method is None:
            try:
                from strategy_menu import get_strategy_launch_method
                method = (get_strategy_launch_method() or "").strip().lower()
            except Exception:
                method = "direct_zapret2"
        if not method:
            method = "direct_zapret2"

        from ui.nav_mode_config import get_nav_visibility
        targets = get_nav_visibility(method)

        from log import log as _log
        _log(f"[NAV] _sync_nav_visibility method={method!r}, _nav_items keys={[p.name for p in self._nav_items]}", "DEBUG")
        mode_visibility: dict[PageName, bool] = {
            page_name: True for page_name in self._nav_items
        }
        for page_name, should_show in targets.items():
            item = self._nav_items.get(page_name)
            if item is None and bool(should_show):
                self._add_nav_item(page_name, NavigationItemPosition.SCROLL)
                item = self._nav_items.get(page_name)

            if item is not None:
                mode_visibility[page_name] = bool(should_show)
                _log(f"[NAV]   {page_name.name} → modeVisible({should_show})", "DEBUG")
            elif bool(should_show):
                _log(f"[NAV]   {page_name.name} → NOT in _nav_items!", "WARNING")

        self._nav_mode_visibility = mode_visibility
        self._apply_nav_visibility_filter()
        self._update_sidebar_search_suggestions()

    def _on_sidebar_search_changed(self, text: str) -> None:
        self._nav_search_query = (text or "").strip()
        # Try routing before rebuilding suggestions: when a completer item is
        # picked, the line edit receives full display text ("title - location"),
        # which may not match search entries directly and would otherwise clear
        # the model before we resolve the target.
        if self._route_sidebar_search_by_text(self._nav_search_query, prefer_first=False):
            return
        self._apply_nav_visibility_filter()
        self._update_sidebar_search_suggestions()

    def _apply_nav_visibility_filter(self) -> None:
        if not getattr(self, "_nav_items", None):
            return

        search_query = (getattr(self, "_nav_search_query", "") or "").casefold()
        mode_visibility = getattr(self, "_nav_mode_visibility", {}) or {}
        visible_by_page: dict[PageName, bool] = {}

        for page_name, item in self._nav_items.items():
            mode_visible = bool(mode_visibility.get(page_name, True))
            label = self._get_nav_label(page_name)
            matches_query = not search_query or (search_query in label.casefold())
            final_visible = mode_visible and matches_query
            item.setVisible(final_visible)
            visible_by_page[page_name] = final_visible

        for header, grouped_pages, _header_key in getattr(self, "_nav_headers", []):
            if header is None:
                continue
            header.setVisible(any(visible_by_page.get(page_name, False) for page_name in grouped_pages))

    def _resolve_ui_language(self) -> str:
        try:
            from config.reg import get_ui_language

            return normalize_language(get_ui_language())
        except Exception:
            return normalize_language(None)

    def _get_nav_label(self, page_name: PageName) -> str:
        fallback = _NAV_LABELS.get(page_name, page_name.name)
        return get_nav_page_label(page_name, language=self._ui_language, fallback=fallback)

    def _get_sidebar_search_pages(self) -> set[PageName]:
        """Pages allowed for sidebar search suggestions and routing."""
        return get_sidebar_search_pages_for_method(self._get_launch_method(), set(_PAGE_CLASS_SPECS.keys()))

    def _setup_sidebar_search_completer(self) -> None:
        if self._sidebar_search_nav_widget is None:
            return

        self._sidebar_search_model = QStandardItemModel(self)
        completer = QCompleter(self._sidebar_search_model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(10)
        completer.activated[QModelIndex].connect(self._on_sidebar_search_result_activated)
        completer.activated[str].connect(self._on_sidebar_search_result_text_activated)
        # Mouse clicks in completer popup are not guaranteed to emit
        # `QCompleter.activated[QModelIndex]` on all Qt/Windows stacks.
        # Wire popup signals directly as a robust fallback.
        try:
            popup = completer.popup()
            if popup is not None:
                popup.clicked.connect(self._on_sidebar_search_result_activated)
                popup.activated.connect(self._on_sidebar_search_result_activated)
        except Exception:
            pass

        self._sidebar_search_completer = completer
        self._sidebar_search_nav_widget.set_completer(completer)

    def _update_sidebar_search_suggestions(self) -> None:
        model = self._sidebar_search_model
        completer = self._sidebar_search_completer
        if model is None or completer is None:
            return

        model.clear()
        query = (getattr(self, "_nav_search_query", "") or "").strip()
        if not query:
            try:
                completer.popup().hide()
            except Exception:
                pass
            return

        visible_pages = self._get_sidebar_search_pages()

        matches = find_search_entries(
            query,
            language=self._ui_language,
            visible_pages=visible_pages,
            max_results=10,
        )
        if not matches:
            try:
                completer.popup().hide()
            except Exception:
                pass
            return

        page_role = int(Qt.ItemDataRole.UserRole)
        tab_role = page_role + 1

        for match in matches:
            title, location = format_search_result(match.entry, language=self._ui_language)
            item = QStandardItem(f"{title} - {location}")
            item.setData(match.entry.page_name.name, page_role)
            item.setData(match.entry.tab_key or "", tab_role)
            model.appendRow(item)

        if self._sidebar_search_nav_widget is not None and self._sidebar_search_nav_widget.isVisible():
            self._sidebar_search_nav_widget.show_completions()

    def _on_sidebar_search_result_activated(self, index: QModelIndex) -> None:
        if not index.isValid():
            return

        page_role = int(Qt.ItemDataRole.UserRole)
        tab_role = page_role + 1

        raw_page_name = index.data(page_role)
        if not isinstance(raw_page_name, str) or not raw_page_name:
            display_text = index.data(int(Qt.ItemDataRole.DisplayRole))
            if isinstance(display_text, str):
                self._route_sidebar_search_by_text(display_text, prefer_first=False)
            return

        try:
            page_name = PageName[raw_page_name]
        except Exception:
            return

        tab_key = index.data(tab_role)
        if not isinstance(tab_key, str):
            tab_key = ""

        self._route_search_result(page_name, tab_key)

        if self._sidebar_search_nav_widget is not None:
            self._sidebar_search_nav_widget.clear()

    def _on_sidebar_search_result_text_activated(self, text: str) -> None:
        self._route_sidebar_search_by_text(text, prefer_first=False)

    def _route_sidebar_search_by_text(self, text: str, prefer_first: bool = False) -> bool:
        text = (text or "").strip()
        if not text:
            return False

        model = self._sidebar_search_model
        if model is None:
            return False

        page_role = int(Qt.ItemDataRole.UserRole)
        tab_role = page_role + 1

        target_item = None
        text_cf = text.casefold()
        for row in range(model.rowCount()):
            item = model.item(row, 0)
            if item is None:
                continue
            if (item.text() or "").strip().casefold() == text_cf:
                target_item = item
                break

        if target_item is None and prefer_first and model.rowCount() > 0:
            target_item = model.item(0, 0)

        if target_item is None:
            # Fallback path when completer injected full text but model was
            # already rebuilt/cleared for that text.
            query = text
            if " - " in query:
                query = (query.split(" - ", 1)[0] or "").strip() or query

            visible_pages = self._get_sidebar_search_pages()

            matches = find_search_entries(
                query,
                language=self._ui_language,
                visible_pages=visible_pages,
                max_results=10,
            )
            selected_match = None
            for match in matches:
                title, location = format_search_result(match.entry, language=self._ui_language)
                display = f"{title} - {location}".strip().casefold()
                title_cf = (title or "").strip().casefold()
                if display == text_cf or title_cf == text_cf:
                    selected_match = match
                    break
            if selected_match is None and prefer_first and matches:
                selected_match = matches[0]

            if selected_match is None:
                return False

            self._route_search_result(selected_match.entry.page_name, selected_match.entry.tab_key or "")
            if self._sidebar_search_nav_widget is not None:
                self._sidebar_search_nav_widget.clear()
            return True

        raw_page_name = target_item.data(page_role)
        if not isinstance(raw_page_name, str) or not raw_page_name:
            return False

        tab_key = target_item.data(tab_role)
        if not isinstance(tab_key, str):
            tab_key = ""

        try:
            page_name = PageName[raw_page_name]
        except Exception:
            return False

        self._route_search_result(page_name, tab_key)
        if self._sidebar_search_nav_widget is not None:
            self._sidebar_search_nav_widget.clear()
        return True

    def _route_search_result(self, page_name: PageName, tab_key: str = "") -> None:
        if not self.show_page(page_name):
            return

        if not tab_key:
            return

        page = self.get_page(page_name)
        if page is not None and hasattr(page, "switch_to_tab"):
            try:
                page.switch_to_tab(tab_key)
            except Exception:
                pass

    def _refresh_navigation_texts(self) -> None:
        if self._sidebar_search_nav_widget is not None:
            self._sidebar_search_nav_widget.set_placeholder_text(
                tr_catalog("sidebar.search.placeholder", language=self._ui_language)
            )

        for page_name, item in getattr(self, "_nav_items", {}).items():
            try:
                item.setText(self._get_nav_label(page_name))
            except Exception:
                pass

        for header, _grouped_pages, header_key in getattr(self, "_nav_headers", []):
            if header is None:
                continue
            try:
                header.setText(tr_catalog(header_key, language=self._ui_language))
            except Exception:
                pass

        self._apply_nav_visibility_filter()
        self._update_sidebar_search_suggestions()

    def _on_ui_language_changed(self, language: str) -> None:
        self._ui_language = normalize_language(language)
        self._refresh_navigation_texts()
        self._refresh_pages_language()

    def _apply_ui_language_to_page(self, page: QWidget | None) -> None:
        if page is None:
            return

        for method_name in ("set_ui_language", "retranslate_ui", "apply_ui_language"):
            method = getattr(page, method_name, None)
            if callable(method):
                try:
                    method(self._ui_language)
                except TypeError:
                    try:
                        method()
                    except Exception:
                        pass
                except Exception:
                    pass
                return

    def _refresh_pages_language(self) -> None:
        for page in getattr(self, "pages", {}).values():
            self._apply_ui_language_to_page(page)

    # ------------------------------------------------------------------
    # Page creation (lazy + eager) — UNCHANGED logic
    # ------------------------------------------------------------------

    def _get_eager_page_names(self) -> tuple[PageName, ...]:
        method = self._get_launch_method()

        names: list[PageName] = [PageName.HOME, PageName.CONTROL]
        entry_page = _EAGER_MODE_ENTRY_PAGE.get(method)
        if entry_page is not None and entry_page not in names:
            names.append(entry_page)

        for page_name in _EAGER_PAGE_NAMES_BASE:
            if page_name not in names:
                names.append(page_name)

        return tuple(names)

    def _create_pages(self):
        """Create page registry and initialize critical pages eagerly."""
        import time as _time
        from log import log

        _t_pages_total = _time.perf_counter()

        for page_name in self._get_eager_page_names():
            self._ensure_page(page_name)
            self._pump_startup_ui()

        log(
            f"⏱ Startup: _create_pages core {(_time.perf_counter() - _t_pages_total) * 1000:.0f}ms",
            "DEBUG",
        )
        self._pump_startup_ui(force=True)

    def _resolve_page_name(self, name: PageName) -> PageName:
        return self._page_aliases.get(name, name)

    def _connect_signal_once(self, key: str, signal_obj, slot_obj) -> None:
        if key in self._lazy_signal_connections:
            return
        try:
            signal_obj.connect(slot_obj)
            self._lazy_signal_connections.add(key)
        except Exception:
            pass

    def _connect_lazy_page_signals(self, page_name: PageName, page: QWidget) -> None:
        if page_name in (
            PageName.ZAPRET1_DIRECT,
            PageName.ZAPRET2_DIRECT,
            PageName.ZAPRET2_ORCHESTRA,
        ):
            if hasattr(page, "strategy_selected"):
                self._connect_signal_once(
                    f"strategy_selected.{page_name.name}",
                    page.strategy_selected,
                    self._on_strategy_selected_from_page,
                )

        if page_name == PageName.ZAPRET2_DIRECT and hasattr(page, "open_category_detail"):
            self._connect_signal_once(
                "z2_direct.open_category_detail",
                page.open_category_detail,
                self._on_open_category_detail,
            )

        if page_name in (PageName.ZAPRET2_DIRECT, PageName.ZAPRET2_USER_PRESETS, PageName.BLOBS) and hasattr(page, "back_clicked"):
            self._connect_signal_once(
                f"back_to_control.{page_name.name}",
                page.back_clicked,
                self._show_active_zapret2_control_page,
            )

        if page_name == PageName.ZAPRET2_ORCHESTRA_USER_PRESETS and hasattr(page, "back_clicked"):
            self._connect_signal_once(
                "back_to_orchestra_control.user_presets",
                page.back_clicked,
                lambda: self.show_page(PageName.ZAPRET2_ORCHESTRA_CONTROL),
            )

        if page_name in (PageName.ZAPRET1_DIRECT, PageName.ZAPRET1_USER_PRESETS) and hasattr(page, "back_clicked"):
            self._connect_signal_once(
                f"back_to_z1_control.{page_name.name}",
                page.back_clicked,
                lambda: self.show_page(PageName.ZAPRET1_DIRECT_CONTROL),
            )

        if page_name in (PageName.ZAPRET2_USER_PRESETS, PageName.ZAPRET2_ORCHESTRA_USER_PRESETS) and hasattr(page, "preset_open_requested"):
            # User presets pages emit file_name here.
            self._connect_signal_once(
                f"{page_name.name}.preset_open_requested",
                page.preset_open_requested,
                self._open_zapret2_preset_detail,
            )
        if page_name in (PageName.ZAPRET2_USER_PRESETS, PageName.ZAPRET2_ORCHESTRA_USER_PRESETS) and hasattr(page, "folders_open_requested"):
            self._connect_signal_once(
                f"{page_name.name}.folders_open_requested",
                page.folders_open_requested,
                self._open_zapret2_preset_folders,
            )

        if page_name == PageName.ZAPRET1_USER_PRESETS and hasattr(page, "preset_open_requested"):
            # User presets page emits file_name here.
            self._connect_signal_once(
                "z1_user_presets.preset_open_requested",
                page.preset_open_requested,
                self._open_zapret1_preset_detail,
            )
        if page_name == PageName.ZAPRET1_USER_PRESETS and hasattr(page, "folders_open_requested"):
            self._connect_signal_once(
                "z1_user_presets.folders_open_requested",
                page.folders_open_requested,
                self._open_zapret1_preset_folders,
            )

        if page_name == PageName.ZAPRET2_PRESET_DETAIL and hasattr(page, "back_clicked"):
            self._connect_signal_once(
                "z2_preset_detail.back_clicked",
                page.back_clicked,
                self._show_active_zapret2_user_presets_page,
            )

        if page_name == PageName.ZAPRET1_PRESET_DETAIL and hasattr(page, "back_clicked"):
            self._connect_signal_once(
                "z1_preset_detail.back_clicked",
                page.back_clicked,
                lambda: self.show_page(PageName.ZAPRET1_USER_PRESETS),
            )
        if page_name == PageName.ZAPRET2_PRESET_FOLDERS and hasattr(page, "back_clicked"):
            self._connect_signal_once(
                "z2_preset_folders.back_clicked",
                page.back_clicked,
                self._show_active_zapret2_user_presets_page,
            )
        if page_name == PageName.ZAPRET1_PRESET_FOLDERS and hasattr(page, "back_clicked"):
            self._connect_signal_once(
                "z1_preset_folders.back_clicked",
                page.back_clicked,
                self._show_zapret1_user_presets_page,
            )
        if page_name == PageName.ZAPRET2_PRESET_FOLDERS and hasattr(page, "folders_changed"):
            self._connect_signal_once(
                "z2_preset_folders.folders_changed",
                page.folders_changed,
                self._refresh_active_zapret2_user_presets_page,
            )
        if page_name == PageName.ZAPRET1_PRESET_FOLDERS and hasattr(page, "folders_changed"):
            self._connect_signal_once(
                "z1_preset_folders.folders_changed",
                page.folders_changed,
                self._refresh_zapret1_user_presets_page,
            )

        if page_name in (PageName.ZAPRET2_DIRECT_CONTROL, PageName.ZAPRET2_ORCHESTRA_CONTROL):
            presets_target = (
                PageName.ZAPRET2_ORCHESTRA_USER_PRESETS
                if page_name == PageName.ZAPRET2_ORCHESTRA_CONTROL
                else PageName.ZAPRET2_USER_PRESETS
            )
            direct_launch_target = (
                PageName.ZAPRET2_ORCHESTRA
                if page_name == PageName.ZAPRET2_ORCHESTRA_CONTROL
                else PageName.ZAPRET2_DIRECT
            )

            for button_attr, handler in (
                ("start_btn", self._proxy_start_click),
                ("stop_winws_btn", self._proxy_stop_click),
                ("stop_and_exit_btn", self._proxy_stop_and_exit),
                ("test_btn", self._proxy_test_click),
                ("folder_btn", self._proxy_folder_click),
            ):
                button = getattr(page, button_attr, None)
                signal = getattr(button, "clicked", None)
                if signal is not None:
                    self._connect_signal_once(
                        f"{page_name.name}.{button_attr}.clicked",
                        signal,
                        handler,
                    )

            if hasattr(page, "navigate_to_presets"):
                self._connect_signal_once(
                    f"{page_name.name}.navigate_to_presets",
                    page.navigate_to_presets,
                    lambda target=presets_target: self.show_page(target),
                )

            if hasattr(page, "navigate_to_direct_launch"):
                self._connect_signal_once(
                    f"{page_name.name}.navigate_to_direct_launch",
                    page.navigate_to_direct_launch,
                    lambda target=direct_launch_target: self.show_page(target),
                )

            if hasattr(page, "navigate_to_blobs"):
                self._connect_signal_once(
                    f"{page_name.name}.navigate_to_blobs",
                    page.navigate_to_blobs,
                    lambda: self.show_page(PageName.BLOBS),
                )

            if page_name == PageName.ZAPRET2_DIRECT_CONTROL and hasattr(page, "direct_mode_changed"):
                self._connect_signal_once(
                    f"{page_name.name}.direct_mode_changed",
                    page.direct_mode_changed,
                    self._on_direct_mode_changed,
                )

        if page_name == PageName.ZAPRET1_DIRECT and hasattr(page, "category_clicked"):
            self._connect_signal_once(
                "z1_direct.category_clicked",
                page.category_clicked,
                self._open_zapret1_category_detail,
            )

        if page_name == PageName.ZAPRET1_STRATEGY_DETAIL:
            if hasattr(page, "back_clicked"):
                self._connect_signal_once(
                    "z1_strategy_detail.back_clicked",
                    page.back_clicked,
                    lambda: self.show_page(PageName.ZAPRET1_DIRECT),
                )
            if hasattr(page, "navigate_to_control"):
                self._connect_signal_once(
                    "z1_strategy_detail.navigate_to_control",
                    page.navigate_to_control,
                    lambda: self.show_page(PageName.ZAPRET1_DIRECT_CONTROL),
                )
            if hasattr(page, "strategy_selected"):
                self._connect_signal_once(
                    "z1_strategy_detail.strategy_selected",
                    page.strategy_selected,
                    self._on_z1_strategy_detail_selected,
                )

        if page_name == PageName.ZAPRET1_DIRECT_CONTROL:
            for button_attr, handler in (
                ("start_btn", self._proxy_start_click),
                ("stop_winws_btn", self._proxy_stop_click),
                ("stop_and_exit_btn", self._proxy_stop_and_exit),
                ("test_btn", self._proxy_test_click),
                ("folder_btn", self._proxy_folder_click),
            ):
                button = getattr(page, button_attr, None)
                signal = getattr(button, "clicked", None)
                if signal is not None:
                    self._connect_signal_once(
                        f"z1_control.{button_attr}.clicked",
                        signal,
                        handler,
                    )

            if hasattr(page, "navigate_to_strategies"):
                self._connect_signal_once(
                    "z1_control.navigate_to_strategies",
                    page.navigate_to_strategies,
                    lambda: self.show_page(PageName.ZAPRET1_DIRECT),
                )
            if hasattr(page, "navigate_to_presets"):
                self._connect_signal_once(
                    "z1_control.navigate_to_presets",
                    page.navigate_to_presets,
                    lambda: self.show_page(PageName.ZAPRET1_USER_PRESETS),
                )

        if page_name == PageName.ZAPRET2_STRATEGY_DETAIL:
            if hasattr(page, "back_clicked"):
                self._connect_signal_once(
                    "strategy_detail.back_clicked",
                    page.back_clicked,
                    self._on_strategy_detail_back,
                )
            if hasattr(page, "navigate_to_root"):
                self._connect_signal_once(
                    "strategy_detail.navigate_to_root",
                    page.navigate_to_root,
                    lambda: self.show_page(PageName.ZAPRET2_DIRECT_CONTROL),
                )
            if hasattr(page, "strategy_selected"):
                self._connect_signal_once(
                    "strategy_detail.strategy_selected",
                    page.strategy_selected,
                    self._on_strategy_detail_selected,
                )
            if hasattr(page, "filter_mode_changed"):
                self._connect_signal_once(
                    "strategy_detail.filter_mode_changed",
                    page.filter_mode_changed,
                    self._on_strategy_detail_filter_mode_changed,
                )

        if page_name == PageName.ZAPRET2_ORCHESTRA_STRATEGY_DETAIL:
            if hasattr(page, "back_clicked"):
                self._connect_signal_once(
                    "orchestra_strategy_detail.back_clicked",
                    page.back_clicked,
                    lambda: self.show_page(PageName.ZAPRET2_ORCHESTRA),
                )
            if hasattr(page, "navigate_to_root"):
                self._connect_signal_once(
                    "orchestra_strategy_detail.navigate_to_root",
                    page.navigate_to_root,
                    lambda: self.show_page(PageName.ZAPRET2_ORCHESTRA_CONTROL),
                )

        if page_name == PageName.ORCHESTRA and hasattr(page, "clear_learned_requested"):
            self._connect_signal_once(
                "orchestra.clear_learned_requested",
                page.clear_learned_requested,
                self._on_clear_learned_requested,
            )


    def _ensure_page_in_stacked_widget(self, page: QWidget | None) -> None:
        stack = getattr(self, "stackedWidget", None)
        if page is None or stack is None:
            return
        try:
            if stack.indexOf(page) < 0:
                stack.addWidget(page)
        except Exception:
            pass

    def _ensure_page(self, name: PageName) -> QWidget | None:
        resolved_name = self._resolve_page_name(name)
        page = self.pages.get(resolved_name)
        if page is not None:
            self._apply_ui_language_to_page(page)
            if bool(getattr(self, "_page_signal_bootstrap_complete", False)):
                self._ensure_page_in_stacked_widget(page)
            return page

        spec = _PAGE_CLASS_SPECS.get(resolved_name)
        if spec is None:
            return None

        attr_name, module_name, class_name = spec
        import time as _time
        _t_page = _time.perf_counter()
        try:
            module = import_module(module_name)
            page_cls = getattr(module, class_name)
            page = page_cls(self)
        except Exception as e:
            from log import log

            # Robust fallback for orchestra Z2 routes in mixed/old builds where
            # dedicated wrappers may be absent from package imports.
            fallback_specs = {
                PageName.ZAPRET2_ORCHESTRA_CONTROL: (
                    "ui.pages.zapret2.direct_control_page",
                    "Zapret2DirectControlPage",
                ),
                PageName.ZAPRET2_ORCHESTRA_USER_PRESETS: (
                    "ui.pages.zapret2.user_presets_page",
                    "Zapret2UserPresetsPage",
                ),
                PageName.ZAPRET2_ORCHESTRA_STRATEGY_DETAIL: (
                    "ui.pages.zapret2.strategy_detail_page",
                    "StrategyDetailPage",
                ),
            }
            fallback = fallback_specs.get(resolved_name)
            if not fallback:
                log(f"Ошибка lazy-инициализации страницы {resolved_name}: {e}", "ERROR")
                return None

            log(
                f"Lazy-инициализация страницы {resolved_name} не удалась: {e}. Пробуем fallback...",
                "WARNING",
            )
            try:
                fb_module = import_module(fallback[0])
                fb_cls = getattr(fb_module, fallback[1])
                page = fb_cls(self)
                log(f"Использован fallback для страницы {resolved_name}: {fallback[1]}", "WARNING")
            except Exception as fallback_error:
                log(
                    f"Fallback lazy-инициализации страницы {resolved_name} тоже не удался: {fallback_error}",
                    "ERROR",
                )
                return None

        # Ensure unique objectName for FluentWindow route keys.
        # Two nav pages can share the same class (e.g. user presets for direct/orchestra),
        # so objectName must be disambiguated explicitly.
        if resolved_name == PageName.ZAPRET2_USER_PRESETS:
            page.setObjectName("Zapret2UserPresetsPage_Direct")
        elif resolved_name == PageName.ZAPRET2_ORCHESTRA_USER_PRESETS:
            page.setObjectName("Zapret2UserPresetsPage_Orchestra")
        elif resolved_name == PageName.ZAPRET2_ORCHESTRA_CONTROL:
            # Ensure unique routeKey even when fallback to Zapret2DirectControlPage is used.
            # Fallback shares class/objectName with ZAPRET2_DIRECT_CONTROL → duplicate routeKey
            # → addSubInterface returns None → page never in _nav_items.
            if not page.objectName():
                cls_name = page.__class__.__name__
                if cls_name == "Zapret2DirectControlPage":
                    page.setObjectName("Zapret2DirectControlPage_Orchestra")
                else:
                    page.setObjectName(cls_name)
        elif not page.objectName():
            page.setObjectName(page.__class__.__name__)

        self.pages[resolved_name] = page
        setattr(self, attr_name, page)
        self._apply_ui_language_to_page(page)

        # Legacy alias
        if resolved_name == PageName.HOSTLIST:
            self.ipset_page = page

        if bool(getattr(self, "_page_signal_bootstrap_complete", False)):
            self._connect_lazy_page_signals(resolved_name, page)
            # For late-created pages, add to stacked widget
            self._ensure_page_in_stacked_widget(page)

        elapsed_ms = int((_time.perf_counter() - _t_page) * 1000)
        self._record_startup_page_init_metric(resolved_name, elapsed_ms)

        return page

    def get_page(self, name: PageName) -> QWidget:
        return self._ensure_page(name)

    def show_page(self, name: PageName) -> bool:
        """Switch to the given page. Works with FluentWindow's switchTo()."""
        page = self._ensure_page(name)
        if page is None:
            return False
        self._ensure_page_in_stacked_widget(page)
        try:
            self.switchTo(page)
        except Exception:
            # Fallback for pages not registered in nav
            self._ensure_page_in_stacked_widget(page)
            if hasattr(self, 'stackedWidget'):
                self.stackedWidget.setCurrentWidget(page)
        return True

    def _show_active_zapret2_user_presets_page(self) -> None:
        show_active_zapret2_user_presets_page(self)

    def _show_zapret1_user_presets_page(self) -> None:
        show_zapret1_user_presets_page(self)

    def _refresh_page_if_possible(self, page_name: PageName) -> None:
        refresh_page_if_possible(self, page_name)

    def _refresh_active_zapret2_user_presets_page(self) -> None:
        refresh_active_zapret2_user_presets_page(self)

    def _refresh_zapret1_user_presets_page(self) -> None:
        refresh_zapret1_user_presets_page(self)

    def _open_zapret2_preset_detail(self, preset_name: str) -> None:
        open_zapret2_preset_detail(self, preset_name)

    def _open_zapret1_preset_detail(self, preset_name: str) -> None:
        open_zapret1_preset_detail(self, preset_name)

    def _open_zapret2_preset_folders(self) -> None:
        open_zapret2_preset_folders(self)

    def _open_zapret1_preset_folders(self) -> None:
        open_zapret1_preset_folders(self)


    # ------------------------------------------------------------------
    # All handler methods — PRESERVED from original
    # ------------------------------------------------------------------

    def _on_direct_mode_changed(self, mode: str):
        """Force rebuild of Прямой запуск page on next show."""
        page = getattr(self, "zapret2_strategies_page", None)
        if page and hasattr(page, "_strategy_set_snapshot"):
            page._strategy_set_snapshot = None

    def _on_background_refresh_needed(self):
        """Re-applies window background (called when tinted_bg or accent changes)."""
        try:
            from ui.theme import apply_window_background
            apply_window_background(self.window())
        except Exception:
            pass

    def _on_background_preset_changed(self, preset: str):
        """Apply new background preset to the window."""
        try:
            from ui.theme import apply_window_background
            apply_window_background(self.window(), preset=preset)
        except Exception:
            pass

    def _on_opacity_changed(self, value: int):
        """Apply window opacity from appearance_page slider."""
        win = self.window()
        if hasattr(win, 'set_window_opacity'):
            win.set_window_opacity(value)

    def _on_mica_changed(self, enabled: bool):
        """Save Mica setting and re-apply window background."""
        try:
            from config.reg import set_mica_enabled
            set_mica_enabled(enabled)
        except Exception:
            pass
        try:
            from ui.theme import apply_window_background
            apply_window_background(self.window())
        except Exception:
            pass

    def _on_animations_changed(self, enabled: bool):
        """Enable/disable all QPropertyAnimation-based animations (qfluentwidgets + Qt native)."""
        try:
            from PyQt6.QtCore import QPropertyAnimation, QAbstractAnimation

            if enabled:
                # Restore original start()
                if hasattr(QPropertyAnimation, '_zapret_original_start'):
                    QPropertyAnimation.start = QPropertyAnimation._zapret_original_start
                    del QPropertyAnimation._zapret_original_start
            else:
                # Monkey-patch start() to set duration=0 before every animation run
                if not hasattr(QPropertyAnimation, '_zapret_original_start'):
                    _orig = QPropertyAnimation.start
                    QPropertyAnimation._zapret_original_start = _orig

                    def _instant_start(
                        self,
                        policy=QAbstractAnimation.DeletionPolicy.KeepWhenStopped,
                    ):
                        self.setDuration(0)
                        QPropertyAnimation._zapret_original_start(self, policy)

                    QPropertyAnimation.start = _instant_start
        except Exception:
            pass

    def _on_smooth_scroll_changed(self, enabled: bool):
        """Toggle smooth scrolling on all existing pages and nested widgets."""
        try:
            from PyQt6.QtCore import Qt
            from PyQt6.QtWidgets import QWidget
            from qfluentwidgets.common.smooth_scroll import SmoothMode

            mode = SmoothMode.COSINE if enabled else SmoothMode.NO_SMOOTH

            def _apply_delegate_mode(delegate) -> None:
                if delegate is None:
                    return

                try:
                    if hasattr(delegate, "useAni"):
                        if not hasattr(delegate, "_zapret_base_use_ani"):
                            delegate._zapret_base_use_ani = bool(delegate.useAni)
                        delegate.useAni = bool(delegate._zapret_base_use_ani) if enabled else False
                except Exception:
                    pass

                for smooth_attr in ("verticalSmoothScroll", "horizonSmoothScroll"):
                    smooth = getattr(delegate, smooth_attr, None)
                    setter = getattr(smooth, "setSmoothMode", None)
                    if callable(setter):
                        try:
                            setter(mode)
                        except Exception:
                            pass

                setter = getattr(delegate, "setSmoothMode", None)
                if callable(setter):
                    try:
                        setter(mode)
                    except TypeError:
                        try:
                            setter(mode, Qt.Orientation.Vertical)
                        except Exception:
                            pass
                    except Exception:
                        pass

            def _apply_smooth_mode(target) -> None:
                setter = getattr(target, "setSmoothMode", None)
                if callable(setter):
                    try:
                        setter(mode, Qt.Orientation.Vertical)
                    except TypeError:
                        try:
                            setter(mode)
                        except Exception:
                            pass
                    except Exception:
                        pass

                _apply_delegate_mode(getattr(target, "scrollDelegate", None))
                _apply_delegate_mode(getattr(target, "scrollDelagate", None))
                _apply_delegate_mode(getattr(target, "delegate", None))
                _apply_delegate_mode(getattr(target, "_presets_scroll_delegate", None))
                _apply_delegate_mode(getattr(target, "_smooth_scroll_delegate", None))

                custom_setter = getattr(target, "set_smooth_scroll_enabled", None)
                if callable(custom_setter):
                    try:
                        custom_setter(enabled)
                    except Exception:
                        pass

            for page in list(self.pages.values()):
                _apply_smooth_mode(page)
                for child in page.findChildren(QWidget):
                    _apply_smooth_mode(child)
        except Exception:
            pass

    def _refresh_pages_after_preset_switch(self):
        refresh_main_window_pages_after_preset_switch(self)

    def _on_clear_learned_requested(self):
        from log import log
        log("Запрошена очистка данных обучения", "INFO")
        if hasattr(self, 'orchestra_runner') and self.orchestra_runner:
            self.orchestra_runner.clear_learned_data()
            log("Данные обучения очищены", "INFO")

    def _on_launch_method_changed(self, method: str):
        from log import log
        from config import WINWS_EXE, WINWS2_EXE

        log(f"Метод запуска изменён на: {method}", "INFO")

        if hasattr(self, 'dpi_starter') and self.dpi_starter.check_process_running_wmi(silent=True):
            log("Останавливаем все процессы winws*.exe перед переключением режима...", "INFO")

            try:
                from utils.process_killer import kill_winws_all
                killed = kill_winws_all()
                if killed:
                    log("Все процессы winws*.exe остановлены через Win API", "INFO")
                if hasattr(self, 'dpi_starter'):
                    self.dpi_starter.cleanup_windivert_service()
                if hasattr(self, 'ui_manager'):
                    self.ui_manager.update_ui_state(running=False)
                if hasattr(self, 'process_monitor_manager'):
                    self.process_monitor_manager.on_process_status_changed(False)
                import time
                time.sleep(0.2)
            except Exception as e:
                log(f"Ошибка остановки через Win API: {e}", "WARNING")

        self._complete_method_switch(method)

    def _complete_method_switch(self, method: str):
        from log import log
        from config import get_winws_exe_for_method

        try:
            from utils.service_manager import cleanup_windivert_services
            cleanup_windivert_services()
        except Exception:
            pass

        if hasattr(self, 'dpi_starter'):
            self.dpi_starter.winws_exe = get_winws_exe_for_method(method)

        try:
            from launcher_common import invalidate_strategy_runner
            invalidate_strategy_runner()
        except Exception as e:
            log(f"Ошибка инвалидации StrategyRunner: {e}", "WARNING")

        can_autostart = True
        if method == "direct_zapret2":
            from preset_zapret2 import ensure_default_preset_exists
            if not ensure_default_preset_exists():
                log("direct_zapret2: выбранный source-пресет не подготовлен", "ERROR")
                try:
                    self.set_status("Ошибка: отсутствует Default.txt (built-in пресет)")
                except Exception:
                    pass
                can_autostart = False

        elif method == "direct_zapret2_orchestra":
            from preset_orchestra_zapret2 import ensure_default_preset_exists
            if not ensure_default_preset_exists():
                log("direct_zapret2_orchestra: preset-zapret2-orchestra.txt не создан", "ERROR")
                try:
                    self.set_status("Ошибка: отсутствует orchestra Default.txt")
                except Exception:
                    pass
                can_autostart = False

        elif method == "direct_zapret1":
            try:
                from preset_zapret1 import ensure_default_preset_exists_v1
                if not ensure_default_preset_exists_v1():
                    log("direct_zapret1: выбранный source-пресет не подготовлен", "ERROR")
                    can_autostart = False
            except Exception as e:
                log(f"direct_zapret1: ошибка инициализации пресета: {e}", "WARNING")

        try:
            self._preset_runtime_coordinator.setup_active_preset_file_watcher()
        except Exception:
            pass

        # Reload strategy pages
        for attr in ('zapret2_strategies_page', 'zapret2_orchestra_strategies_page',
                     'orchestra_zapret2_control_page', 'zapret1_strategies_page'):
            page = getattr(self, attr, None)
            if page and hasattr(page, 'reload_for_mode_change'):
                page.reload_for_mode_change()

        log(f"Переключение на режим '{method}' завершено", "INFO")

        try:
            self._sync_nav_visibility(method)
        except Exception:
            pass

        from PyQt6.QtCore import QTimer
        if can_autostart:
            QTimer.singleShot(500, lambda: self._auto_start_after_method_switch(method))

        try:
            self._redirect_to_strategies_page_for_method(method)
        except Exception:
            pass

    def _redirect_to_strategies_page_for_method(self, method: str) -> None:
        redirect_to_strategies_page_for_method(self, method)

    def _auto_start_after_method_switch(self, method: str):
        from log import log

        try:
            if not hasattr(self, 'dpi_controller') or not self.dpi_controller:
                return

            if method == "orchestra":
                log("Автозапуск Оркестр", "INFO")
                self.dpi_controller.start_dpi_async(selected_mode=None, launch_method="orchestra")

            elif method == "direct_zapret2":
                from config import get_dpi_autostart
                if not get_dpi_autostart():
                    return

                from core.services import get_direct_flow_coordinator

                try:
                    profile = get_direct_flow_coordinator().ensure_launch_profile(
                        "direct_zapret2",
                        require_filters=False,
                    )
                except Exception:
                    return

                selected_mode = profile.to_selected_mode()
                self.dpi_controller.start_dpi_async(selected_mode=selected_mode, launch_method=method)

            elif method == "direct_zapret2_orchestra":
                from config import get_dpi_autostart
                if not get_dpi_autostart():
                    return

                from preset_orchestra_zapret2 import (
                    ensure_default_preset_exists,
                    get_active_preset_path,
                    get_active_preset_name,
                )

                if not ensure_default_preset_exists():
                    return

                preset_path = get_active_preset_path()
                preset_name = get_active_preset_name() or "Default"

                if not preset_path.exists():
                    return

                selected_mode = {
                    'is_preset_file': True,
                    'name': f"Пресет оркестра: {preset_name}",
                    'preset_path': str(preset_path),
                }
                self.dpi_controller.start_dpi_async(selected_mode=selected_mode, launch_method=method)

            elif method == "direct_zapret1":
                from config import get_dpi_autostart
                if not get_dpi_autostart():
                    return

                from core.services import get_direct_flow_coordinator

                try:
                    profile = get_direct_flow_coordinator().ensure_launch_profile(
                        "direct_zapret1",
                        require_filters=False,
                    )
                except Exception:
                    return

                selected_mode = profile.to_selected_mode()
                self.dpi_controller.start_dpi_async(selected_mode=selected_mode, launch_method=method)

        except Exception as e:
            log(f"Ошибка автозапуска после переключения режима: {e}", "ERROR")

    def _proxy_start_click(self):
        self.home_page.start_btn.click()

    def _proxy_stop_click(self):
        self.home_page.stop_btn.click()

    def _proxy_stop_and_exit(self):
        from log import log
        log("Остановка winws и закрытие программы...", "INFO")
        if hasattr(self, "request_exit"):
            self.request_exit(stop_dpi=True)
            return
        if hasattr(self, 'dpi_controller') and self.dpi_controller:
            self._closing_completely = True
            self.dpi_controller.stop_and_exit_async()
        else:
            self.home_page.stop_btn.click()
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()

    def _proxy_test_click(self):
        self.home_page.test_btn.click()

    def _proxy_folder_click(self):
        self.home_page.folder_btn.click()

    def _open_subscription_dialog(self):
        self.show_page(PageName.PREMIUM)

    def _get_direct_strategy_summary(self, max_items: int = 2) -> str:
        try:
            from strategy_menu import get_direct_strategy_selections
            from strategy_menu.strategies_registry import registry

            selections = get_direct_strategy_selections() or {}
            active_names: list[str] = []
            for cat_key in registry.get_all_category_keys_by_command_order():
                sid = selections.get(cat_key, "none") or "none"
                if sid == "none":
                    continue
                info = registry.get_category_info(cat_key)
                active_names.append(getattr(info, "full_name", None) or cat_key)

            if not active_names:
                return "Не выбрана"
            if len(active_names) <= max_items:
                return " • ".join(active_names)
            return " • ".join(active_names[:max_items]) + f" +{len(active_names) - max_items} ещё"
        except Exception:
            return "Прямой запуск"

    def update_current_strategy_display(self, strategy_name: str):
        launch_method = None
        try:
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
            if launch_method in ("direct_zapret2", "direct_zapret2_orchestra", "direct_zapret1"):
                strategy_name = self._get_direct_strategy_summary()
        except Exception:
            pass

        self.control_page.update_strategy(strategy_name)
        try:
            page = getattr(self, "zapret2_direct_control_page", None)
            if page and hasattr(page, "update_strategy"):
                page.update_strategy(strategy_name)
        except Exception:
            pass

        for page_attr in (
            'zapret2_direct_control_page', 'orchestra_zapret2_control_page',
            'zapret2_strategies_page', 'zapret2_orchestra_strategies_page',
            'orchestra_zapret2_user_presets_page', 'zapret1_direct_control_page',
            'zapret1_strategies_page',
        ):
            page = getattr(self, page_attr, None)
            if page and hasattr(page, 'update_current_strategy'):
                page.update_current_strategy(strategy_name)

        if hasattr(self.home_page, "update_launch_method_card"):
            self.home_page.update_launch_method_card()

    def update_autostart_display(self, enabled: bool, strategy_name: str = None):
        self.home_page.update_autostart_status(enabled)
        self.autostart_page.update_status(enabled, strategy_name)

    def update_subscription_display(self, is_premium: bool, days: int = None):
        self.home_page.update_subscription_status(is_premium, days)
        self.about_page.update_subscription_status(is_premium, days)

    def set_status_text(self, text: str, status: str = "neutral"):
        self.home_page.set_status(text, status)

    def _on_autostart_enabled(self):
        from log import log
        log("Автозапуск включён через страницу настроек", "INFO")
        self.update_autostart_display(True)

    def _on_autostart_disabled(self):
        from log import log
        log("Автозапуск отключён через страницу настроек", "INFO")
        self.update_autostart_display(False)

    def _on_subscription_updated(self, is_premium: bool, days_remaining: int):
        from log import log
        log(f"Статус подписки обновлён: premium={is_premium}, days={days_remaining}", "INFO")
        self.update_subscription_display(is_premium, days_remaining if days_remaining > 0 else None)

        if hasattr(self, 'appearance_page') and self.appearance_page:
            self.appearance_page.set_premium_status(is_premium)

    def _on_strategy_selected_from_page(self, strategy_id: str, strategy_name: str):
        from log import log
        try:
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
        except Exception:
            launch_method = "direct_zapret2"

        sender = None
        try:
            sender = self.sender()
        except Exception:
            sender = None

        if launch_method == "direct_zapret2" and sender is getattr(self, "zapret2_strategies_page", None):
            display_name = self._get_direct_strategy_summary()
            self.update_current_strategy_display(display_name)
            if hasattr(self, "parent_app"):
                try:
                    self.parent_app.current_strategy_name = display_name
                except Exception:
                    pass
            return

        log(f"Стратегия выбрана из страницы: {strategy_id} - {strategy_name}", "INFO")
        self.update_current_strategy_display(strategy_name)

        if hasattr(self, 'parent_app') and hasattr(self.parent_app, 'on_strategy_selected_from_dialog'):
            self.parent_app.on_strategy_selected_from_dialog(strategy_id, strategy_name)

    def _on_open_category_detail(self, category_key: str, current_strategy_id: str):
        from log import log
        from strategy_menu.strategies_registry import registry

        try:
            category_info = registry.get_category_info(category_key)
            if not category_info:
                return

            detail_page = self._ensure_page(PageName.ZAPRET2_STRATEGY_DETAIL)
            if detail_page and hasattr(detail_page, 'show_category'):
                detail_page.show_category(category_key, category_info, current_strategy_id)

            self.show_page(PageName.ZAPRET2_STRATEGY_DETAIL)

            try:
                self._direct_zapret2_last_opened_category_key = category_key
                self._direct_zapret2_restore_detail_on_open = True
            except Exception:
                pass
        except Exception as e:
            log(f"Error opening category detail: {e}", "ERROR")

    def _on_strategy_detail_back(self):
        from strategy_menu import get_strategy_launch_method
        method = get_strategy_launch_method()

        if method == "direct_zapret2_orchestra":
            self.show_page(PageName.ZAPRET2_ORCHESTRA_CONTROL)
        elif method == "direct_zapret2":
            self.show_page(PageName.ZAPRET2_DIRECT)
        elif method == "direct_zapret1":
            self.show_page(PageName.ZAPRET1_DIRECT_CONTROL)
        else:
            self.show_page(PageName.CONTROL)

    def _on_strategy_detail_selected(self, category_key: str, strategy_id: str):
        from log import log
        log(f"Strategy selected from detail: {category_key} = {strategy_id}", "INFO")
        if hasattr(self, 'zapret2_strategies_page') and hasattr(self.zapret2_strategies_page, 'apply_strategy_selection'):
            self.zapret2_strategies_page.apply_strategy_selection(category_key, strategy_id)

    def _on_strategy_detail_filter_mode_changed(self, category_key: str, filter_mode: str):
        try:
            if hasattr(self, 'zapret2_strategies_page') and hasattr(self.zapret2_strategies_page, 'apply_filter_mode_change'):
                self.zapret2_strategies_page.apply_filter_mode_change(category_key, filter_mode)
        except Exception:
            pass

    # ── Zapret 1 strategy detail ────────────────────────────────────────────

    def _open_zapret1_category_detail(self, category_key: str, category_info: dict) -> None:
        from log import log
        try:
            detail_page = self._ensure_page(PageName.ZAPRET1_STRATEGY_DETAIL)
            if detail_page is None:
                log("ZAPRET1_STRATEGY_DETAIL page not found", "ERROR")
                return

            from core.presets.direct_facade import DirectPresetFacade

            def _reload_dpi():
                try:
                    page = getattr(self, "zapret1_direct_control_page", None)
                    if page and hasattr(page, "_reload_dpi"):
                        page._reload_dpi()
                except Exception:
                    pass

            manager = DirectPresetFacade.from_launch_method(
                "direct_zapret1",
                on_dpi_reload_needed=_reload_dpi,
            )
            detail_page.set_category(category_key, category_info, manager)
            self.show_page(PageName.ZAPRET1_STRATEGY_DETAIL)
        except Exception as e:
            log(f"Error opening V1 category detail: {e}", "ERROR")

    def _on_z1_strategy_detail_selected(self, category_key: str, strategy_id: str) -> None:
        from log import log
        log(f"V1 strategy detail selected: {category_key} = {strategy_id}", "INFO")
        # Обновить субтитры карточек на странице списка категорий
        page = getattr(self, "zapret1_strategies_page", None)
        if page and hasattr(page, "_refresh_subtitles"):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(100, page._refresh_subtitles)

    def show_autostart_page(self):
        self.show_page(PageName.AUTOSTART)

    def show_hosts_page(self):
        self.show_page(PageName.HOSTS)

    def show_servers_page(self):
        self.show_page(PageName.SERVERS)

    def _show_active_zapret2_control_page(self):
        try:
            from strategy_menu import get_strategy_launch_method

            if get_strategy_launch_method() == "direct_zapret2_orchestra":
                self.show_page(PageName.ZAPRET2_ORCHESTRA_CONTROL)
            else:
                self.show_page(PageName.ZAPRET2_DIRECT_CONTROL)
        except Exception:
            self.show_page(PageName.ZAPRET2_DIRECT_CONTROL)

    def _navigate_to_control(self):
        try:
            from strategy_menu import get_strategy_launch_method
            if get_strategy_launch_method() == "direct_zapret2":
                self.show_page(PageName.ZAPRET2_DIRECT_CONTROL)
                return
            if get_strategy_launch_method() == "direct_zapret2_orchestra":
                self.show_page(PageName.ZAPRET2_ORCHESTRA_CONTROL)
                return
            if get_strategy_launch_method() == "direct_zapret1":
                self.show_page(PageName.ZAPRET1_DIRECT_CONTROL)
                return
            if get_strategy_launch_method() == "orchestra":
                self.show_page(PageName.ORCHESTRA)
                return
        except Exception:
            pass
        self.show_page(PageName.CONTROL)

    def _navigate_to_strategies(self):
        from log import log

        try:
            from strategy_menu import get_strategy_launch_method
            method = get_strategy_launch_method()

            if method == "orchestra":
                target_page = PageName.ORCHESTRA
            elif method == "direct_zapret2_orchestra":
                target_page = PageName.ZAPRET2_ORCHESTRA_CONTROL
            elif method == "direct_zapret2":
                last_key = getattr(self, "_direct_zapret2_last_opened_category_key", None)
                want_restore = bool(getattr(self, "_direct_zapret2_restore_detail_on_open", False))

                if want_restore and last_key:
                    try:
                        from strategy_menu.strategies_registry import registry
                        category_info = registry.get_category_info(last_key)
                        detail_page = self._ensure_page(PageName.ZAPRET2_STRATEGY_DETAIL)
                        if category_info and detail_page and hasattr(detail_page, "show_category"):
                            try:
                                from core.presets.direct_facade import DirectPresetFacade

                                selections = DirectPresetFacade.from_launch_method("direct_zapret2").get_strategy_selections() or {}
                                current_strategy_id = selections.get(last_key, "none")
                            except Exception:
                                current_strategy_id = "none"
                            detail_page.show_category(last_key, category_info, current_strategy_id)
                            target_page = PageName.ZAPRET2_STRATEGY_DETAIL
                        else:
                            target_page = PageName.ZAPRET2_DIRECT_CONTROL
                    except Exception:
                        target_page = PageName.ZAPRET2_DIRECT_CONTROL
                else:
                    target_page = PageName.ZAPRET2_DIRECT_CONTROL
            elif method == "direct_zapret1":
                target_page = PageName.ZAPRET1_DIRECT_CONTROL
            else:
                target_page = PageName.CONTROL

            self.show_page(target_page)
        except Exception as e:
            log(f"Ошибка определения метода запуска стратегий: {e}", "ERROR")
            self.show_page(PageName.ZAPRET2_DIRECT)

    def _navigate_to_dpi_settings(self):
        self.show_page(PageName.DPI_SETTINGS)
