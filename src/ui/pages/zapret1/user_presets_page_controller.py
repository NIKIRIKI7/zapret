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


class Zapret1UserPresetsPageController:
    LAUNCH_METHOD = "direct_zapret1"
    SELECTION_KEY = "winws1"
    HIERARCHY_SCOPE = "preset_zapret1"

    @classmethod
    def _get_direct_facade(cls):
        from core.presets.direct_facade import DirectPresetFacade

        return DirectPresetFacade.from_launch_method(cls.LAUNCH_METHOD)

    @staticmethod
    def get_preset_store():
        from core.services import get_preset_store_v1

        return get_preset_store_v1()

    def create_preset(self, *, name: str, from_current: bool) -> UserPresetActionResult:
        facade = self._get_direct_facade()
        facade.create(name, from_current=from_current)
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
        facade = self._get_direct_facade()
        updated = facade.rename_by_file_name(current_name, new_name)
        switched_file_name = updated.file_name if facade.is_selected_file_name(updated.file_name) else None
        if switched_file_name:
            from core.presets.direct_runtime_events import notify_direct_preset_switched

            notify_direct_preset_switched(self.LAUNCH_METHOD, switched_file_name)

        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message=f"Пресет '{current_name}' переименован в '{new_name}'",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
            structure_changed=True,
            switched_file_name=switched_file_name,
        )

    def import_preset_from_file(self, *, file_path: str) -> UserPresetImportResult:
        requested_name = str(Path(file_path).stem or "").strip() or "Imported"
        facade = self._get_direct_facade()
        imported = facade.import_from_file(Path(file_path), requested_name)
        actual_name = imported.name
        actual_file_name = imported.file_name

        expected_file_name = f"{requested_name}.txt" if requested_name else ""
        file_name_changed = bool(
            actual_file_name and expected_file_name and actual_file_name.casefold() != expected_file_name.casefold()
        )
        content = (
            "Пресет импортирован.\n"
            f"Отображаемое имя: {actual_name}\n"
            f"Имя файла: {actual_file_name}"
        )

        return UserPresetImportResult(
            ok=True,
            actual_name=actual_name,
            actual_file_name=actual_file_name,
            requested_name=requested_name,
            log_level="INFO",
            log_message=f"Импортирован пресет '{actual_name}'",
            infobar_level="warning" if file_name_changed else "success",
            infobar_title="Импортирован с новым именем файла" if file_name_changed else "Пресет импортирован",
            infobar_content=content,
            structure_changed=True,
        )

    def reset_all_presets(self) -> UserPresetResetAllResult:
        facade = self._get_direct_facade()
        success_count, total, failed = facade.reset_all_to_templates()
        selected_file_name = facade.get_selected_file_name()
        if selected_file_name:
            from core.presets.direct_runtime_events import notify_direct_preset_switched

            notify_direct_preset_switched(self.LAUNCH_METHOD, selected_file_name)

        failed_count = len(failed or [])
        if failed_count:
            log_message = (
                f"Восстановление заводских пресетов завершено частично: "
                f"успешно={success_count}/{total}, ошибки={failed_count}"
            )
            level = "WARNING"
        else:
            log_message = f"Восстановлены заводские пресеты: {success_count}/{total}"
            level = "INFO"

        return UserPresetResetAllResult(
            ok=True,
            success_count=int(success_count or 0),
            total_count=int(total or 0),
            failed_count=failed_count,
            log_level=level,
            log_message=log_message,
            structure_changed=True,
            switched_file_name=selected_file_name,
        )

    def duplicate_preset(self, *, file_name: str, display_name: str) -> UserPresetActionResult:
        new_name = f"{display_name} (копия)"
        facade = self._get_direct_facade()
        facade.duplicate_by_file_name(file_name, new_name)
        try:
            self.get_hierarchy_store().copy_preset_meta_to_new(file_name, new_name, source_display_name=display_name)
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
        facade = self._get_direct_facade()
        facade.reset_to_template_by_file_name(file_name)
        from core.presets.direct_runtime_events import notify_direct_preset_saved, notify_direct_preset_switched

        notify_direct_preset_saved(self.LAUNCH_METHOD, file_name)
        if facade.is_selected_file_name(file_name):
            notify_direct_preset_switched(self.LAUNCH_METHOD, file_name)

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
        if self.is_builtin_preset_file(file_name):
            return UserPresetActionResult(
                ok=False,
                log_level="WARNING",
                log_message="Встроенные пресеты удалять нельзя",
                infobar_level="warning",
                infobar_title="Ошибка",
                infobar_content="Встроенные пресеты удалять нельзя. Можно удалить только пользовательские пресеты.",
                structure_changed=False,
            )

        facade = self._get_direct_facade()
        facade.delete_by_file_name(file_name)
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
        facade = self._get_direct_facade()
        facade.export_plain_text_by_file_name(file_name, Path(file_path))
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
        facade = self._get_direct_facade()
        facade.restore_deleted()
        selected_file_name = facade.get_selected_file_name()
        if selected_file_name:
            from core.presets.direct_runtime_events import notify_direct_preset_switched

            notify_direct_preset_switched(self.LAUNCH_METHOD, selected_file_name)

        return UserPresetActionResult(
            ok=True,
            log_level="INFO",
            log_message="Восстановлены удалённые пресеты",
            infobar_level=None,
            infobar_title="",
            infobar_content="",
            structure_changed=True,
            switched_file_name=selected_file_name,
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

    def is_builtin_preset_file(self, name: str) -> bool:
        candidate = str(name or "").strip()
        if not candidate or not candidate.lower().endswith(".txt"):
            return False
        facade = self._get_direct_facade()
        try:
            manifest = facade.get_manifest_by_file_name(candidate)
            if manifest is not None:
                return str(manifest.kind or "").strip().lower() == "builtin"
        except Exception:
            pass
        return False

    def list_preset_entries_light(self) -> list[dict[str, object]]:
        try:
            facade = self._get_direct_facade()
            return [
                {
                    "file_name": item.file_name,
                    "display_name": item.name,
                    "kind": item.kind,
                    "is_builtin": str(item.kind or "").strip().lower() == "builtin",
                }
                for item in facade.list_manifests()
            ]
        except Exception as e:
            log(f"Z1UserPresetsPage: не удалось загрузить lightweight список пресетов: {e}", "ERROR")
            return []

    @classmethod
    def get_active_preset_name_light(cls) -> str:
        try:
            from core.services import get_direct_flow_coordinator

            preset = get_direct_flow_coordinator().get_selected_source_manifest(cls.LAUNCH_METHOD)
            return str(preset.name if preset is not None else "").strip()
        except Exception:
            return ""

    @classmethod
    def get_selected_source_preset_file_name_light(cls) -> str:
        try:
            from core.services import get_selection_service

            return str(get_selection_service().get_selected_file_name(cls.SELECTION_KEY) or "").strip()
        except Exception:
            return ""

    @classmethod
    def get_presets_dir_light(cls):
        from core.services import get_app_paths

        return get_app_paths().engine_paths(cls.SELECTION_KEY).ensure_directories().presets_dir

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

    def resolve_display_name(self, reference: str) -> str:
        candidate = str(reference or "").strip()
        if not candidate:
            return ""
        if candidate.lower().endswith(".txt"):
            facade = self._get_direct_facade()
            try:
                manifest = facade.get_manifest_by_file_name(candidate)
                if manifest is not None:
                    return manifest.name
            except Exception:
                pass
        return candidate

    def get_hierarchy_store(self):
        from core.presets.library_hierarchy import PresetHierarchyStore

        return PresetHierarchyStore(self.HIERARCHY_SCOPE)

    def is_builtin_preset_file_with_cache(self, name: str, cached_metadata: dict[str, dict[str, object]] | None) -> bool:
        candidate = str(name or "").strip()
        if not candidate or not candidate.lower().endswith(".txt"):
            return False

        if isinstance(cached_metadata, dict):
            cached_meta = cached_metadata.get(candidate)
            if isinstance(cached_meta, dict):
                return bool(cached_meta.get("is_builtin", False))

        return self.is_builtin_preset_file(candidate)

    def toggle_preset_pin(self, name: str, display_name: str) -> bool:
        hierarchy = self.get_hierarchy_store()
        return bool(hierarchy.toggle_preset_pin(name, display_name=display_name))

    def move_preset_by_step(self, name: str, direction: int, *, cached_metadata: dict[str, dict[str, object]] | None = None) -> bool:
        hierarchy = self.get_hierarchy_store()
        return bool(
            hierarchy.move_preset_by_step_flat(
                self.list_preset_entries_light(),
                name,
                direction,
                is_builtin_resolver=lambda file_name: self.is_builtin_preset_file_with_cache(str(file_name or ""), cached_metadata),
            )
        )

    def move_preset_on_drop(
        self,
        *,
        source_kind: str,
        source_id: str,
        target_kind: str,
        target_id: str,
        cached_metadata: dict[str, dict[str, object]] | None = None,
    ) -> bool:
        if source_kind != "preset":
            return False

        hierarchy = self.get_hierarchy_store()
        all_names = self.list_preset_entries_light()

        if target_kind == "preset" and target_id:
            return bool(
                hierarchy.move_preset_before_flat(
                    all_names,
                    source_id,
                    target_id,
                    is_builtin_resolver=lambda file_name: self.is_builtin_preset_file_with_cache(str(file_name or ""), cached_metadata),
                )
            )

        return bool(
            hierarchy.move_preset_to_end_flat(
                all_names,
                source_id,
                is_builtin_resolver=lambda file_name: self.is_builtin_preset_file_with_cache(str(file_name or ""), cached_metadata),
            )
        )

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
            is_builtin = builtin_by_file.get(file_name, False)
            meta = hierarchy.get_preset_meta(file_name, display_name=display_name)
            rows.append(
                {
                    "kind": "preset",
                    "name": display_name,
                    "file_name": file_name,
                    "description": str(preset.get("description") or ""),
                    "date": str(preset.get("modified_display") or ""),
                    "is_active": bool(file_name and file_name == str(active_file_name or "").strip()),
                    "is_builtin": is_builtin,
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
                            "page.z1_user_presets.empty.not_found",
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
                            "page.z1_user_presets.empty.none",
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

    def activate_preset(self, *, file_name: str, display_name: str) -> UserPresetActivationResult:
        target_file_name = str(file_name or "").strip()
        target_display_name = str(display_name or target_file_name).strip() or target_file_name

        try:
            from core.presets.direct_runtime_events import activate_direct_preset_file

            activate_direct_preset_file(self.LAUNCH_METHOD, target_file_name)
            return UserPresetActivationResult(
                ok=True,
                log_level="INFO",
                log_message=f"Активирован пресет '{target_display_name}'",
                infobar_level=None,
                infobar_title="",
                infobar_content="",
                activated_file_name=target_file_name,
            )
        except Exception as e:
            return UserPresetActivationResult(
                ok=False,
                log_level="ERROR",
                log_message=f"Ошибка активации пресета: {e}",
                infobar_level="warning",
                infobar_title="Ошибка",
                infobar_content=f"Не удалось активировать пресет '{target_display_name}'",
                activated_file_name=None,
            )
