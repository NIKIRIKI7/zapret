"""Компоненты страницы диагностики соединений."""

from __future__ import annotations

from qfluentwidgets import CaptionLabel, TextEdit

from ui.smooth_scroll import apply_editor_smooth_scroll_preference


class ScrollBlockingConnectionTextEdit(TextEdit):
    """TextEdit, который не прокручивает родительскую страницу колесом мыши."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("noDrag", True)
        apply_editor_smooth_scroll_preference(self)

    def wheelEvent(self, event):
        scrollbar = self.verticalScrollBar()
        delta = event.angleDelta().y()
        if delta > 0 and scrollbar.value() == scrollbar.minimum():
            event.accept()
            return
        if delta < 0 and scrollbar.value() == scrollbar.maximum():
            event.accept()
            return
        super().wheelEvent(event)
        event.accept()


class ConnectionStatusBadge(CaptionLabel):
    """Небольшой статусный бейдж."""

    def __init__(self, text: str = "", status: str = "muted", parent=None):
        super().__init__(parent)
        self.setText(text)

    def set_status(self, text: str, status: str = "muted"):
        _ = status
        self.setText(text)
