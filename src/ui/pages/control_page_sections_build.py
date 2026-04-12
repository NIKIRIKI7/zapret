"""Build-helper простых секций Control page."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy

from ui.compat_widgets import SettingsCard, QuickActionsBar, PulsingDot
from ui.theme import get_cached_qta_pixmap


@dataclass(slots=True)
class ControlStatusWidgets:
    card: SettingsCard
    status_dot: object
    status_title: object
    status_desc: object


@dataclass(slots=True)
class ControlManagementWidgets:
    card: SettingsCard
    start_btn: object
    stop_winws_btn: object
    stop_and_exit_btn: object
    progress_bar: object
    loading_label: object


@dataclass(slots=True)
class ControlStrategyWidgets:
    card: SettingsCard
    strategy_icon: QLabel
    strategy_label: object
    strategy_desc: object


@dataclass(slots=True)
class ControlExtraActionsWidgets:
    section_label: object
    actions_group: QuickActionsBar
    test_btn: object
    folder_btn: object


def build_control_status_section(
    *,
    tr_fn,
    has_fluent_labels: bool,
    subtitle_label_cls,
    caption_label_cls,
) -> ControlStatusWidgets:
    status_card = SettingsCard()

    status_layout = QHBoxLayout()
    status_layout.setSpacing(16)

    status_dot = PulsingDot()
    status_layout.addWidget(status_dot)

    status_text_layout = QVBoxLayout()
    status_text_layout.setSpacing(2)

    if has_fluent_labels:
        status_title = subtitle_label_cls(
            tr_fn("page.control.status.checking", "Проверка...")
        )
    else:
        status_title = QLabel(
            tr_fn("page.control.status.checking", "Проверка...")
        )
        status_title.setStyleSheet("font-size: 15px; font-weight: 600;")
    status_text_layout.addWidget(status_title)

    if has_fluent_labels:
        status_desc = caption_label_cls(
            tr_fn("page.control.status.detecting", "Определение состояния процесса")
        )
    else:
        status_desc = QLabel(
            tr_fn("page.control.status.detecting", "Определение состояния процесса")
        )
        status_desc.setStyleSheet("font-size: 12px;")
    status_text_layout.addWidget(status_desc)

    status_layout.addLayout(status_text_layout, 1)
    status_card.add_layout(status_layout)
    return ControlStatusWidgets(
        card=status_card,
        status_dot=status_dot,
        status_title=status_title,
        status_desc=status_desc,
    )


def build_control_management_section(
    *,
    tr_fn,
    has_fluent_labels: bool,
    caption_label_cls,
    indeterminate_progress_bar_cls,
    big_action_button_cls,
    stop_button_cls,
    on_start,
    on_stop_winws,
    on_stop_and_exit,
    parent,
) -> ControlManagementWidgets:
    control_card = SettingsCard()

    buttons_layout = QHBoxLayout()
    buttons_layout.setSpacing(12)

    start_btn = big_action_button_cls(
        tr_fn("page.control.button.start", "Запустить Zapret"),
        "fa5s.play",
        accent=True,
    )
    start_btn.clicked.connect(on_start)
    buttons_layout.addWidget(start_btn)

    stop_winws_btn = stop_button_cls(
        tr_fn("page.control.button.stop_only_winws", "Остановить только winws.exe"),
        "fa5s.stop",
    )
    stop_winws_btn.clicked.connect(on_stop_winws)
    stop_winws_btn.setVisible(False)
    buttons_layout.addWidget(stop_winws_btn)

    stop_and_exit_btn = stop_button_cls(
        tr_fn("page.control.button.stop_and_exit", "Остановить и закрыть программу"),
        "fa5s.power-off",
    )
    stop_and_exit_btn.clicked.connect(on_stop_and_exit)
    stop_and_exit_btn.setVisible(False)
    buttons_layout.addWidget(stop_and_exit_btn)

    buttons_layout.addStretch()
    control_card.add_layout(buttons_layout)

    progress_bar = indeterminate_progress_bar_cls(parent)
    progress_bar.setVisible(False)
    control_card.add_widget(progress_bar)

    if has_fluent_labels:
        loading_label = caption_label_cls("")
    else:
        loading_label = QLabel("")
        loading_label.setStyleSheet("font-size: 12px;")
    loading_label.setVisible(False)
    control_card.add_widget(loading_label)

    return ControlManagementWidgets(
        card=control_card,
        start_btn=start_btn,
        stop_winws_btn=stop_winws_btn,
        stop_and_exit_btn=stop_and_exit_btn,
        progress_bar=progress_bar,
        loading_label=loading_label,
    )


def build_control_strategy_section(
    *,
    tr_fn,
    has_fluent_labels: bool,
    strong_body_label_cls,
    caption_label_cls,
    accent_hex: str,
) -> ControlStrategyWidgets:
    strategy_card = SettingsCard()

    strategy_layout = QHBoxLayout()
    strategy_layout.setSpacing(12)

    strategy_icon = QLabel()
    try:
        from ui.fluent_icons import fluent_pixmap

        strategy_icon.setPixmap(fluent_pixmap('fa5s.cog', 20))
    except Exception:
        strategy_icon.setPixmap(get_cached_qta_pixmap('fa5s.cog', color=accent_hex, size=20))
    strategy_icon.setFixedSize(24, 24)
    strategy_layout.addWidget(strategy_icon)

    strategy_text_layout = QVBoxLayout()
    strategy_text_layout.setSpacing(2)

    if has_fluent_labels:
        strategy_label = strong_body_label_cls(
            tr_fn("page.control.strategy.not_selected", "Не выбрана")
        )
    else:
        strategy_label = QLabel(
            tr_fn("page.control.strategy.not_selected", "Не выбрана")
        )
        strategy_label.setStyleSheet("font-size: 14px; font-weight: 500;")
    strategy_label.setWordWrap(True)
    strategy_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    strategy_text_layout.addWidget(strategy_label)

    if has_fluent_labels:
        strategy_desc = caption_label_cls(
            tr_fn("page.control.strategy.select_hint", "Выберите стратегию в разделе «Стратегии»")
        )
    else:
        strategy_desc = QLabel(
            tr_fn("page.control.strategy.select_hint", "Выберите стратегию в разделе «Стратегии»")
        )
        strategy_desc.setStyleSheet("font-size: 11px;")
    strategy_text_layout.addWidget(strategy_desc)

    strategy_layout.addLayout(strategy_text_layout, 1)
    strategy_card.add_layout(strategy_layout)

    return ControlStrategyWidgets(
        card=strategy_card,
        strategy_icon=strategy_icon,
        strategy_label=strategy_label,
        strategy_desc=strategy_desc,
    )


def build_control_extra_actions_section(
    *,
    tr_fn,
    strong_body_label_cls,
    action_button_cls,
    quick_actions_bar_cls,
    parent,
    on_test,
    on_open_folder,
) -> ControlExtraActionsWidgets:
    test_btn = action_button_cls(
        tr_fn("page.control.button.connection_test", "Тест соединения"),
        "fa5s.wifi",
    )
    test_btn.clicked.connect(on_test)
    folder_btn = action_button_cls(
        tr_fn("page.control.button.open_folder", "Открыть папку"),
        "fa5s.folder-open",
    )
    folder_btn.clicked.connect(on_open_folder)

    section_label = strong_body_label_cls(
        tr_fn("page.control.section.additional", "Дополнительные действия")
    )

    actions_group = quick_actions_bar_cls(parent)
    test_btn.setToolTip(
        tr_fn(
            "page.control.section.additional.test_desc",
            "Проверить сетевое подключение и доступность маршрута",
        )
    )
    folder_btn.setToolTip(
        tr_fn(
            "page.control.section.additional.folder_desc",
            "Быстро перейти к рабочей папке программы",
        )
    )
    actions_group.add_buttons([test_btn, folder_btn])

    return ControlExtraActionsWidgets(
        section_label=section_label,
        actions_group=actions_group,
        test_btn=test_btn,
        folder_btn=folder_btn,
    )
