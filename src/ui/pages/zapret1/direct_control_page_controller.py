from __future__ import annotations

from ui.control_page_controller import (
    ControlAutoDpiPlan,
    ControlPageController,
    ControlProgramSettingsPlan,
    ControlRuntimeState,
    ControlStatusPlan,
)
from ui.text_catalog import tr as tr_catalog


class DirectPresetNamePlan:
    def __init__(self, *, text: str, tooltip: str):
        self.text = text
        self.tooltip = tooltip


class Zapret1ActivationPlan:
    def __init__(self, *, sync_program_settings: bool, refresh_preset_name: bool):
        self.sync_program_settings = bool(sync_program_settings)
        self.refresh_preset_name = bool(refresh_preset_name)


class Zapret1UiStateChangePlan:
    def __init__(
        self,
        *,
        refresh_preset_name_now: bool,
        loading: bool,
        loading_text: str,
        update_status_state,
        update_status_error: str,
        strategy_summary: str,
    ):
        self.refresh_preset_name_now = bool(refresh_preset_name_now)
        self.loading = bool(loading)
        self.loading_text = loading_text
        self.update_status_state = update_status_state
        self.update_status_error = update_status_error
        self.strategy_summary = strategy_summary


class Zapret1StrategyUpdatePlan:
    def __init__(self, *, refresh_preset_name: bool, strategy_name: str):
        self.refresh_preset_name = bool(refresh_preset_name)
        self.strategy_name = strategy_name


class Zapret1OptimisticStartupPlan:
    def __init__(self, *, should_mark_running: bool, preset_name_text: str, preset_name_tooltip: str):
        self.should_mark_running = bool(should_mark_running)
        self.preset_name_text = preset_name_text
        self.preset_name_tooltip = preset_name_tooltip


class Zapret1DirectControlPageController(ControlPageController):
    @staticmethod
    def build_activation_plan() -> Zapret1ActivationPlan:
        return Zapret1ActivationPlan(
            sync_program_settings=True,
            refresh_preset_name=True,
        )

    @staticmethod
    def load_program_settings() -> ControlProgramSettingsPlan:
        auto_dpi_enabled = False
        try:
            from config import get_dpi_autostart

            auto_dpi_enabled = bool(get_dpi_autostart())
        except Exception:
            pass

        return ControlProgramSettingsPlan(
            auto_dpi_enabled=auto_dpi_enabled,
            defender_disabled=False,
            max_blocked=False,
        )

    @staticmethod
    def save_auto_dpi(enabled: bool) -> ControlAutoDpiPlan:
        return ControlPageController.save_auto_dpi(enabled)

    @staticmethod
    def resolve_runtime_state(*, snapshot_state=None, last_known_dpi_running: bool = False) -> ControlRuntimeState:
        return ControlPageController.resolve_runtime_state(
            snapshot_state=snapshot_state,
            last_known_dpi_running=last_known_dpi_running,
        )

    def build_status_plan(self, *, state: str | bool, last_error: str, language: str) -> ControlStatusPlan:
        phase = str(state or "").strip().lower()
        if phase not in {"autostart_pending", "starting", "running", "stopping", "failed", "stopped"}:
            phase = "running" if bool(state) else "stopped"

        if phase == "running":
            return ControlStatusPlan(
                phase=phase,
                title=tr_catalog("page.z1_control.status.running", language=language, default="Zapret 1 работает"),
                description=tr_catalog("page.z1_control.status.bypass_active", language=language, default="Обход блокировок активен"),
                dot_color="#6ccb5f",
                pulsing=True,
                show_start=False,
                show_stop_only=True,
                show_stop_and_exit=True,
            )
        if phase == "autostart_pending":
            return ControlStatusPlan(
                phase=phase,
                title="Автозапуск Zapret 1 запланирован",
                description="Подготавливаем стартовый запуск выбранного пресета",
                dot_color="#f5a623",
                pulsing=True,
                show_start=False,
                show_stop_only=False,
                show_stop_and_exit=False,
            )
        if phase == "starting":
            return ControlStatusPlan(
                phase=phase,
                title="Zapret 1 запускается",
                description="Ждём подтверждение процесса winws.exe",
                dot_color="#f5a623",
                pulsing=True,
                show_start=False,
                show_stop_only=False,
                show_stop_and_exit=False,
            )
        if phase == "stopping":
            return ControlStatusPlan(
                phase=phase,
                title="Zapret 1 останавливается",
                description="Завершаем winws.exe и освобождаем WinDivert",
                dot_color="#f5a623",
                pulsing=True,
                show_start=False,
                show_stop_only=False,
                show_stop_and_exit=False,
            )
        if phase == "failed":
            return ControlStatusPlan(
                phase=phase,
                title="Ошибка запуска Zapret 1",
                description=self.short_dpi_error(last_error) or "Процесс не подтвердился или завершился сразу",
                dot_color="#ff6b6b",
                pulsing=False,
                show_start=True,
                show_stop_only=False,
                show_stop_and_exit=False,
            )
        return ControlStatusPlan(
            phase="stopped",
            title=tr_catalog("page.z1_control.status.stopped", language=language, default="Zapret 1 остановлен"),
            description=tr_catalog("page.z1_control.status.press_start", language=language, default="Нажмите «Запустить» для активации"),
            dot_color="#ff6b6b",
            pulsing=False,
            show_start=True,
            show_stop_only=False,
            show_stop_and_exit=False,
        )

    @staticmethod
    def build_preset_name_plan(*, language: str) -> DirectPresetNamePlan:
        try:
            from core.services import get_direct_flow_coordinator

            preset = get_direct_flow_coordinator().get_selected_source_manifest("direct_zapret1")
            active_name = str(getattr(preset, "name", "") or "").strip()
            if active_name:
                return DirectPresetNamePlan(text=active_name, tooltip=active_name)
        except Exception:
            pass

        return DirectPresetNamePlan(
            text=tr_catalog("page.z1_control.preset.not_selected", language=language, default="Не выбран"),
            tooltip="",
        )

    @staticmethod
    def build_optimistic_startup_plan(*, language: str) -> Zapret1OptimisticStartupPlan:
        try:
            from strategy_menu import get_strategy_launch_method

            method = str(get_strategy_launch_method() or "").strip().lower()
        except Exception:
            method = ""

        preset_plan = Zapret1DirectControlPageController.build_preset_name_plan(language=language)
        return Zapret1OptimisticStartupPlan(
            should_mark_running=(method == "direct_zapret1"),
            preset_name_text=preset_plan.text,
            preset_name_tooltip=preset_plan.tooltip,
        )

    @staticmethod
    def prewarm_direct_payload() -> None:
        try:
            from core.presets.direct_facade import DirectPresetFacade

            DirectPresetFacade.from_launch_method("direct_zapret1").get_basic_ui_payload()
        except Exception:
            pass

    @staticmethod
    def build_ui_state_change_plan(*, state, changed_fields: frozenset[str], page_visible: bool) -> Zapret1UiStateChangePlan:
        changed = set(changed_fields or ())
        refresh_preset_name_now = bool("active_preset_revision" in changed and page_visible)
        return Zapret1UiStateChangePlan(
            refresh_preset_name_now=refresh_preset_name_now,
            loading=bool(state.dpi_busy),
            loading_text=str(state.dpi_busy_text or ""),
            update_status_state=state.dpi_phase or ("running" if state.dpi_running else "stopped"),
            update_status_error=str(state.dpi_last_error or ""),
            strategy_summary=str(state.current_strategy_summary or ""),
        )

    @staticmethod
    def build_strategy_update_plan(*, name: str) -> Zapret1StrategyUpdatePlan:
        return Zapret1StrategyUpdatePlan(
            refresh_preset_name=True,
            strategy_name=str(name or ""),
        )
