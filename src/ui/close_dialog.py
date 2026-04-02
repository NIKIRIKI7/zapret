# ui/close_dialog.py
"""
WinUI диалог выбора варианта закрытия приложения.
Показывается при нажатии на крестик (X) в titlebar.
"""

from PyQt6.QtWidgets import QHBoxLayout
from qfluentwidgets import (
    MessageBoxBase, SubtitleLabel, BodyLabel,
)
from ui.dialog_action_buttons import create_dialog_action_button, create_dialog_cancel_button


class CloseDialog(MessageBoxBase):
    """
    WinUI диалог: варианты закрытия приложения.

    Результат через ask_close_action():
      - None    -> отмена (Esc / клик мимо)
      - "tray"  -> свернуть в трей
      - False   -> закрыть только GUI
      - True    -> закрыть GUI + остановить DPI
    """

    def __init__(self, parent=None):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)
        self.result_stop_dpi = None
        self.result_tray = False

        # --- Заголовок и описание ---
        self.titleLabel = SubtitleLabel("Закрыть приложение", self.widget)
        self.bodyLabel = BodyLabel(
            "DPI обход (winws) продолжит работать в фоне,\n"
            "если вы закроете только GUI.",
            self.widget,
        )
        self.bodyLabel.setWordWrap(True)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.bodyLabel)
        self.viewLayout.addSpacing(8)

        # --- Кнопка "Свернуть в трей" ---
        self.trayButton = create_dialog_action_button(
            self.widget,
            text="Свернуть в трей",
            icon_name="fa5s.window-restore",
            icon_color="#d0d0d0",
        )
        self.trayButton.clicked.connect(self._on_tray)
        self.viewLayout.addWidget(self.trayButton)

        # --- Кнопка "Закрыть только GUI" ---
        self.guiOnlyButton = create_dialog_action_button(
            self.widget,
            text="Закрыть только GUI",
            icon_name="fa5s.sign-out-alt",
            icon_color="#aaaaaa",
        )
        self.guiOnlyButton.clicked.connect(self._on_gui_only)
        self.viewLayout.addWidget(self.guiOnlyButton)

        # --- Кнопка "Закрыть и остановить DPI" (danger/red) ---
        self.stopDpiButton = create_dialog_action_button(
            self.widget,
            text="Закрыть и остановить DPI",
            icon_name="fa5s.stop-circle",
            icon_color="#ffffff",
            danger=True,
        )
        self.stopDpiButton.clicked.connect(self._on_stop_dpi)
        self.viewLayout.addWidget(self.stopDpiButton)

        # --- Кнопка "Отмена" (прозрачная, по центру) ---
        self._cancelRow = QHBoxLayout()
        self._cancelRow.addStretch()
        self.cancelLinkButton = create_dialog_cancel_button(
            self.widget,
            text="Отмена",
            icon_name="fa5s.times",
            icon_color="#aaaaaa",
        )
        self.cancelLinkButton.clicked.connect(self.reject)
        self._cancelRow.addWidget(self.cancelLinkButton)
        self._cancelRow.addStretch()
        self.viewLayout.addLayout(self._cancelRow)

        # Скрываем дефолтные кнопки MessageBoxBase и убираем их пространство
        self.yesButton.hide()
        self.cancelButton.hide()
        self.buttonGroup.setFixedHeight(0)

        self.widget.setMinimumWidth(440)

    def _on_tray(self):
        self.result_tray = True
        self.accept()

    def _on_gui_only(self):
        self.result_stop_dpi = False
        self.accept()

    def _on_stop_dpi(self):
        self.result_stop_dpi = True
        self.accept()


def ask_close_action(parent=None):
    """
    Возвращает действие закрытия приложения:
      - None   -> пользователь отменил
      - "tray" -> свернуть в трей
      - False  -> закрыть только GUI
      - True   -> закрыть GUI + остановить DPI

    Если DPI-процесс не запущен, диалог не показывается и
    сразу возвращается False (закрыть только GUI).
    """
    is_dpi_running = True

    try:
        dpi_controller = getattr(parent, "dpi_controller", None)
        if dpi_controller and hasattr(dpi_controller, "is_running"):
            is_dpi_running = bool(dpi_controller.is_running())
    except Exception:
        pass

    if is_dpi_running and parent is not None:
        try:
            dpi_starter = getattr(parent, "dpi_starter", None)
            if dpi_starter and hasattr(dpi_starter, "check_process_running_wmi"):
                is_dpi_running = bool(dpi_starter.check_process_running_wmi(silent=True))
        except Exception:
            pass

    if not is_dpi_running:
        return False

    dlg = CloseDialog(parent)
    dlg.exec()
    if dlg.result_tray:
        return "tray"
    return dlg.result_stop_dpi
