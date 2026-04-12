"""Status card for Premium page."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy


class StatusCard(QFrame):
    """Full-width subscription status card."""

    _STATUS_CONFIG = {
        'active':  {'bg': '#1c2e24', 'fg': '#7ecb9a', 'icon': '✓'},
        'warning': {'bg': '#2a2516', 'fg': '#c8a96e', 'icon': '⚠'},
        'expired': {'bg': '#2a1e1e', 'fg': '#c98080', 'icon': '✕'},
        'neutral': {'bg': '#1a2030', 'fg': '#7aa8d4', 'icon': 'ℹ'},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(52)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(10)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedWidth(22)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title_lbl = QLabel()
        self._detail_lbl = QLabel()

        row.addWidget(self._icon_lbl)
        row.addWidget(self._title_lbl)
        row.addSpacing(8)
        row.addWidget(self._detail_lbl)
        row.addStretch(1)

        self.set_status("", "", "neutral")

    def set_status(self, text: str, details: str = "", status: str = "neutral"):
        cfg = self._STATUS_CONFIG.get(status, self._STATUS_CONFIG['neutral'])

        self._icon_lbl.setText(cfg['icon'])
        self._icon_lbl.setStyleSheet(
            f"color: {cfg['fg']}; font-size: 15px; font-weight: bold; background: transparent;"
        )

        self._title_lbl.setText(text)
        self._title_lbl.setStyleSheet(
            f"color: {cfg['fg']}; font-weight: 600; font-size: 13px; background: transparent;"
        )

        self._detail_lbl.setText(details)
        self._detail_lbl.setStyleSheet(
            "color: rgba(255,255,255,180); font-size: 13px; background: transparent;"
        )
        self._detail_lbl.setVisible(bool(details))

        self.setStyleSheet(f"""
            StatusCard {{
                background-color: {cfg['bg']};
                border: none;
                border-radius: 8px;
            }}
        """)
