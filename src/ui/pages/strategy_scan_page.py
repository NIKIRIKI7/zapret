"""Strategy Scanner page — brute-force DPI bypass strategy selection.

Can be used as a standalone page or embedded as a tab inside BlockCheck.
Tests strategies one by one through winws2 + HTTPS probe.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QFont, QColor, QAction
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QHeaderView, QMenu

from blockcheck.strategy_scan_page_controller import StrategyScanPageController
from ui.pages.base_page import BasePage, ScrollBlockingTextEdit
from ui.popup_menu import exec_popup_menu
from ui.text_catalog import tr as tr_catalog

try:
    from qfluentwidgets import (
        ComboBox, CaptionLabel, BodyLabel,
        ProgressBar, qconfig,
        TableWidget, PushButton, LineEdit, RoundMenu,
    )
    HAS_FLUENT = True
except ImportError:
    HAS_FLUENT = False
    RoundMenu = None
    from PyQt6.QtWidgets import (
        QComboBox as ComboBox,
        QTableWidget as TableWidget,
        QPushButton as PushButton,
        QLineEdit as LineEdit,
        QProgressBar as ProgressBar,
    )

from ui.compat_widgets import (
    SettingsCard, ActionButton, PrimaryActionButton, InfoBarHelper,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker (QObject, runs StrategyScanner in a daemon thread)
# ---------------------------------------------------------------------------

class StrategyScanWorker(QObject):
    """Bridges StrategyScanner (sync, bg thread) to Qt signals (main thread)."""

    strategy_started = pyqtSignal(str, int, int)   # name, index, total
    strategy_result = pyqtSignal(object)            # StrategyProbeResult
    scan_log = pyqtSignal(str)                      # log line
    phase_changed = pyqtSignal(str)                 # phase description
    scan_finished = pyqtSignal(object)              # StrategyScanReport

    def __init__(
        self,
        target: str,
        mode: str = "quick",
        start_index: int = 0,
        scan_protocol: str = "tcp_https",
        udp_games_scope: str = "all",
        parent=None,
    ):
        super().__init__(parent)
        self._target = target
        self._mode = mode
        self._scan_protocol = scan_protocol
        self._udp_games_scope = udp_games_scope
        try:
            self._start_index = max(0, int(start_index))
        except Exception:
            self._start_index = 0
        self._scanner = None
        self._cancelled = False
        self._bg_thread: threading.Thread | None = None

    def start(self):
        self._cancelled = False
        self._bg_thread = threading.Thread(
            target=self._run_in_thread, daemon=True, name="strategy-scan-worker",
        )
        self._bg_thread.start()

    def _run_in_thread(self):
        try:
            from blockcheck.strategy_scanner import StrategyScanner
            self._scanner = StrategyScanner(
                target=self._target,
                mode=self._mode,
                start_index=self._start_index,
                callback=self,
                scan_protocol=self._scan_protocol,
                udp_games_scope=self._udp_games_scope,
            )
            report = self._scanner.run()
            self.scan_finished.emit(report)
        except Exception as e:
            logger.exception("StrategyScanWorker crashed")
            self.scan_log.emit(f"ERROR: {e}")
            self.scan_finished.emit(None)

    def stop(self):
        self._cancelled = True
        if self._scanner:
            self._scanner.cancel()

    @property
    def is_running(self) -> bool:
        return self._bg_thread is not None and self._bg_thread.is_alive()

    # --- StrategyScanCallback implementation (called from bg thread) ---
    def on_strategy_started(self, name, index, total):
        self.strategy_started.emit(name, index, total)

    def on_strategy_result(self, result):
        self.strategy_result.emit(result)

    def on_log(self, message):
        self.scan_log.emit(message)

    def on_phase(self, phase):
        self.phase_changed.emit(phase)

    def is_cancelled(self):
        return self._cancelled


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

class StrategyScanPage(BasePage):
    """Strategy Scanner — brute-force DPI bypass strategy testing."""

    back_clicked = pyqtSignal()

    def __init__(self, parent=None, *, embedded: bool = False):
        self._embedded = bool(embedded)
        super().__init__(
            title=tr_catalog("page.strategy_scan.title", default="Подбор стратегии"),
            subtitle=tr_catalog("page.strategy_scan.subtitle",
                                default="Автоматический перебор стратегий обхода DPI"),
            parent=parent,
            title_key="page.strategy_scan.title",
            subtitle_key="page.strategy_scan.subtitle",
        )
        self.setObjectName("StrategyScanPage")

        self._worker: StrategyScanWorker | None = None
        self._controller = StrategyScanPageController()
        self._result_rows: list[dict] = []
        self._scan_target: str = ""
        self._scan_protocol: str = "tcp_https"
        self._scan_udp_games_scope: str = "all"
        self._scan_mode: str = "quick"
        self._scan_cursor: int = 0
        self._run_log_file: Path | None = None
        self._quick_domain_btn: ActionButton | None = None
        self._quick_domains_cache: list[str] | None = None
        self._quick_stun_targets_cache: list[str] | None = None
        self._target_label: QLabel | None = None
        self._games_scope_label: QLabel | None = None
        self._games_scope_combo = None
        self._udp_scope_hint_label: QLabel | None = None
        self._prepare_support_btn = None
        self._support_status_label = None

        self.enable_deferred_ui_build(after_build=self._after_ui_built)

    def _after_ui_built(self) -> None:
        self._connect_theme()

        if self._embedded:
            try:
                if self.title_label is not None:
                    self.title_label.setVisible(False)
                if self.subtitle_label is not None:
                    self.subtitle_label.setVisible(False)
            except Exception:
                pass
            try:
                self.vBoxLayout.setContentsMargins(0, 8, 0, 0)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        if not self._embedded:
            # ── Back button ──
            back_row = QHBoxLayout()
            back_btn = ActionButton(
                tr_catalog("page.strategy_scan.back", default="Назад"),
                icon_name="fa5s.arrow-left",
            )
            back_btn.clicked.connect(self._on_back)
            back_row.addWidget(back_btn)
            back_row.addStretch()
            self.add_widget(self._wrap_layout(back_row))

        # ── Control Card ──
        self._control_card = SettingsCard(
            tr_catalog("page.strategy_scan.control", default="Управление сканированием")
        )

        # Row 1: protocol + mode + target
        settings_row = QHBoxLayout()
        settings_row.setSpacing(12)

        protocol_label = CaptionLabel(
            tr_catalog("page.strategy_scan.protocol", default="Протокол:")
        ) if HAS_FLUENT else QLabel(tr_catalog("page.strategy_scan.protocol", default="Протокол:"))
        settings_row.addWidget(protocol_label)

        self._protocol_combo = ComboBox()
        self._protocol_combo.addItem(
            tr_catalog("page.strategy_scan.protocol_tcp", default="TCP/HTTPS"),
            userData="tcp_https",
        )
        self._protocol_combo.addItem(
            tr_catalog("page.strategy_scan.protocol_stun", default="STUN Voice (Discord/Telegram)"),
            userData="stun_voice",
        )
        self._protocol_combo.addItem(
            tr_catalog("page.strategy_scan.protocol_games", default="UDP Games (Roblox/Amazon/Steam)"),
            userData="udp_games",
        )
        self._protocol_combo.setCurrentIndex(0)
        self._protocol_combo.setFixedWidth(150)
        self._protocol_combo.currentIndexChanged.connect(self._on_protocol_changed)
        settings_row.addWidget(self._protocol_combo)

        self._games_scope_label = CaptionLabel(
            tr_catalog("page.strategy_scan.udp_scope", default="Охват UDP:")
        ) if HAS_FLUENT else QLabel(tr_catalog("page.strategy_scan.udp_scope", default="Охват UDP:"))
        settings_row.addWidget(self._games_scope_label)

        self._games_scope_combo = ComboBox()
        self._games_scope_combo.addItem(
            tr_catalog("page.strategy_scan.udp_scope_all", default="Все ipset (по умолчанию)"),
            userData="all",
        )
        self._games_scope_combo.addItem(
            tr_catalog("page.strategy_scan.udp_scope_games_only", default="Только игровые ipset"),
            userData="games_only",
        )
        self._games_scope_combo.setCurrentIndex(0)
        self._games_scope_combo.setFixedWidth(220)
        self._games_scope_combo.currentIndexChanged.connect(self._on_udp_games_scope_changed)
        settings_row.addWidget(self._games_scope_combo)

        settings_row.addSpacing(16)

        mode_label = CaptionLabel(
            tr_catalog("page.strategy_scan.mode", default="Режим:")
        ) if HAS_FLUENT else QLabel(tr_catalog("page.strategy_scan.mode", default="Режим:"))
        settings_row.addWidget(mode_label)

        self._mode_combo = ComboBox()
        self._mode_combo.addItem(
            tr_catalog("page.strategy_scan.mode_quick", default="Быстрый (30)"), "quick"
        )
        self._mode_combo.addItem(
            tr_catalog("page.strategy_scan.mode_standard", default="Стандартный (80)"), "standard"
        )
        self._mode_combo.addItem(
            tr_catalog("page.strategy_scan.mode_full", default="Полный (все)"), "full"
        )
        self._mode_combo.setCurrentIndex(0)
        self._mode_combo.setFixedWidth(180)
        settings_row.addWidget(self._mode_combo)

        settings_row.addSpacing(16)

        target_label = CaptionLabel(
            tr_catalog("page.strategy_scan.target", default="Цель:")
        ) if HAS_FLUENT else QLabel(tr_catalog("page.strategy_scan.target", default="Цель:"))
        self._target_label = target_label
        settings_row.addWidget(target_label)

        self._target_input = LineEdit()
        self._target_input.setText(
            tr_catalog("page.strategy_scan.target.default", default="discord.com")
        )
        self._target_input.setPlaceholderText(
            tr_catalog("page.strategy_scan.target.placeholder", default="discord.com")
        )
        self._target_input.setFixedWidth(200)
        self._target_input.setFixedHeight(33)
        settings_row.addWidget(self._target_input)

        self._quick_domain_btn = ActionButton(
            tr_catalog("page.strategy_scan.quick_domains", default="Быстрый выбор"),
            icon_name="fa5s.list",
        )
        self._quick_domain_btn.setToolTip(
            tr_catalog(
                "page.strategy_scan.quick_domains_hint",
                default="Выберите домен из готового списка",
            )
        )
        self._quick_domain_btn.clicked.connect(self._show_quick_domains_menu)
        settings_row.addWidget(self._quick_domain_btn)

        settings_row.addStretch()
        self._control_card.add_layout(settings_row)

        self._udp_scope_hint_label = CaptionLabel("") if HAS_FLUENT else QLabel("")
        self._udp_scope_hint_label.setWordWrap(True)
        self._control_card.add_widget(self._udp_scope_hint_label)

        # Row 2: buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._start_btn = PrimaryActionButton(
            tr_catalog("page.strategy_scan.start", default="Начать сканирование"),
            icon_name="fa5s.search",
        )
        self._start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self._start_btn)

        self._stop_btn = ActionButton(
            tr_catalog("page.strategy_scan.stop", default="Остановить"),
            icon_name="fa5s.stop",
        )
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self._stop_btn)

        btn_row.addStretch()
        self._control_card.add_layout(btn_row)

        # Progress bar (determinate)
        self._progress_bar = ProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._control_card.add_widget(self._progress_bar)

        # Status label
        self._status_label = CaptionLabel(
            tr_catalog("page.strategy_scan.ready", default="Готово к сканированию")
        ) if HAS_FLUENT else QLabel(tr_catalog("page.strategy_scan.ready", default="Готово к сканированию"))
        self._control_card.add_widget(self._status_label)

        self.add_widget(self._control_card)

        # ── Warning Card ──
        self._warning_card = SettingsCard(
            tr_catalog("page.strategy_scan.warning_title", default="Внимание")
        )
        warning_text = BodyLabel() if HAS_FLUENT else QLabel()
        warning_text.setText(tr_catalog(
            "page.strategy_scan.warning_text",
            default="Во время сканирования текущий обход DPI будет остановлен. "
                    "Каждая стратегия тестируется отдельно через winws2. "
                    "После завершения можно перезапустить обход.",
        ))
        warning_text.setWordWrap(True)
        self._warning_card.add_widget(warning_text)
        self.add_widget(self._warning_card)

        # ── Results Table Card ──
        self._results_card = SettingsCard(
            tr_catalog("page.strategy_scan.results", default="Результаты")
        )

        self._table = TableWidget()
        self._table.setColumnCount(5)
        headers = [
            "#",
            tr_catalog("page.strategy_scan.col_strategy", default="Стратегия"),
            tr_catalog("page.strategy_scan.col_status", default="Статус"),
            tr_catalog("page.strategy_scan.col_time", default="Время (мс)"),
            tr_catalog("page.strategy_scan.col_action", default="Действие"),
        ]
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)
        self._table.setMinimumHeight(250)
        self._table.verticalHeader().setVisible(False)

        try:
            header = self._table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            self._table.setColumnWidth(0, 50)
        except Exception:
            pass

        self._results_card.add_widget(self._table)
        self.add_widget(self._results_card)

        # ── Log Card ──
        self._log_card = SettingsCard(
            tr_catalog("page.strategy_scan.log", default="Подробный лог")
        )

        # Кнопка "Развернуть / Свернуть" в заголовке лог-карточки
        self._log_expanded = False
        self._expand_log_btn = PushButton()
        self._expand_log_btn.setText("Развернуть")
        self._expand_log_btn.setFixedWidth(120)
        self._expand_log_btn.clicked.connect(self._toggle_log_expand)
        log_header = QHBoxLayout()
        self._support_status_label = CaptionLabel("") if HAS_FLUENT else QLabel("")
        self._support_status_label.setWordWrap(True)
        log_header.addWidget(self._support_status_label, 1)
        log_header.addStretch()
        self._prepare_support_btn = ActionButton(
            tr_catalog(
                "page.strategy_scan.prepare_support",
                default="Подготовить обращение",
            ),
            icon_name="fa5b.github",
        )
        self._prepare_support_btn.clicked.connect(self._prepare_support_from_strategy_scan)
        log_header.addWidget(self._prepare_support_btn)
        log_header.addWidget(self._expand_log_btn)
        self._log_card.add_layout(log_header)

        self._log_edit = ScrollBlockingTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMinimumHeight(180)
        self._log_edit.setMaximumHeight(300)
        self._log_edit.setFont(QFont("Consolas", 9))
        self._log_card.add_widget(self._log_edit)
        self.add_widget(self._log_card)

        self._on_protocol_changed(self._protocol_combo.currentIndex())

    # ------------------------------------------------------------------
    # Log expand / collapse
    # ------------------------------------------------------------------

    def _toggle_log_expand(self):
        """Развернуть/свернуть лог на всю страницу."""
        self._log_expanded = not self._log_expanded

        if self._log_expanded:
            # Скрываем остальные карточки
            self._control_card.setVisible(False)
            self._warning_card.setVisible(False)
            self._results_card.setVisible(False)
            # Убираем потолок высоты лога
            self._log_edit.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            self._log_edit.setMinimumHeight(400)
            self._expand_log_btn.setText("Свернуть")
        else:
            # Восстанавливаем карточки
            self._control_card.setVisible(True)
            self._warning_card.setVisible(True)
            self._results_card.setVisible(True)
            # Восстанавливаем ограничения
            self._log_edit.setMinimumHeight(180)
            self._log_edit.setMaximumHeight(300)
            self._expand_log_btn.setText("Развернуть")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_layout(layout: QHBoxLayout) -> QWidget:
        """Wrap a layout in a transparent QWidget for add_widget()."""
        w = QWidget()
        w.setLayout(layout)
        w.setStyleSheet("background: transparent;")
        return w

    def _scan_protocol_from_combo(self) -> str:
        """Current scan protocol from UI combo."""
        data = self._protocol_combo.currentData()
        raw = str(data or "").strip().lower()
        if raw == "stun_voice":
            return "stun_voice"
        if raw == "udp_games":
            return "udp_games"
        return "tcp_https"

    def _udp_games_scope_from_combo(self) -> str:
        """Current UDP games scope selection from UI combo."""
        if self._games_scope_combo is None:
            return "all"
        data = self._games_scope_combo.currentData()
        return self._controller.normalize_udp_games_scope(str(data or "all"))

    def _on_protocol_changed(self, _index: int) -> None:
        """Adjust target input defaults when protocol changes."""
        protocol = self._scan_protocol_from_combo()
        current = self._target_input.text()

        is_udp_games = protocol == "udp_games"
        if self._games_scope_label is not None:
            self._games_scope_label.setVisible(is_udp_games)
        if self._games_scope_combo is not None:
            self._games_scope_combo.setVisible(is_udp_games)
            self._games_scope_combo.setEnabled(is_udp_games)

        show_target_controls = protocol != "udp_games"
        if self._target_label is not None:
            self._target_label.setVisible(show_target_controls)
        self._target_input.setVisible(show_target_controls)
        if self._quick_domain_btn is not None:
            self._quick_domain_btn.setVisible(show_target_controls)

        if protocol in {"stun_voice", "udp_games"} and current and ":" not in current and not current.upper().startswith("STUN:"):
            # When switching from TCP mode, a plain domain is usually not a STUN endpoint.
            current = ""

        normalized = self._controller.normalize_target_input(current, protocol)
        if not normalized:
            normalized = self._controller.default_target_for_protocol(protocol)

        self._target_input.setText(normalized)
        self._target_input.setPlaceholderText(self._controller.default_target_for_protocol(protocol))
        self._refresh_udp_scope_hint()

    def _on_udp_games_scope_changed(self, _index: int) -> None:
        """Update UDP scope helper text after combo change."""
        self._refresh_udp_scope_hint()

    def _refresh_udp_scope_hint(self) -> None:
        """Refresh compact helper label with resolved UDP ipset sources."""
        if self._udp_scope_hint_label is None:
            return

        protocol = self._scan_protocol_from_combo()
        if protocol != "udp_games":
            self._udp_scope_hint_label.setVisible(False)
            return

        scope = self._udp_games_scope_from_combo()
        paths = self._controller.resolve_games_ipset_paths(scope)

        if scope == "games_only":
            scope_label = tr_catalog("page.strategy_scan.udp_scope_games_only", default="Только игровые ipset")
        else:
            scope_label = tr_catalog("page.strategy_scan.udp_scope_all", default="Все ipset (по умолчанию)")

        short_names = [Path(p).name or p for p in paths]
        preview = ", ".join(short_names[:4])
        if len(short_names) > 4:
            preview += f", ... (+{len(short_names) - 4})"

        hint = (
            f"UDP scope: {scope_label} | "
            f"ipset files: {len(paths)} | {preview}"
        )
        self._udp_scope_hint_label.setText(hint)
        self._udp_scope_hint_label.setToolTip("\n".join(paths))
        self._udp_scope_hint_label.setVisible(True)

    def _load_quick_domains(self) -> list[str]:
        """Load and cache quick domain choices for strategy scan."""
        if self._quick_domains_cache is not None:
            return list(self._quick_domains_cache)

        self._quick_domains_cache = self._controller.load_quick_domains()
        return list(self._quick_domains_cache)

    def _load_quick_stun_targets(self) -> list[str]:
        """Load and cache quick STUN endpoint choices."""
        if self._quick_stun_targets_cache is not None:
            return list(self._quick_stun_targets_cache)

        self._quick_stun_targets_cache = self._controller.load_quick_stun_targets()
        return list(self._quick_stun_targets_cache)

    def _show_quick_domains_menu(self) -> None:
        """Open popup menu with predefined targets for selected protocol."""
        if self._quick_domain_btn is None:
            return

        if HAS_FLUENT and RoundMenu is not None:
            menu = RoundMenu(parent=self)
        else:
            menu = QMenu(self)
        protocol = self._scan_protocol_from_combo()
        current = self._controller.normalize_target_input(self._target_input.text(), protocol)
        options = self._load_quick_domains() if protocol == "tcp_https" else self._load_quick_stun_targets()

        for option in options:
            action = QAction(option, menu)
            action.setCheckable(True)
            action.setChecked(option == current)
            action.triggered.connect(
                lambda checked=False, selected_target=option: self._on_pick_quick_domain(selected_target)
            )
            menu.addAction(action)

        if not menu.actions():
            return

        exec_popup_menu(
            menu,
            self._quick_domain_btn.mapToGlobal(self._quick_domain_btn.rect().bottomLeft()),
            owner=self,
        )

    def _on_pick_quick_domain(self, domain: str) -> None:
        """Fill the domain field from quick picker."""
        if not domain:
            return
        self._target_input.setText(domain)
        try:
            self._target_input.setFocus(Qt.FocusReason.OtherFocusReason)
            self._target_input.selectAll()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _connect_theme(self):
        if HAS_FLUENT:
            qconfig.themeChanged.connect(lambda _: self._apply_theme())

    def _apply_theme(self):
        pass  # Table colors are set per-cell, no global refresh needed

    # ------------------------------------------------------------------
    # Navigation cleanup
    # ------------------------------------------------------------------

    def _on_back(self):
        """Navigate back without interrupting background scan."""
        self.back_clicked.emit()

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def _on_start(self):
        if self._worker and self._worker.is_running:
            return

        scan_protocol = self._scan_protocol_from_combo()
        scan_games_scope = self._udp_games_scope_from_combo() if scan_protocol == "udp_games" else "all"

        _MODE_MAP = {0: "quick", 1: "standard", 2: "full"}
        mode = _MODE_MAP.get(self._mode_combo.currentIndex(), "quick")

        start_plan = self._controller.plan_scan_start(
            raw_target_input=self._target_input.text(),
            scan_protocol=scan_protocol,
            udp_games_scope=scan_games_scope,
            mode=mode,
            previous_target=self._scan_target,
            previous_protocol=self._scan_protocol,
            previous_scope=self._scan_udp_games_scope,
            result_rows_count=len(self._result_rows),
            table_row_count=self._table.rowCount(),
            starting_status_text=tr_catalog("page.strategy_scan.starting", default="Запуск сканирования..."),
        )
        self._target_input.setText(start_plan.target)

        if not start_plan.keep_current_results:
            self._table.setRowCount(0)
            self._result_rows.clear()
            self._log_edit.clear()
        self._set_support_status("")

        self._scan_target = start_plan.target
        self._scan_protocol = start_plan.scan_protocol
        self._scan_udp_games_scope = start_plan.udp_games_scope
        self._scan_mode = start_plan.mode
        self._scan_cursor = start_plan.scan_cursor
        log_state = self._controller.start_run_log(
            target=start_plan.target,
            mode=start_plan.mode,
            scan_protocol=start_plan.scan_protocol,
            resume_index=self._scan_cursor,
            udp_games_scope=start_plan.udp_games_scope,
        )
        self._run_log_file = log_state.path

        # UI state
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._protocol_combo.setEnabled(False)
        if self._games_scope_combo is not None:
            self._games_scope_combo.setEnabled(False)
        self._mode_combo.setEnabled(False)
        self._target_input.setEnabled(False)
        if self._quick_domain_btn is not None:
            self._quick_domain_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(self._scan_cursor)
        self._status_label.setText(start_plan.status_text)

        # Create and start worker
        self._worker = StrategyScanWorker(
            target=start_plan.target,
            mode=start_plan.mode,
            start_index=self._scan_cursor,
            scan_protocol=start_plan.scan_protocol,
            udp_games_scope=start_plan.udp_games_scope,
            parent=self,
        )
        self._worker.strategy_started.connect(self._on_strategy_started)
        self._worker.strategy_result.connect(self._on_strategy_result)
        self._worker.scan_log.connect(self._on_log)
        self._worker.phase_changed.connect(self._on_phase_changed)
        self._worker.scan_finished.connect(self._on_finished)
        self._worker.start()

    def _on_stop(self):
        if self._worker:
            self._worker.stop()
        self._stop_btn.setEnabled(False)
        self._status_label.setText(
            tr_catalog("page.strategy_scan.stopping", default="Остановка...")
        )
        # Force-reset UI if worker doesn't finish in 5s
        QTimer.singleShot(5000, self._force_stop)

    def _force_stop(self):
        if self._worker and self._worker.is_running:
            self._reset_ui()

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_strategy_started(self, name: str, index: int, total: int):
        if total > 0:
            self._progress_bar.setRange(0, total)
        if self._progress_bar.value() < self._scan_cursor:
            self._progress_bar.setValue(self._scan_cursor)
        working = sum(1 for r in self._result_rows if r.get("success"))
        self._status_label.setText(
            f"[{index + 1}/{total}] {name}  |  {working} рабочих"
        )

    def _on_strategy_result(self, result):
        """Add a row to the results table."""
        from PyQt6.QtWidgets import QTableWidgetItem

        row_idx = self._table.rowCount()
        self._table.insertRow(row_idx)

        # #
        num_item = QTableWidgetItem(str(self._scan_cursor + 1))
        num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row_idx, 0, num_item)

        # Strategy name
        name_item = QTableWidgetItem(result.strategy_name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        tip_parts = [result.strategy_args]
        if result.error:
            tip_parts.append(f"\n--- Ошибка ---\n{result.error}")
        name_item.setToolTip("".join(tip_parts))
        self._table.setItem(row_idx, 1, name_item)

        # Status
        if result.success:
            status_item = QTableWidgetItem("OK")
            status_item.setForeground(QColor("#52c477"))
        elif "timeout" in result.error.lower():
            status_item = QTableWidgetItem("TIMEOUT")
            status_item.setForeground(QColor("#888888"))
        else:
            status_item = QTableWidgetItem("FAIL")
            status_item.setForeground(QColor("#e05454"))
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        status_item.setToolTip(result.error if result.error else "OK")
        self._table.setItem(row_idx, 2, status_item)

        # Time
        time_text = f"{result.time_ms:.0f}" if result.time_ms > 0 else "—"
        time_item = QTableWidgetItem(time_text)
        time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row_idx, 3, time_item)

        # Action button (only for successful strategies)
        if result.success:
            apply_btn = PushButton()
            apply_btn.setText(tr_catalog("page.strategy_scan.apply", default="Применить"))
            apply_btn.setFixedHeight(26)
            apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            apply_btn.clicked.connect(
                lambda checked=False, args=result.strategy_args, name=result.strategy_name:
                    self._on_apply_strategy(args, name)
            )
            self._table.setCellWidget(row_idx, 4, apply_btn)

        # Track result and update progress after test completes
        self._result_rows.append({
            "id": getattr(result, "strategy_id", ""),
            "name": result.strategy_name,
            "args": result.strategy_args,
            "success": result.success,
        })
        self._scan_cursor += 1
        self._progress_bar.setValue(self._scan_cursor)
        self._controller.save_resume_state(
            self._scan_target,
            self._scan_protocol,
            self._scan_cursor,
            self._scan_udp_games_scope,
        )

        # Scroll to latest
        self._table.scrollToBottom()

    def _on_log(self, message: str):
        self._log_edit.append(message)
        self._controller.append_run_log(self._run_log_file, message)

    def _on_phase_changed(self, phase: str):
        self._status_label.setText(phase)
        self._controller.append_run_log(self._run_log_file, f"[PHASE] {phase}")

    def _on_finished(self, report):
        """Handle scan completion."""
        self._reset_ui()
        finish_plan = self._controller.finalize_scan_report(
            report,
            scan_target=self._scan_target,
            scan_protocol=self._scan_protocol,
            scan_udp_games_scope=self._scan_udp_games_scope,
            scan_mode=self._scan_mode,
            scan_cursor=self._scan_cursor,
            result_rows=self._result_rows,
        )

        if finish_plan.total_available > 0:
            self._progress_bar.setRange(0, finish_plan.total_available)

        self._status_label.setText(finish_plan.status_text)
        self._progress_bar.setValue(min(finish_plan.total_count, self._progress_bar.maximum()))
        if finish_plan.log_message:
            self._controller.append_run_log(self._run_log_file, finish_plan.log_message)

        if finish_plan.support_status_code == "ready_after_error":
            self._set_support_status(
                tr_catalog(
                    "page.strategy_scan.support_ready_after_error",
                    default="Можно подготовить обращение по логам ошибки",
                )
            )
            return

        self._set_support_status(
            tr_catalog(
                "page.strategy_scan.support_ready",
                default="Можно подготовить обращение по этому сканированию",
            )
        )

        try:
            if finish_plan.notification_kind == "baseline_accessible":
                if finish_plan.baseline_variant == "stun":
                    if self._scan_protocol == "udp_games":
                        baseline_title_default = "UDP уже доступен"
                    else:
                        baseline_title_default = "STUN уже доступен"
                    baseline_title = tr_catalog(
                        "page.strategy_scan.baseline_ok_title_stun",
                        default=baseline_title_default,
                    )
                    baseline_text = tr_catalog(
                        "page.strategy_scan.baseline_ok_text_stun",
                        default="STUN/UDP уже доступен без обхода DPI — результаты могут быть ложноположительными",
                    )
                else:
                    baseline_title = tr_catalog(
                        "page.strategy_scan.baseline_ok_title",
                        default="Домен уже доступен",
                    )
                    baseline_text = tr_catalog(
                        "page.strategy_scan.baseline_ok_text",
                        default="Домен доступен без обхода DPI — результаты могут быть ложноположительными",
                    )
                InfoBarHelper.warning(
                    self.window(),
                    baseline_title,
                    baseline_text,
                )
            elif finish_plan.notification_kind == "found":
                InfoBarHelper.success(
                    self.window(),
                    tr_catalog("page.strategy_scan.found", default="Найдены рабочие стратегии"),
                    f"{finish_plan.working_count} из {finish_plan.total_count}",
                )
            elif finish_plan.notification_kind == "not_found":
                InfoBarHelper.warning(
                    self.window(),
                    tr_catalog("page.strategy_scan.not_found", default="Рабочих стратегий не найдено"),
                    tr_catalog("page.strategy_scan.try_full",
                               default="Попробуйте полный режим сканирования"),
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Apply strategy
    # ------------------------------------------------------------------

    def _on_apply_strategy(self, strategy_args: str, strategy_name: str):
        """Copy the working strategy into the selected source preset."""
        try:
            result = self._controller.apply_strategy(
                strategy_args=strategy_args,
                strategy_name=strategy_name,
                scan_target=self._scan_target,
                scan_protocol=self._scan_protocol,
                scan_udp_games_scope=self._scan_udp_games_scope,
            )

            InfoBarHelper.success(
                self.window(),
                tr_catalog("page.strategy_scan.applied", default="Стратегия добавлена"),
                f"{result.strategy_name} добавлена в пресет для {result.applied_target}",
            )
        except Exception as e:
            logger.warning("Failed to apply strategy: %s", e)
            try:
                InfoBarHelper.warning(
                    self.window(),
                    "Ошибка",
                    str(e),
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _reset_ui(self):
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._protocol_combo.setEnabled(True)
        if self._games_scope_combo is not None:
            self._games_scope_combo.setEnabled(self._scan_protocol_from_combo() == "udp_games")
        self._mode_combo.setEnabled(True)
        self._target_input.setEnabled(True)
        if self._quick_domain_btn is not None:
            self._quick_domain_btn.setEnabled(True)

    def _set_support_status(self, text: str) -> None:
        if self._support_status_label is None:
            return
        self._support_status_label.setText(str(text or "").strip())

    def _prepare_support_from_strategy_scan(self) -> None:
        scan_protocol = self._scan_protocol or self._scan_protocol_from_combo()
        target = self._scan_target or self._controller.normalize_target_input(
            self._target_input.text(),
            scan_protocol,
        )
        if not target:
            target = self._controller.default_target_for_protocol(scan_protocol)

        protocol_label = self._protocol_combo.currentText() if self._protocol_combo is not None else scan_protocol
        mode_label = self._mode_combo.currentText() if self._mode_combo is not None else self._scan_mode

        try:
            feedback = self._controller.prepare_support(
                run_log_file=self._run_log_file,
                target=target,
                protocol_label=protocol_label,
                mode_label=mode_label,
                scan_protocol=scan_protocol,
            )
            result = feedback.result
            if result.zip_path:
                logger.info("Prepared Strategy Scan support archive: %s", result.zip_path)

            self._set_support_status(feedback.status_text)

            try:
                InfoBarHelper.success(
                    self.window(),
                    tr_catalog(
                        "page.strategy_scan.support_prepared_title",
                        default="Обращение подготовлено",
                    ),
                    feedback.info_text,
                )
            except Exception:
                pass
        except Exception as exc:
            logger.warning("Failed to prepare strategy-scan support bundle: %s", exc)
            self._set_support_status("Ошибка подготовки")
            try:
                InfoBarHelper.warning(
                    self.window(),
                    tr_catalog("page.strategy_scan.error", default="Ошибка сканирования"),
                    f"Не удалось подготовить обращение:\n{exc}",
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------

    def set_ui_language(self, language: str) -> None:
        super().set_ui_language(language)
        try:
            self._control_card.set_title(
                tr_catalog("page.strategy_scan.control", language=language,
                           default="Управление сканированием"))
            self._results_card.set_title(
                tr_catalog("page.strategy_scan.results", language=language,
                           default="Результаты"))
            self._log_card.set_title(
                tr_catalog("page.strategy_scan.log", language=language,
                           default="Подробный лог"))
            self._expand_log_btn.setText(
                tr_catalog("page.strategy_scan.collapse_log", language=language,
                           default="Свернуть")
                if self._log_expanded else
                tr_catalog("page.strategy_scan.expand_log", language=language,
                           default="Развернуть")
            )
            self._warning_card.set_title(
                tr_catalog("page.strategy_scan.warning_title", language=language,
                           default="Внимание"))
            self._start_btn.setText(
                tr_catalog("page.strategy_scan.start", language=language,
                           default="Начать сканирование"))
            self._stop_btn.setText(
                tr_catalog("page.strategy_scan.stop", language=language,
                           default="Остановить"))
            if self._prepare_support_btn is not None:
                self._prepare_support_btn.setText(
                    tr_catalog(
                        "page.strategy_scan.prepare_support",
                        language=language,
                        default="Подготовить обращение",
                    )
                )
            self._protocol_combo.setItemText(
                0,
                tr_catalog("page.strategy_scan.protocol_tcp", language=language, default="TCP/HTTPS"),
            )
            self._protocol_combo.setItemText(
                1,
                tr_catalog(
                    "page.strategy_scan.protocol_stun",
                    language=language,
                    default="STUN Voice (Discord/Telegram)",
                ),
            )
            self._protocol_combo.setItemText(
                2,
                tr_catalog(
                    "page.strategy_scan.protocol_games",
                    language=language,
                    default="UDP Games (Roblox/Amazon/Steam)",
                ),
            )
            if self._games_scope_label is not None:
                self._games_scope_label.setText(
                    tr_catalog("page.strategy_scan.udp_scope", language=language, default="Охват UDP:")
                )
            if self._games_scope_combo is not None:
                self._games_scope_combo.setItemText(
                    0,
                    tr_catalog(
                        "page.strategy_scan.udp_scope_all",
                        language=language,
                        default="Все ipset (по умолчанию)",
                    ),
                )
                self._games_scope_combo.setItemText(
                    1,
                    tr_catalog(
                        "page.strategy_scan.udp_scope_games_only",
                        language=language,
                        default="Только игровые ipset",
                    ),
                )
            if self._quick_domain_btn is not None:
                self._quick_domain_btn.setText(
                    tr_catalog("page.strategy_scan.quick_domains", language=language,
                               default="Быстрый выбор"))
                self._quick_domain_btn.setToolTip(
                    tr_catalog("page.strategy_scan.quick_domains_hint", language=language,
                               default="Выберите домен из готового списка"))
            self._refresh_udp_scope_hint()
        except Exception:
            pass
