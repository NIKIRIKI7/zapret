from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from pathlib import Path

from log import log


@dataclass(slots=True)
class UserPresetActionResult:
    ok: bool
    log_level: str
    log_message: str
    infobar_level: str | None
    infobar_title: str
    infobar_content: str
    structure_changed: bool
    switched_file_name: str | None = None
    error_code: str | None = None


@dataclass(slots=True)
class UserPresetImportResult:
    ok: bool
    actual_name: str
    actual_file_name: str
    requested_name: str
    log_level: str
    log_message: str
    infobar_level: str
    infobar_title: str
    infobar_content: str
    structure_changed: bool


@dataclass(slots=True)
class UserPresetResetAllResult:
    ok: bool
    success_count: int
    total_count: int
    failed_count: int
    log_level: str
    log_message: str
    structure_changed: bool
    switched_file_name: str | None


@dataclass(slots=True)
class UserPresetListPlan:
    rows: list[dict[str, object]]
    total_presets: int
    visible_presets: int
    query: str


@dataclass(slots=True)
class UserPresetActivationResult:
    ok: bool
    log_level: str
    log_message: str
    infobar_level: str | None
    infobar_title: str
    infobar_content: str
    activated_file_name: str | None


class OrchestraZapret2UserPresetsPageController:
    LAUNCH_METHOD = "direct_zapret2_orchestra"
    HIERARCHY_SCOPE = "preset_orchestra_zapret2"

    def __init__(self) -> None:
        self._manager = None
        self._manager_backend = ""

    @staticmethod
    def _get_direct_facade():
        raise RuntimeError("Direct facade недоступен для orchestra preset backend")

    @staticmethod
    def get_preset_store():
        from preset_orchestra_zapret2.preset_store import get_preset_store

        return get_preset_store()

    def get_orchestra_manager(self):
        backend = "preset_orchestra_zapret2"
        if self._manager is None or self._manager_backend != backend:
            from preset_orchestra_zapret2 import PresetManager

            self._manager = PresetManager()
            self._manager_backend = backend
        return self._manager

    def list_preset_entries_light(self) -> list[dict[str, object]]:
        try:
            manager = self.get_orchestra_manager()
            return [
                {
                    "file_name": f"{name}.txt",
                    "display_name": name,
                    "kind": "user",
                    "is_builtin": False,
                }
                for name in manager.list_presets()
            ]
        except Exception as e:
            log(f"OrchestraZapret2UserPresetsPage: не удалось загрузить lightweight список пресетов: {e}", "ERROR")
            return []

    @staticmethod
    def get_active_preset_name_light() -> str:
        try:
            from preset_orchestra_zapret2 import get_active_preset_name

            return str(get_active_preset_name() or "").strip()
        except Exception:
            return ""

    @classmethod
    def get_selected_source_preset_file_name_light(cls) -> str:
        active_name = cls.get_active_preset_name_light()
        return f"{active_name}.txt" if active_name else ""

    @staticmethod
    def get_presets_dir_light():
        from preset_orchestra_zapret2 import get_presets_dir

        return get_presets_dir()

    @staticmethod
    def resolve_display_name(reference: str) -> str:
        candidate = str(reference or "").strip()
        if not candidate:
            return ""
        if candidate.lower().endswith(".txt"):
            return Path(candidate).stem
        return candidate

    @staticmethod
    def is_builtin_preset_file(_name: str) -> bool:
        return False

    @staticmethod
    def is_builtin_preset_file_with_cache(_name: str, _cached_metadata: dict[str, dict[str, object]] | None) -> bool:
        return False

    def get_hierarchy_store(self):
        from core.presets.library_hierarchy import PresetHierarchyStore

        return PresetHierarchyStore(self.HIERARCHY_SCOPE)

    @staticmethod
    def has_deleted_presets() -> bool:
        try:
            from preset_orchestra_zapret2.preset_defaults import get_deleted_preset_names

            return bool(get_deleted_preset_names())
        except Exception:
            return False

    def load_preset_list_metadata_light(self) -> dict[str, dict[str, object]]:
        from core.presets.list_metadata import read_preset_list_metadata

        metadata: dict[str, dict[str, object]] = {}
        presets_dir = self.get_presets_dir_light()

        for entry in self.list_preset_entries_light():
            file_name = str(entry.get("file_name") or "").strip()
            display_name = str(entry.get("display_name") or file_name).strip()
            kind = str(entry.get("kind") or "").strip() or "user"
            is_builtin = bool(entry.get("is_builtin", False))
            if not file_name:
                continue
            try:
                path = presets_dir / file_name
                metadata[file_name] = {
                    **read_preset_list_metadata(path),
                    "display_name": display_name,
                    "kind": kind,
                    "is_builtin": is_builtin,
                }
            except Exception:
                metadata[file_name] = {
                    "description": "",
                    "modified_display": "",
                    "icon_color": "",
                    "display_name": display_name,
                    "kind": kind,
                    "is_builtin": is_builtin,
                }

        return metadata

    def read_single_preset_list_metadata_light(self, file_name_or_name: str) -> tuple[str, dict[str, object]] | None:
        from core.presets.list_metadata import read_preset_list_metadata

        candidate = str(file_name_or_name or "").strip()
        if not candidate:
            return None

        candidate_file_name = candidate if candidate.lower().endswith(".txt") else f"{candidate}.txt"
        matched_entry = None
        for entry in self.list_preset_entries_light():
            entry_file_name = str(entry.get("file_name") or "").strip()
            entry_display_name = str(entry.get("display_name") or entry_file_name).strip()
            if entry_file_name == candidate_file_name or entry_display_name == candidate:
                matched_entry = entry
                candidate_file_name = entry_file_name or candidate_file_name
                break

        if matched_entry is None:
            return None

        display_name = str(matched_entry.get("display_name") or candidate_file_name).strip()
        kind = str(matched_entry.get("kind") or "").strip() or "user"
        is_builtin = bool(matched_entry.get("is_builtin", False))
        path = self.get_presets_dir_light() / candidate_file_name

        try:
            metadata = {
                **read_preset_list_metadata(path),
                "display_name": display_name,
                "kind": kind,
                "is_builtin": is_builtin,
            }
        except Exception:
            metadata = {
                "description": "",
                "modified_display": "",
                "icon_color": "",
                "display_name": display_name,
                "kind": kind,
                "is_builtin": is_builtin,
            }

        return candidate_file_name, metadata

    def toggle_preset_pin(self, name: str, display_name: str) -> bool:
        hierarchy = self.get_hierarchy_store()
        return bool(hierarchy.toggle_preset_pin(name, display_name=display_name))

    def move_preset_by_step(self, name: str, direction: int, *, cached_metadata: dict[str, dict[str, object]] | None = None) -> bool:
        _ = cached_metadata
        hierarchy = self.get_hierarchy_store()
        return bool(hierarchy.move_preset_by_step_flat(self.list_preset_entries_light(), name, direction, is_builtin_resolver=lambda _file_name: False))

    def move_preset_on_drop(
        self,
        *,
        source_kind: str,
        source_id: str,
        target_kind: str,
        target_id: str,
        cached_metadata: dict[str, dict[str, object]] | None = None,
    ) -> bool:
        _ = cached_metadata
        if source_kind != "preset":
            return False

        hierarchy = self.get_hierarchy_store()
        all_names = self.list_preset_entries_light()

        if target_kind == "preset" and target_id:
            return bool(hierarchy.move_preset_before_flat(all_names, source_id, target_id, is_builtin_resolver=lambda _file_name: False))

        return bool(hierarchy.move_preset_to_end_flat(all_names, source_id, is_builtin_resolver=lambda _file_name: False))

    def build_preset_rows_plan(
        self,
        *,
        all_presets: dict[str, dict[str, object]],
        query: str,
        active_file_name: str,
        language: str,
    ) -> UserPresetListPlan:
        from ui.pages.user_presets_runtime_controller import normalize_preset_icon_color
        from ui.text_catalog import tr as tr_catalog

        normalized_query = str(query or "").strip().lower()
        hierarchy = self.get_hierarchy_store()
        builtin_by_file = {
            file_name: bool(meta.get("is_builtin", False))
            for file_name, meta in all_presets.items()
        }

        rows: list[dict[str, object]] = []
        visible_entries: list[dict[str, object]] = []

        for file_name, meta in all_presets.items():
            display_name = str(meta.get("display_name") or file_name).strip()
            if normalized_query and normalized_query not in display_name.lower():
                continue
            visible_entries.append(
                {
                    "file_name": file_name,
                    "display_name": display_name,
                    "is_builtin": builtin_by_file.get(file_name, False),
                }
            )

        ordered_names = hierarchy.list_presets_flat(
            visible_entries,
            is_builtin_resolver=lambda file_name: builtin_by_file.get(str(file_name or ""), False),
        )

        for file_name in ordered_names:
            preset = all_presets.get(file_name)
            if not preset:
                continue
            display_name = str(preset.get("display_name") or file_name).strip()
            meta = hierarchy.get_preset_meta(file_name, display_name=display_name)
            rows.append(
                {
                    "kind": "preset",
                    "name": display_name,
                    "file_name": file_name,
                    "description": str(preset.get("description") or ""),
                    "date": str(preset.get("modified_display") or ""),
                    "is_active": bool(file_name and file_name == str(active_file_name or "").strip()),
                    "is_builtin": False,
                    "icon_color": normalize_preset_icon_color(str(preset.get("icon_color") or "")),
                    "depth": 0,
                    "is_pinned": bool(meta.get("pinned", False)),
                    "rating": int(meta.get("rating", 0) or 0),
                }
            )

        if not rows:
            if normalized_query:
                rows.append(
                    {
                        "kind": "empty",
                        "text": tr_catalog(
                            "page.z2_user_presets.empty.not_found",
                            language=language,
                            default="Ничего не найдено.",
                        ),
                    }
                )
            else:
                rows.append(
                    {
                        "kind": "empty",
                        "text": tr_catalog(
                            "page.z2_user_presets.empty.none",
                            language=language,
                            default="Нет пресетов. Создайте новый или импортируйте из файла.",
                        ),
                    }
                )

        return UserPresetListPlan(
            rows=rows,
            total_presets=len(all_presets),
            visible_presets=len(visible_entries),
            query=normalized_query,
        )

    def create_preset(self, *, name: str, from_current: bool) -> UserPresetActionResult:
        manager = self.get_orchestra_manager()
        preset = manager.create_preset(name, from_current=from_current)
        if not preset:
            raise RuntimeError("Не удалось создать пресет.")
        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Создан пресет '{name}'",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
            structure_changed=True,
        )

    def rename_preset(self, *, current_name: str, new_name: str) -> UserPresetActionResult:
        display_name = self.resolve_display_name(current_name)
        manager = self.get_orchestra_manager()
        if not manager.rename_preset_by_file_name(current_name, new_name):
            raise RuntimeError("Не удалось переименовать пресет.")
        self.get_hierarchy_store().rename_preset_meta(
            current_name,
            new_name,
            old_display_name=display_name,
            new_display_name=new_name,
        )
        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Пресет '{display_name}' переименован в '{new_name}'",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
            structure_changed=True,
        )

    def import_preset_from_file(self, *, file_path: str) -> UserPresetImportResult:
        requested_name = str(Path(file_path).stem or "").strip() or "Imported"
        manager = self.get_orchestra_manager()
        if not manager.import_preset(Path(file_path), requested_name):
            raise RuntimeError("Не удалось импортировать пресет")
        try:
            self.get_hierarchy_store().delete_preset_meta(requested_name, display_name=requested_name)
        except Exception:
            pass
        actual_file_name = f"{requested_name}.txt"
        return UserPresetImportResult(
            ok=True,
            actual_name=requested_name,
            actual_file_name=actual_file_name,
            requested_name=requested_name,
            log_level="INFO",
            log_message=f"Импортирован пресет '{requested_name}'",
            infobar_level="success",
            infobar_title="Пресет импортирован",
            infobar_content=(
                "Пресет импортирован.\n"
                f"Отображаемое имя: {requested_name}\n"
                f"Имя файла: {actual_file_name}"
            ),
            structure_changed=True,
        )

    def reset_all_presets(self) -> UserPresetResetAllResult:
        manager = self.get_orchestra_manager()
        success_count, total_count, failed = manager.reset_all_presets_to_default_templates()
        failed_count = len(failed or [])
        if failed_count:
            log_message = (
                f"Восстановление заводских пресетов завершено частично: "
                f"успешно={success_count}/{total_count}, ошибки={failed_count}"
            )
            level = "WARNING"
        else:
            log_message = f"Восстановлены заводские пресеты: {success_count}/{total_count}"
            level = "INFO"
        return UserPresetResetAllResult(
            ok=True,
            success_count=int(success_count or 0),
            total_count=int(total_count or 0),
            failed_count=failed_count,
            log_level=level,
            log_message=log_message,
            structure_changed=True,
            switched_file_name=None,
        )

    def activate_preset(self, *, file_name: str, display_name: str) -> UserPresetActivationResult:
        target_file_name = str(file_name or "").strip()
        target_display_name = str(display_name or target_file_name).strip() or target_file_name
        try:
            manager = self.get_orchestra_manager()
            activated = bool(manager.switch_preset_by_file_name(target_file_name, reload_dpi=False))
            if activated:
                return UserPresetActivationResult(
                    ok=True,
                    log_level="INFO",
                    log_message=f"Активирован пресет '{target_display_name}'",
                    infobar_level=None,
                    infobar_title="",
                    infobar_content="",
                    activated_file_name=target_file_name,
                )
            return UserPresetActivationResult(
                ok=False,
                log_level="ERROR",
                log_message=f"Не удалось активировать пресет '{target_display_name}'",
                infobar_level="error",
                infobar_title="Ошибка",
                infobar_content=f"Не удалось активировать пресет '{target_display_name}'",
                activated_file_name=None,
            )
        except Exception as e:
            return UserPresetActivationResult(
                ok=False,
                log_level="ERROR",
                log_message=f"Ошибка активации пресета: {e}",
                infobar_level="error",
                infobar_title="Ошибка",
                infobar_content=f"Ошибка: {e}",
                activated_file_name=None,
            )

    def duplicate_preset(self, *, file_name: str, display_name: str) -> UserPresetActionResult:
        new_name = f"{display_name} (копия)"
        manager = self.get_orchestra_manager()
        if not manager.duplicate_preset_by_file_name(file_name, new_name):
            raise RuntimeError("Не удалось дублировать пресет")
        try:
            self.get_hierarchy_store().copy_preset_meta_to_new(
                file_name,
                new_name,
                source_display_name=display_name,
                new_display_name=new_name,
            )
        except Exception:
            pass
        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Пресет '{display_name}' дублирован как '{new_name}'",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
            structure_changed=True,
        )

    def reset_preset_to_template(self, *, file_name: str, display_name: str) -> UserPresetActionResult:
        manager = self.get_orchestra_manager()
        if not manager.reset_preset_to_default_template_by_file_name(file_name):
            raise RuntimeError("Не удалось сбросить пресет к настройкам шаблона")
        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Сброшен пресет '{display_name}' к шаблону",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
            structure_changed=False,
        )

    def delete_preset(self, *, file_name: str, display_name: str) -> UserPresetActionResult:
        manager = self.get_orchestra_manager()
        deleted = manager.delete_preset_by_file_name(file_name)
        if not deleted:
            raise RuntimeError("Не удалось удалить пресет")
        try:
            self.get_hierarchy_store().delete_preset_meta(file_name, display_name=display_name)
        except Exception:
            pass
        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Удалён пресет '{display_name}'",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
            structure_changed=True,
        )

    def export_preset(self, *, file_name: str, file_path: str, display_name: str) -> UserPresetActionResult:
        manager = self.get_orchestra_manager()
        if not manager.export_preset_by_file_name(file_name, Path(file_path)):
            raise RuntimeError("Не удалось экспортировать пресет")
        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Экспортирован пресет '{display_name}' в {file_path}",
            infobar_level="success",
            infobar_title="Успех",
            infobar_content=f"Пресет экспортирован: {file_path}",
            structure_changed=False,
        )

    def restore_deleted_presets(self) -> UserPresetActionResult:
        from preset_orchestra_zapret2.preset_defaults import clear_all_deleted_presets, ensure_templates_copied_to_presets

        clear_all_deleted_presets()
        ensure_templates_copied_to_presets()
        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message="Восстановлены удалённые пресеты",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
            structure_changed=True,
        )

    @staticmethod
    def open_presets_info() -> UserPresetActionResult:
        try:
            from config.urls import PRESET_INFO_URL

            webbrowser.open(PRESET_INFO_URL)
            return UserPresetActionResult(
                ok=True,
                log_level="INFO",
                log_message=f"Открыта страница о пресетах: {PRESET_INFO_URL}",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
                structure_changed=False,
            )
        except Exception as e:
            return UserPresetActionResult(
                ok=False,
                log_level="ERROR",
                log_message=f"Не удалось открыть страницу о пресетах: {e}",
                infobar_level="warning",
                infobar_title="Ошибка",
                infobar_content=f"Не удалось открыть страницу о пресетах: {e}",
                structure_changed=False,
            )

    @staticmethod
    def open_new_configs_post() -> UserPresetActionResult:
        try:
            from core.direct_flow import DirectFlowCoordinator

            webbrowser.open(DirectFlowCoordinator.PRESETS_DOWNLOAD_URL)
            return UserPresetActionResult(
                ok=True,
                log_level="INFO",
                log_message=f"Открыта страница пресетов: {DirectFlowCoordinator.PRESETS_DOWNLOAD_URL}",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
                structure_changed=False,
            )
        except Exception as e:
            return UserPresetActionResult(
                ok=False,
                log_level="ERROR",
                log_message=f"Ошибка открытия страницы пресетов: {e}",
                infobar_level="warning",
                infobar_title="Ошибка",
                infobar_content=f"Не удалось открыть страницу пресетов: {e}",
                structure_changed=False,
            )
