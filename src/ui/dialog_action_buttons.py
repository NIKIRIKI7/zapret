from __future__ import annotations

from PyQt6.QtGui import QIcon

try:
    import qtawesome as qta

    _HAS_QTA = True
except ImportError:
    qta = None
    _HAS_QTA = False

from qfluentwidgets import PushButton, TransparentPushButton


_DANGER_BUTTON_QSS = (
    "QPushButton{background-color:#c42b1c;color:white;border:none;border-radius:5px;}"
    "QPushButton:hover{background-color:#a52014;}"
    "QPushButton:pressed{background-color:#8e1a10;}"
)


def _resolve_icon(icon_name: str | None, color: str | None) -> QIcon:
    if not _HAS_QTA or not icon_name:
        return QIcon()

    try:
        return qta.icon(icon_name, color=color)
    except Exception:
        return QIcon()


def _configure_button_icon(button, icon_name: str | None, icon_color: str | None) -> None:
    try:
        button.setIcon(_resolve_icon(icon_name, icon_color))
    except Exception:
        pass


def create_dialog_action_button(
    parent,
    *,
    text: str,
    icon_name: str | None = None,
    icon_color: str | None = None,
    danger: bool = False,
) -> PushButton:
    """Создаёт обычную fluent-кнопку действия для диалога."""

    button = PushButton(parent)
    button.setText(text)
    button.setMinimumHeight(36)
    _configure_button_icon(button, icon_name, icon_color)

    if danger:
        try:
            button.setStyleSheet(_DANGER_BUTTON_QSS)
        except Exception:
            pass

    return button


def create_dialog_cancel_button(
    parent,
    *,
    text: str,
    icon_name: str | None = None,
    icon_color: str | None = None,
) -> TransparentPushButton:
    """Создаёт прозрачную fluent-кнопку отмены."""

    button = TransparentPushButton(parent)
    button.setText(text)
    _configure_button_icon(button, icon_name, icon_color)
    return button
