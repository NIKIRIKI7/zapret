"""Orchestra Zapret2 user presets page."""

from __future__ import annotations

from ui.pages.zapret2.user_presets_page import BaseZapret2UserPresetsPage

from .user_presets_page_controller import OrchestraZapret2UserPresetsPageController


class OrchestraZapret2UserPresetsPage(BaseZapret2UserPresetsPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._controller = OrchestraZapret2UserPresetsPageController()

    def _current_breadcrumb_title(self) -> str:
        return self._tr("page.z2_user_presets.title.orchestra", "Мои пресеты (Оркестратор Z2)")

    def _apply_mode_labels(self) -> None:
        try:
            self.title_label.setText(
                self._tr("page.z2_user_presets.title.orchestra", "Мои пресеты (Оркестратор Z2)")
            )
            if self.subtitle_label is not None:
                self.subtitle_label.setText(
                    self._tr(
                        "page.z2_user_presets.subtitle.orchestra",
                        "Управление пресетами для режима direct_zapret2_orchestra",
                    )
                )
            self._rebuild_breadcrumb()
        except Exception:
            pass

    def _get_preset_store(self):
        return self._controller.get_preset_store()

    def _rebuild_presets_rows(self, all_presets: dict[str, dict[str, object]], *, started_at: float | None = None) -> None:
        super()._rebuild_presets_rows(all_presets, started_at=started_at)
        self._restore_deleted_btn.setVisible(self._controller.has_deleted_presets())
