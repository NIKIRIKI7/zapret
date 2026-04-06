"""Orchestra Zapret2 user presets page."""

from __future__ import annotations

from pathlib import Path

from log import log
from ui.pages import user_presets_runtime as shared_runtime
from ui.pages.zapret2.user_presets_page import (
    BaseZapret2UserPresetsPage,
    InfoBar,
    MessageBox,
    _CreatePresetDialog,
    _RenamePresetDialog,
    _ResetAllPresetsDialog,
)


class OrchestraZapret2UserPresetsPage(BaseZapret2UserPresetsPage):
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
        from preset_orchestra_zapret2.preset_store import get_preset_store

        return get_preset_store()

    def _get_orchestra_manager(self):
        backend = "preset_orchestra_zapret2"
        if self._manager is None or self._manager_backend != backend:
            from preset_orchestra_zapret2 import PresetManager

            self._manager = PresetManager()
            self._manager_backend = backend
        return self._manager

    def _list_preset_entries_light(self) -> list[dict[str, object]]:
        try:
            manager = self._get_orchestra_manager()
            return [
                {
                    "file_name": f"{name}.txt",
                    "display_name": name,
                    "kind": "user",
                    "is_builtin": False,
                }
                for name in manager.list_presets()
            ]
        except Exception:
            return []

    def _get_active_preset_name_light(self) -> str:
        try:
            from preset_orchestra_zapret2 import get_active_preset_name

            return str(get_active_preset_name() or "").strip()
        except Exception:
            return ""

    def _get_selected_source_preset_file_name_light(self) -> str:
        active_name = self._get_active_preset_name_light()
        return f"{active_name}.txt" if active_name else ""

    def _get_presets_dir_light(self):
        from preset_orchestra_zapret2 import get_presets_dir

        return get_presets_dir()

    def _resolve_display_name(self, reference: str) -> str:
        candidate = str(reference or "").strip()
        if not candidate:
            return ""
        if candidate.lower().endswith(".txt"):
            return Path(candidate).stem
        return candidate

    def _is_builtin_preset_file(self, name: str) -> bool:
        _ = name
        return False

    def _hierarchy_scope_key(self) -> str:
        return "preset_orchestra_zapret2"

    def _rebuild_presets_rows(self, all_presets: dict[str, dict[str, object]], *, started_at: float | None = None) -> None:
        super()._rebuild_presets_rows(all_presets, started_at=started_at)
        try:
            from preset_orchestra_zapret2.preset_defaults import get_deleted_preset_names

            self._restore_deleted_btn.setVisible(bool(get_deleted_preset_names()))
        except Exception:
            self._restore_deleted_btn.setVisible(False)

    def _on_create_clicked(self):
        self._show_inline_action_create()

    def _show_inline_action_create(self):
        dlg = _CreatePresetDialog([], self.window(), language=self._ui_language)
        if not dlg.exec():
            return

        name = dlg.nameEdit.text().strip()
        from_current = getattr(dlg, "_source", "current") == "current"

        try:
            manager = self._get_orchestra_manager()
            preset = manager.create_preset(name, from_current=from_current)
            if not preset:
                InfoBar.error(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=self._tr("page.z2_user_presets.error.create_failed", "Не удалось создать пресет."),
                    parent=self.window(),
                )
                return
            shared_runtime.mark_presets_structure_changed(self)
            log(f"Создан пресет '{name}'", "INFO")
        except Exception as e:
            log(f"Ошибка создания пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z2_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _show_inline_action_rename(self, current_name: str):
        display_name = self._resolve_display_name(current_name)
        dlg = _RenamePresetDialog(display_name, [], self.window(), language=self._ui_language)
        if not dlg.exec():
            return

        new_name = dlg.nameEdit.text().strip()
        if not new_name or new_name == display_name:
            return

        try:
            manager = self._get_orchestra_manager()
            if not manager.rename_preset_by_file_name(current_name, new_name):
                InfoBar.error(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=self._tr("page.z2_user_presets.error.rename_failed", "Не удалось переименовать пресет."),
                    parent=self.window(),
                )
                return
            self._get_hierarchy_store().rename_preset_meta(
                current_name,
                new_name,
                old_display_name=display_name,
                new_display_name=new_name,
            )
            shared_runtime.mark_presets_structure_changed(self)
            log(f"Пресет '{display_name}' переименован в '{new_name}'", "INFO")
        except Exception as e:
            log(f"Ошибка переименования пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z2_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_import_clicked(self):
        file_path, _ = self._open_import_dialog()
        if not file_path:
            return
        try:
            name = str(Path(file_path).stem or "").strip() or "Imported"
            manager = self._get_orchestra_manager()
            if manager.import_preset(Path(file_path), name):
                try:
                    self._get_hierarchy_store().delete_preset_meta(name, display_name=name)
                except Exception:
                    pass
                shared_runtime.mark_presets_structure_changed(self)
                log(f"Импортирован пресет '{name}'", "INFO")
                self._show_import_result_infobar(name, name, f"{name}.txt")
            else:
                InfoBar.warning(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=self._tr("page.z2_user_presets.error.import_failed", "Не удалось импортировать пресет"),
                    parent=self.window(),
                )
        except Exception as e:
            log(f"Ошибка импорта пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z2_user_presets.error.import_exception", "Ошибка импорта: {error}", error=e),
                parent=self.window(),
            )

    def _open_import_dialog(self):
        from PyQt6.QtWidgets import QFileDialog

        return QFileDialog.getOpenFileName(
            self,
            self._tr("page.z2_user_presets.file_dialog.import_title", "Импортировать пресет"),
            "",
            "Preset files (*.txt);;All files (*.*)",
        )

    def _on_reset_all_presets_clicked(self):
        dlg = _ResetAllPresetsDialog(self.window(), language=self._ui_language)
        if not dlg.exec():
            return

        self._bulk_reset_running = True
        try:
            manager = self._get_orchestra_manager()
            success_count, total, failed = manager.reset_all_presets_to_default_templates()
            shared_runtime.mark_presets_structure_changed(self)
            if failed:
                log(
                    f"Восстановление заводских пресетов завершено частично: "
                    f"успешно={success_count}/{total}, ошибки={len(failed)}",
                    "WARNING",
                )
            else:
                log(f"Восстановлены заводские пресеты: {success_count}/{total}", "INFO")
            self._show_reset_all_result(success_count, total)
        except Exception as e:
            log(f"Ошибка массового восстановления пресетов: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr(
                    "page.z2_user_presets.error.reset_all_exception",
                    "Ошибка восстановления пресетов: {error}",
                    error=e,
                ),
                parent=self.window(),
            )
        finally:
            self._bulk_reset_running = False
            if self._ui_dirty and self.isVisible():
                self.refresh_presets_view_if_possible()

    def _on_activate_preset(self, name: str):
        try:
            manager = self._get_orchestra_manager()
            activated = bool(manager.switch_preset_by_file_name(name, reload_dpi=False))
            if activated:
                display_name = self._resolve_display_name(name)
                log(f"Активирован пресет '{display_name}'", "INFO")
                self._apply_active_preset_marker()
            else:
                InfoBar.warning(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=self._tr(
                        "page.z2_user_presets.error.activate_failed",
                        "Не удалось активировать пресет '{name}'",
                        name=name,
                    ),
                    parent=self.window(),
                )
        except Exception as e:
            log(f"Ошибка активации пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z2_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_duplicate_preset(self, name: str):
        try:
            display_name = self._resolve_display_name(name)
            new_name = f"{display_name} (копия)"
            manager = self._get_orchestra_manager()
            if manager.duplicate_preset_by_file_name(name, new_name):
                try:
                    self._get_hierarchy_store().copy_preset_meta_to_new(
                        name,
                        new_name,
                        source_display_name=display_name,
                        new_display_name=new_name,
                    )
                except Exception:
                    pass
                shared_runtime.mark_presets_structure_changed(self)
                log(f"Пресет '{name}' дублирован как '{new_name}'", "INFO")
            else:
                InfoBar.warning(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=self._tr("page.z2_user_presets.error.duplicate_failed", "Не удалось дублировать пресет"),
                    parent=self.window(),
                )
        except Exception as e:
            log(f"Ошибка дублирования пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z2_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_reset_preset(self, name: str):
        try:
            display_name = self._resolve_display_name(name)
            if MessageBox:
                box = MessageBox(
                    self._tr("page.z2_user_presets.dialog.reset_single.title", "Сбросить пресет?"),
                    self._tr(
                        "page.z2_user_presets.dialog.reset_single.body",
                        "Пресет '{name}' будет перезаписан данными из шаблона.\n"
                        "Все изменения в этом пресете будут потеряны.\n"
                        "Этот пресет станет активным и будет применен заново.",
                        name=display_name,
                    ),
                    self.window(),
                )
                box.yesButton.setText(
                    self._tr("page.z2_user_presets.dialog.reset_single.button", "Сбросить")
                )
                box.cancelButton.setText(
                    self._tr("page.z2_user_presets.dialog.button.cancel", "Отмена")
                )
                if not box.exec():
                    return

            manager = self._get_orchestra_manager()
            if not manager.reset_preset_to_default_template_by_file_name(name):
                InfoBar.warning(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=self._tr(
                        "page.z2_user_presets.error.reset_failed",
                        "Не удалось сбросить пресет к настройкам шаблона",
                    ),
                    parent=self.window(),
                )
                return
            log(f"Сброшен пресет '{display_name}' к шаблону", "INFO")
        except Exception as e:
            log(f"Ошибка сброса пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z2_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_delete_preset(self, name: str):
        try:
            display_name = self._resolve_display_name(name)
            if MessageBox:
                box = MessageBox(
                    self._tr("page.z2_user_presets.dialog.delete_single.title", "Удалить пресет?"),
                    self._tr(
                        "page.z2_user_presets.dialog.delete_single.body",
                        "Пресет '{name}' будет удален из списка пользовательских пресетов.\n"
                        "Изменения в этом пресете будут потеряны.\n"
                        "Вернуть его можно только через восстановление удаленных пресетов (если доступен шаблон).",
                        name=display_name,
                    ),
                    self.window(),
                )
                box.yesButton.setText(
                    self._tr("page.z2_user_presets.dialog.delete_single.button", "Удалить")
                )
                box.cancelButton.setText(
                    self._tr("page.z2_user_presets.dialog.button.cancel", "Отмена")
                )
                if not box.exec():
                    return

            deleted = False
            manager = self._get_orchestra_manager()
            if manager.delete_preset_by_file_name(name):
                try:
                    self._get_hierarchy_store().delete_preset_meta(name, display_name=display_name)
                except Exception:
                    pass
                shared_runtime.mark_presets_structure_changed(self)
                deleted = True

            if deleted:
                log(f"Удалён пресет '{display_name}'", "INFO")
            else:
                InfoBar.warning(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=self._tr("page.z2_user_presets.error.delete_failed", "Не удалось удалить пресет"),
                    parent=self.window(),
                )
        except Exception as e:
            log(f"Ошибка удаления пресета: {e}", "ERROR")
            if "Preset not found" in str(e):
                try:
                    self._get_hierarchy_store().delete_preset_meta(name, display_name=self._resolve_display_name(name))
                except Exception:
                    pass
                normalized_name = str(name or "").strip()
                if normalized_name:
                    self._cached_presets_metadata.pop(normalized_name, None)
                    if not normalized_name.lower().endswith(".txt"):
                        self._cached_presets_metadata.pop(f"{normalized_name}.txt", None)
                if self.isVisible() and self._cached_presets_metadata:
                    self._ui_dirty = False
                    self._refresh_presets_view_from_cache()
                else:
                    self._ui_dirty = True
                    if self.isVisible():
                        self._load_presets()
                return
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z2_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _on_export_preset(self, name: str):
        display_name = self._resolve_display_name(name)
        file_path, _ = self._open_export_dialog(display_name)
        if not file_path:
            return
        try:
            manager = self._get_orchestra_manager()
            if manager.export_preset_by_file_name(name, Path(file_path)):
                log(f"Экспортирован пресет '{display_name}' в {file_path}", "INFO")
                InfoBar.success(
                    title=self._tr("page.z2_user_presets.infobar.success", "Успех"),
                    content=self._tr(
                        "page.z2_user_presets.info.exported",
                        "Пресет экспортирован: {path}",
                        path=file_path,
                    ),
                    parent=self.window(),
                )
            else:
                InfoBar.warning(
                    title=self._tr("common.error.title", "Ошибка"),
                    content=self._tr("page.z2_user_presets.error.export_failed", "Не удалось экспортировать пресет"),
                    parent=self.window(),
                )
        except Exception as e:
            log(f"Ошибка экспорта пресета: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr("page.z2_user_presets.error.generic", "Ошибка: {error}", error=e),
                parent=self.window(),
            )

    def _open_export_dialog(self, display_name: str):
        from PyQt6.QtWidgets import QFileDialog

        return QFileDialog.getSaveFileName(
            self,
            self._tr("page.z2_user_presets.file_dialog.export_title", "Экспортировать пресет"),
            f"{display_name}.txt",
            "Preset files (*.txt);;All files (*.*)",
        )

    def _on_restore_deleted(self):
        try:
            from preset_orchestra_zapret2.preset_defaults import (
                clear_all_deleted_presets,
                ensure_templates_copied_to_presets,
            )

            clear_all_deleted_presets()
            ensure_templates_copied_to_presets()
            shared_runtime.mark_presets_structure_changed(self)
            log("Восстановлены удалённые пресеты", "INFO")
        except Exception as e:
            log(f"Ошибка восстановления удалённых пресетов: {e}", "ERROR")
            InfoBar.error(
                title=self._tr("common.error.title", "Ошибка"),
                content=self._tr(
                    "page.z2_user_presets.error.restore_deleted",
                    "Ошибка восстановления: {error}",
                    error=e,
                ),
                parent=self.window(),
            )
