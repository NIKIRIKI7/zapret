from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ui.pages.preset_subpage_base import PresetSubpageBase, _RenameDialog

try:
    from qfluentwidgets import MessageBox
except ImportError:
    MessageBox = None


class OrchestraPresetSubpageBase(PresetSubpageBase):
    def _breadcrumb_parent_text(self) -> str:
        return "Пресеты Оркестра"

    def _is_current_builtin(self) -> bool:
        return False

    def _save_file(self) -> None:
        if self._preset_path is None:
            return
        try:
            from preset_orchestra_zapret2 import (
                _atomic_write_text,
                get_active_preset_name,
                get_active_preset_path,
                set_active_preset_name,
            )

            preset_name = str(self._preset_name or "").strip() or Path(str(self._preset_file_name or "").strip()).stem
            if not preset_name:
                raise ValueError("Preset name is required for orchestra preset saving")

            source_text = self.editor.toPlainText()
            _atomic_write_text(self._preset_path, source_text)

            active_name = str(get_active_preset_name() or "").strip()
            if active_name.lower() == preset_name.lower():
                set_active_preset_name(preset_name)
                _atomic_write_text(get_active_preset_path(), source_text)
                self._notify_preset_switched()

            self._notify_preset_saved(f"{preset_name}.txt")
            self._set_footer(f"Сохранено {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            self._set_footer(f"Ошибка сохранения: {e}")
            self._show_error(str(e))

    def _rename_preset(self) -> None:
        if self._is_current_builtin():
            self._show_error("Встроенный пресет нельзя переименовать. Создайте копию и работайте уже с ней.")
            return
        self._flush_pending_save()
        dialog = _RenameDialog(self._preset_name, [], self.window())
        if not dialog.exec():
            return
        new_name = dialog.nameEdit.text().strip()
        if not new_name or new_name == self._preset_name:
            return
        try:
            from preset_orchestra_zapret2 import get_active_preset_name, rename_preset

            old_name = str(self._preset_name or "").strip() or Path(str(self._preset_file_name or "").strip()).stem
            if not old_name:
                raise ValueError("Preset name is required for orchestra preset rename")
            if not rename_preset(old_name, new_name):
                raise ValueError("Не удалось переименовать orchestra preset")
            self._notify_preset_structure_changed()
            self.set_preset_file_name(f"{new_name}.txt")
            active_name = str(get_active_preset_name() or "").strip()
            if active_name.lower() == new_name.lower():
                self._notify_preset_switched()
            self._show_success(f"Пресет переименован: {new_name}")
        except Exception as e:
            self._show_error(str(e))

    def _duplicate_preset(self) -> None:
        self._flush_pending_save()
        try:
            from preset_orchestra_zapret2 import duplicate_preset

            preset_name = str(self._preset_name or "").strip() or Path(str(self._preset_file_name or "").strip()).stem
            if not preset_name:
                raise ValueError("Preset name is required for orchestra preset duplicate")
            new_name = f"{self._preset_name} (копия)"
            if not duplicate_preset(preset_name, new_name):
                raise ValueError("Не удалось создать копию orchestra preset")
            self._notify_preset_structure_changed()
            self.set_preset_file_name(f"{new_name}.txt")
            self._show_success(f"Создан дубликат: {new_name}")
        except Exception as e:
            self._show_error(str(e))

    def _export_preset(self) -> None:
        self._flush_pending_save()
        file_path, _ = self._get_export_path()
        if not file_path:
            return
        try:
            from preset_orchestra_zapret2 import export_preset

            preset_name = str(self._preset_name or "").strip() or Path(str(self._preset_file_name or "").strip()).stem
            if not preset_name:
                raise ValueError("Preset name is required for orchestra preset export")
            if not export_preset(preset_name, Path(file_path)):
                raise ValueError("Не удалось экспортировать orchestra preset")
            self._show_success(f"Пресет экспортирован: {file_path}")
        except Exception as e:
            self._show_error(str(e))

    def _get_export_path(self) -> tuple[str, str]:
        from PyQt6.QtWidgets import QFileDialog

        return QFileDialog.getSaveFileName(
            self,
            "Экспортировать пресет",
            f"{self._preset_name}.txt",
            "Preset files (*.txt);;All files (*.*)",
        )

    def _reset_preset(self) -> None:
        self._flush_pending_save()
        if MessageBox is not None:
            box = MessageBox(
                "Сбросить пресет?",
                f"Пресет «{self._preset_name}» будет перезаписан данными из шаблона.",
                self.window(),
            )
            box.yesButton.setText("Сбросить")
            box.cancelButton.setText("Отмена")
            if not box.exec():
                return
        try:
            from preset_orchestra_zapret2 import PresetManager, get_active_preset_name

            preset_name = str(self._preset_name or "").strip() or Path(str(self._preset_file_name or "").strip()).stem
            if not preset_name:
                raise ValueError("Preset name is required for orchestra preset reset")
            is_active = str(get_active_preset_name() or "").strip().lower() == preset_name.lower()
            manager = PresetManager()
            if not manager.reset_preset_to_default_template(
                preset_name,
                make_active=is_active,
                sync_active_file=is_active,
                emit_switched=is_active,
            ):
                raise ValueError("Не удалось сбросить orchestra preset")
            self.set_preset_file_name(f"{preset_name}.txt")
            self._notify_preset_saved(f"{preset_name}.txt")
            self._show_success(f"Пресет «{self._preset_name}» сброшен")
        except Exception as e:
            self._show_error(str(e))

    def _delete_preset(self) -> None:
        if self._is_current_builtin():
            self._show_error("Встроенный пресет нельзя удалить.")
            return
        self._flush_pending_save()
        if MessageBox is not None:
            box = MessageBox(
                "Удалить пресет?",
                f"Пресет «{self._preset_name}» будет удалён.",
                self.window(),
            )
            box.yesButton.setText("Удалить")
            box.cancelButton.setText("Отмена")
            if not box.exec():
                return
        try:
            from preset_orchestra_zapret2 import delete_preset

            preset_name = str(self._preset_name or "").strip() or Path(str(self._preset_file_name or "").strip()).stem
            if not preset_name:
                raise ValueError("Preset name is required for orchestra preset delete")
            if not delete_preset(preset_name):
                raise ValueError("Не удалось удалить orchestra preset")
            self._notify_preset_structure_changed()
            self.back_clicked.emit()
            self._show_success(f"Пресет «{self._preset_name}» удалён")
        except Exception as e:
            self._show_error(str(e))

    def _current_selected_name(self) -> str:
        try:
            from preset_orchestra_zapret2 import get_active_preset_name

            return str(get_active_preset_name() or "").strip()
        except Exception:
            return ""

    def _current_selected_file_name(self) -> str:
        active_name = self._current_selected_name()
        return f"{active_name}.txt" if active_name else ""

    def _activate_selected_preset(self) -> bool:
        try:
            from preset_orchestra_zapret2 import PresetManager

            preset_name = str(self._preset_name or "").strip() or Path(str(self._preset_file_name or "").strip()).stem
            if not preset_name:
                return False
            return bool(PresetManager().switch_preset(preset_name, reload_dpi=False))
        except Exception:
            return False

    def _notify_preset_switched(self) -> None:
        try:
            from preset_orchestra_zapret2 import get_preset_store

            preset_name = str(self._preset_name or "").strip() or Path(str(self._preset_file_name or "").strip()).stem
            if preset_name:
                get_preset_store().notify_preset_switched(preset_name)
        except Exception:
            pass

    def _notify_preset_saved(self, file_name: str) -> None:
        try:
            from preset_orchestra_zapret2 import get_preset_store

            _ = file_name
            preset_name = str(self._preset_name or "").strip() or Path(str(self._preset_file_name or "").strip()).stem
            if preset_name:
                get_preset_store().notify_preset_saved(preset_name)
        except Exception:
            pass
