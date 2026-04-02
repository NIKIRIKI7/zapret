from __future__ import annotations

from qfluentwidgets import MessageBoxBase, SubtitleLabel, BodyLabel


class StartStrategyWarningDialog(MessageBoxBase):
    """Фирменный диалог предупреждения о том, что стратегия не выбрана."""

    def __init__(self, parent=None, title: str = "Стратегия не выбрана", subtitle: str = ""):
        if parent and not parent.isWindow():
            parent = parent.window()
        super().__init__(parent)

        subtitle_text = subtitle or (
            "Для запуска Zapret выберите хотя бы одну стратегию "
            "в разделе «Стратегии»."
        )

        self.titleLabel = SubtitleLabel(title, self.widget)
        self.bodyLabel = BodyLabel(subtitle_text, self.widget)
        self.bodyLabel.setWordWrap(True)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.bodyLabel)

        self.yesButton.setText("Понятно")
        self.hideCancelButton()

        self.widget.setMinimumWidth(380)


def show_start_strategy_warning(parent=None, subtitle: str = "") -> None:
    """Показывает предупреждение о необходимости выбрать стратегию."""
    dlg = StartStrategyWarningDialog(parent=parent, subtitle=subtitle)
    dlg.exec()
