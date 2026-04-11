from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget

from app_context import AppContext, build_app_context
from config import APP_VERSION, HEIGHT, MIN_WIDTH, WIDTH
from core.services import install_app_context
from log import global_logger, log
from main.runtime_state import (
    log_startup_metric as emit_startup_metric,
    startup_elapsed_ms,
)
from ui.fluent_app_window import ZapretFluentWindow
from ui.holiday_effects import HolidayEffectsManager
from ui.main_window import MainWindowUI
from ui.main_window_state import AppUiState
from ui.page_names import PageName
from ui.theme_subscription_manager import ThemeSubscriptionManager
from ui.window_close_controller import WindowCloseController
from ui.window_geometry_controller import WindowGeometryController
from ui.window_notification_controller import WindowNotificationController
from utils import run_hidden

if TYPE_CHECKING:
    from managers.dpi_manager import DPIManager
    from managers.initialization_manager import InitializationManager
    from managers.process_monitor_manager import ProcessMonitorManager
    from managers.subscription_manager import SubscriptionManager
    from managers.ui_manager import UIManager

class LupiDPIApp(ZapretFluentWindow, MainWindowUI, ThemeSubscriptionManager):
    """Главное окно приложения — FluentWindow + навигация + подписки."""

    deferred_init_requested = pyqtSignal()
    continue_startup_requested = pyqtSignal()
    finalize_ui_bootstrap_requested = pyqtSignal()
    startup_interactive_ready = pyqtSignal(str)
    startup_post_init_ready = pyqtSignal(str)
    runner_runtime_state_requested = pyqtSignal(object)
    active_preset_content_changed_requested = pyqtSignal(str)

    from ui.theme import ThemeHandler
    # ✅ ДОБАВЛЯЕМ TYPE HINTS для менеджеров
    ui_manager: 'UIManager'
    dpi_manager: 'DPIManager'
    process_monitor_manager: 'ProcessMonitorManager'
    subscription_manager: 'SubscriptionManager'
    initialization_manager: 'InitializationManager'
    theme_handler: 'ThemeHandler'

    def log_startup_metric(self, marker: str, details: str = "") -> None:
        emit_startup_metric(marker, details)

    @staticmethod
    def _build_initial_ui_state() -> AppUiState:
        """Честное стартовое состояние UI до реальной проверки и автозапуска."""
        try:
            from config import get_dpi_autostart, get_winws_exe_for_method
            from strategy_menu import get_strategy_launch_method

            autostart_enabled = bool(get_dpi_autostart())
            launch_method = str(get_strategy_launch_method() or "").strip().lower()
            expected_process = ""
            if launch_method and launch_method != "orchestra":
                expected_process = os.path.basename(get_winws_exe_for_method(launch_method)).strip().lower()

            autostart_pending_methods = {
                "direct_zapret2",
                "direct_zapret1",
                "orchestra",
            }

            if autostart_enabled and launch_method in autostart_pending_methods:
                return AppUiState(
                    dpi_phase="autostart_pending",
                    dpi_running=False,
                    dpi_expected_process=expected_process,
                    autostart_enabled=autostart_enabled,
                )

            return AppUiState(
                dpi_phase="stopped",
                dpi_running=False,
                dpi_expected_process=expected_process,
                autostart_enabled=autostart_enabled,
            )
        except Exception:
            return AppUiState()

    def closeEvent(self, event):
        """Обрабатывает событие закрытия окна"""
        close_controller = getattr(self, "window_close_controller", None)
        if close_controller is not None:
            if not close_controller.should_continue_final_close(event):
                return

        self._is_exiting = True

        try:
            if hasattr(global_logger, "set_ui_error_notifier"):
                global_logger.set_ui_error_notifier(None)
        except Exception:
            pass
        
        # ✅ Гарантированно сохраняем геометрию/состояние окна при выходе
        try:
            geometry_controller = getattr(self, "window_geometry_controller", None)
            if geometry_controller is not None:
                geometry_controller.persist_now(force=True)
        except Exception as e:
            log(f"Ошибка сохранения геометрии окна при закрытии: {e}", "❌ ERROR")
        
        self._cleanup_support_managers_for_close()
        self._cleanup_threaded_pages_for_close()

        self._cleanup_visual_and_proxy_resources_for_close()
        self._cleanup_runtime_threads_for_close()

        # ✅ ВАЖНО: winws/winws2 не должны останавливаться при "Выход" из трея/меню.
        # Останавливаем процессы только если явно запрошен "Выход и остановить DPI".
        if getattr(self, "_stop_dpi_on_exit", False):
            try:
                from utils.process_killer import kill_winws_force
                kill_winws_force()
                log("Процессы winws завершены при закрытии приложения (stop_dpi_on_exit=True)", "DEBUG")
            except Exception as e:
                log(f"Ошибка остановки winws при закрытии: {e}", "DEBUG")
        else:
            log("Выход без остановки DPI: winws не трогаем", "DEBUG")

        self._cleanup_tray_for_close()

        super().closeEvent(event)

    def _release_input_interaction_states(self) -> None:
        """Сбрасывает drag/resize состояния при скрытии/потере фокуса окна."""
        try:
            if bool(getattr(self, "_is_resizing", False)) and hasattr(self, "_end_resize"):
                self._end_resize()
            else:
                self._is_resizing = False
                self._resize_edge = None
                self._resize_start_pos = None
                self._resize_start_geometry = None
                self.unsetCursor()
        except Exception:
            pass

        try:
            self._is_dragging = False
            self._drag_start_pos = None
            self._drag_window_pos = None
        except Exception:
            pass

        try:
            tb = getattr(self, "title_bar", None)
            if tb is not None:
                tb._is_moving = False
                tb._is_system_moving = False
                tb._drag_pos = None
                tb._window_pos = None
        except Exception:
            pass

    def request_exit(self, stop_dpi: bool) -> None:
        """Единая точка выхода из приложения.

        - stop_dpi=False: закрыть GUI, DPI оставить работать.
        - stop_dpi=True: остановить DPI и выйти (учитывает текущий launch_method).
        """
        from PyQt6.QtWidgets import QApplication

        self._stop_dpi_on_exit = bool(stop_dpi)

        self._closing_completely = True

        # Сохраняем геометрию/состояние окна сразу (без debounce).
        try:
            geometry_controller = getattr(self, "window_geometry_controller", None)
            if geometry_controller is not None:
                geometry_controller.persist_now(force=True)
        except Exception as e:
            log(f"Ошибка сохранения геометрии окна при request_exit: {e}", "DEBUG")

        # Скрываем иконку трея (если есть) — пользователь выбрал полный выход.
        try:
            if hasattr(self, "tray_manager") and self.tray_manager:
                self.tray_manager.hide_icon()
        except Exception:
            pass

        if stop_dpi:
            log("Запрошен выход: остановить DPI и выйти", "INFO")

            # Предпочтительно: асинхронная остановка + выход.
            try:
                if hasattr(self, "dpi_controller") and self.dpi_controller:
                    self.dpi_controller.stop_and_exit_async()
                    return
            except Exception as e:
                log(f"stop_and_exit_async не удалось: {e}", "WARNING")

            # Аварийный low-level fallback без старого stop-модуля.
            try:
                runtime = getattr(self, "dpi_runtime", None)
                if runtime is not None:
                    runtime.stop_all_processes()
                    runtime.cleanup_windivert_service()
            except Exception as e:
                log(f"Ошибка остановки DPI перед выходом: {e}", "WARNING")

        else:
            log("Запрошен выход: выйти без остановки DPI", "INFO")

        # Закрываем все окна — это вызовет closeEvent с полной очисткой
        # потоков, страниц и менеджеров (т.к. _closing_completely=True).
        # Без этого closeEvent не вызывается и cleanup не происходит → краш.
        QApplication.closeAllWindows()
        QApplication.processEvents()
        QApplication.quit()

    def ensure_tray_manager(self):
        """Возвращает tray manager, создавая его только как аварийный fallback."""
        tray_manager = getattr(self, "tray_manager", None)
        if tray_manager is not None:
            return tray_manager

        try:
            initialization_manager = getattr(self, "initialization_manager", None)
            if initialization_manager is not None:
                return initialization_manager.ensure_tray_initialized()
        except Exception as e:
            log(f"Не удалось инициализировать системный трей по требованию: {e}", "WARNING")

        return None

    def minimize_to_tray(self) -> bool:
        """Скрывает окно в трей (без выхода из GUI)."""
        try:
            tray_manager = self.ensure_tray_manager()
            if tray_manager is not None:
                return bool(tray_manager.hide_to_tray(show_hint=True))
        except Exception as e:
            log(f"Ошибка сценария сворачивания в трей: {e}", "WARNING")

        return False

    def set_status(self, text: str) -> None:
        """Sets the status text."""
        status_type = "neutral"
        lower_text = text.lower()
        if "работает" in lower_text or "запущен" in lower_text or "успешно" in lower_text:
            status_type = "running"
        elif "останов" in lower_text or "ошибка" in lower_text or "выключен" in lower_text:
            status_type = "stopped"
        elif "внимание" in lower_text or "предупреждение" in lower_text:
            status_type = "warning"

        store = getattr(self, "ui_state_store", None)
        if store is not None:
            store.set_status_message(text, status_type)


    def delayed_dpi_start(self) -> None:
        """Выполняет отложенный запуск DPI с проверкой наличия автозапуска"""
        if hasattr(self, 'dpi_manager'):
            self.dpi_manager.delayed_dpi_start()

    def on_strategy_selected_from_dialog(self, strategy_id: str, strategy_name: str) -> None:
        """Обрабатывает выбор стратегии из диалога."""
        try:
            log(f"Выбрана стратегия: {strategy_name} (ID: {strategy_id})", level="INFO")
            
            # ДЛЯ DIRECT РЕЖИМА ИСПОЛЬЗУЕМ ПРОСТОЕ НАЗВАНИЕ
            from strategy_menu import get_strategy_launch_method
            launch_method = get_strategy_launch_method()
            
            if launch_method == "direct_zapret2":
                # direct_zapret2 is preset-based; do not show a phantom single-strategy name.
                try:
                    preset = self.app_context.direct_flow_coordinator.get_selected_source_manifest("direct_zapret2")
                    preset_name = str(getattr(preset, "name", "") or "")
                    display_name = f"Пресет: {preset_name}"
                except Exception:
                    display_name = "Пресет"
                strategy_name = display_name
                log(f"Установлено имя пресета для direct_zapret2: {display_name}", "DEBUG")
            elif strategy_id == "DIRECT_MODE" or launch_method == "direct_zapret1":
                if launch_method == "direct_zapret1":
                    try:
                        preset = self.app_context.direct_flow_coordinator.get_selected_source_manifest("direct_zapret1")
                        preset_name = str(getattr(preset, "name", "") or "")
                        display_name = f"Пресет: {preset_name}"
                    except Exception:
                        display_name = "Пресет"
                else:
                    log(
                        f"Выбран неподдерживаемый direct-режим запуска: {launch_method}",
                        "ERROR",
                    )
                    self.set_status("Ошибка: выбран удалённый или неподдерживаемый режим запуска")
                    return
                strategy_name = display_name
                log(f"Установлено простое название для режима {launch_method}: {display_name}", "DEBUG")

            # Обновляем новые страницы интерфейса
            if hasattr(self, 'update_current_strategy_display'):
                self.update_current_strategy_display(strategy_name)

            # Все поддерживаемые DPI-режимы идут через единый controller pipeline.
            if launch_method in ("direct_zapret2", "direct_zapret1", "orchestra"):
                log(
                    f"Запуск {launch_method} передан в единый DPI controller pipeline",
                    "INFO",
                )
                self.dpi_controller.start_dpi_async(selected_mode=None, launch_method=launch_method)
            else:
                raise RuntimeError(f"Неподдерживаемый метод запуска: {launch_method}")
                
        except Exception as e:
            log(f"Ошибка при установке выбранной стратегии: {str(e)}", level="❌ ERROR")
            import traceback
            log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            self.set_status(f"Ошибка при установке стратегии: {str(e)}")

    def __init__(self, start_in_tray: bool = False, *, app_context: AppContext):
        # ZapretFluentWindow.__init__ handles: titlebar, icon, dark theme, min size
        super().__init__()

        from strategy_menu import get_strategy_launch_method
        current_method = get_strategy_launch_method()
        log(f"Метод запуска стратегий: {current_method}", "INFO")

        self.start_in_tray = start_in_tray
        self.app_context = app_context
        self.ui_state_store = app_context.ui_state_store
        self.app_runtime_state = app_context.app_runtime_state
        self.dpi_runtime_service = app_context.dpi_runtime_service

        # Flags
        self._dpi_autostart_initiated = False
        self._is_exiting = False
        self._stop_dpi_on_exit = False
        self._closing_completely = False
        self._deferred_init_started = False
        self._startup_post_init_ready = False
        self._startup_subscription_ready = False
        self._startup_background_init_started = False
        self._tray_launch_notification_pending = bool(self.start_in_tray)

        # FluentWindow handles: frameless, titlebar, acrylic, resize, drag
        # We only need to set title and restore geometry
        self.setWindowTitle(f"Zapret2 v{APP_VERSION}")
        self.setMinimumSize(MIN_WIDTH, 400)
        self.window_close_controller = WindowCloseController(self)
        self.window_geometry_controller = WindowGeometryController(
            self,
            min_width=MIN_WIDTH,
            min_height=400,
            default_width=WIDTH,
            default_height=HEIGHT,
        )
        self.window_notification_controller = WindowNotificationController(self)
        self.window_notification_controller.register_global_error_notifier()
        self.window_geometry_controller.restore_geometry()

        self._holiday_effects = HolidayEffectsManager(self)
        self._startup_ttff_logged = False
        self._startup_ttff_ms = None
        self._startup_interactive_logged = False
        self._startup_interactive_ms = None
        self._startup_managers_ready_logged = False
        self._startup_managers_ready_ms = None
        self._startup_post_init_done_logged = False
        self._startup_post_init_done_ms = None
        self._last_active_preset_content_path = ""
        self._last_active_preset_content_ms = 0
        self.deferred_init_requested.connect(self._deferred_init, Qt.ConnectionType.QueuedConnection)
        self.continue_startup_requested.connect(self._continue_deferred_init, Qt.ConnectionType.QueuedConnection)
        self.finalize_ui_bootstrap_requested.connect(self._finalize_ui_bootstrap, Qt.ConnectionType.QueuedConnection)
        self.runner_runtime_state_requested.connect(self._apply_runner_runtime_state_update, Qt.ConnectionType.QueuedConnection)
        self.active_preset_content_changed_requested.connect(self._apply_active_preset_content_changed, Qt.ConnectionType.QueuedConnection)

        # Show window right away (FluentWindow handles rendering)
        if not self.start_in_tray and not self.isVisible():
            self.show()
            log("Основное окно показано (FluentWindow, init в фоне)", "DEBUG")

        self.deferred_init_requested.emit()

    def _mark_startup_subscription_ready(self, source: str = "subscription_ready") -> None:
        self._startup_subscription_ready = True

    def _start_background_init(self) -> None:
        if self._startup_background_init_started:
            return
        self._startup_background_init_started = True

        try:
            subscription_manager = getattr(self, "subscription_manager", None)
            if subscription_manager is not None:
                subscription_manager.initialize_async()
        except Exception:
            pass

        notification_controller = getattr(self, "window_notification_controller", None)
        if notification_controller is not None:
            notification_controller.schedule_startup_notification_queue(0)

    def _deferred_init(self) -> None:
        """Heavy initialization — runs after first frame is shown."""
        if self._deferred_init_started:
            return
        self._deferred_init_started = True

        import time as _time
        _t_total = _time.perf_counter()
        log("⏱ Startup: deferred init started", "DEBUG")

        # Build UI: create the first visible pages and minimum navigation shell.
        # Всё, что не нужно для первого кадра и первого клика, переносим дальше.
        _t_build = _time.perf_counter()
        try:
            self.build_ui(WIDTH, HEIGHT)
        except Exception as e:
            log(f"Startup: build_ui failed: {e}", "ERROR")
            try:
                import traceback
                log(traceback.format_exc(), "DEBUG")
            except Exception:
                pass
            return
        log(f"⏱ Startup: build_ui {(_time.perf_counter() - _t_build) * 1000:.0f}ms", "DEBUG")
        log(f"⏱ Startup: deferred init total {( _time.perf_counter() - _t_total ) * 1000:.0f}ms", "DEBUG")
        self.continue_startup_requested.emit()

    def _continue_deferred_init(self) -> None:
        """Продолжает старт уже после показа базового UI.

        Этот этап не должен мешать первому визуальному отклику окна: сначала
        пользователь видит страницу и может начать взаимодействовать, а потом
        приложение спокойно поднимает менеджеры и фоновую инфраструктуру.
        """
        import time as _time
        _t_total = _time.perf_counter()

        _t_mgr = _time.perf_counter()
        manager_bootstrap(self)
        log(f"⏱ Startup: managers init {( _time.perf_counter() - _t_mgr ) * 1000:.0f}ms", "DEBUG")

        self.update_title_with_subscription_status(False, None, 0, source="init")

        # Стартовый порядок теперь управляется самим initialization_manager.
        self.initialization_manager.run_async_init()
        log(f"⏱ Startup: continue init total {( _time.perf_counter() - _t_total ) * 1000:.0f}ms", "DEBUG")

        # Тяжёлые глобальные связи окна дозаводим ещё одним отдельным проходом,
        # чтобы не склеивать их с первым построением интерфейса.
        self.finalize_ui_bootstrap_requested.emit()

    def _finalize_ui_bootstrap(self) -> None:
        """Завершает не критичную для первого кадра сборку главного окна."""
        try:
            self.finish_ui_bootstrap()
        except Exception as e:
            log(f"Startup: finish_ui_bootstrap failed: {e}", "DEBUG")

    def _apply_runner_runtime_state_update(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return

        runtime_service = getattr(self, "dpi_runtime_service", None)
        if runtime_service is None:
            return

        launch_method = str(payload.get("launch_method") or "").strip().lower()
        if launch_method not in {"direct_zapret1", "direct_zapret2"}:
            return

        snapshot = runtime_service.snapshot()
        current_method = str(snapshot.launch_method or "").strip().lower()
        if current_method and current_method != launch_method and snapshot.phase in {"starting", "running", "autostart_pending"}:
            return

        try:
            from config import get_winws_exe_for_method

            expected_process = os.path.basename(get_winws_exe_for_method(launch_method)).strip().lower()
        except Exception:
            expected_process = snapshot.expected_process

        preset_path = str(payload.get("preset_path") or "").strip()
        pid = payload.get("pid")
        error_text = str(payload.get("error") or "").strip()
        phase = str(payload.get("phase") or "").strip().lower()

        if phase == "starting":
            runtime_service.begin_start(
                launch_method=launch_method,
                expected_process=expected_process,
                expected_preset_path=preset_path,
            )
            return

        if phase == "running":
            runtime_service.mark_running(
                pid=pid if isinstance(pid, int) else None,
                expected_process=expected_process,
                expected_preset_path=preset_path or snapshot.expected_preset_path,
            )
            return

        if phase == "failed":
            runtime_service.mark_start_failed(
                error_text or "Запуск завершился ошибкой",
            )

    def _apply_active_preset_content_changed(self, path: str) -> None:
        normalized_path = os.path.normcase(str(path or "").strip())
        if not normalized_path:
            return

        now_ms = startup_elapsed_ms()
        if (
            normalized_path == str(getattr(self, "_last_active_preset_content_path", "") or "")
            and max(0, now_ms - int(getattr(self, "_last_active_preset_content_ms", 0) or 0)) < 500
        ):
            return

        self._last_active_preset_content_path = normalized_path
        self._last_active_preset_content_ms = now_ms

        store = getattr(self, "ui_state_store", None)
        if store is None:
            return
        try:
            store.bump_preset_content_revision()
        except Exception:
            pass

    def _mark_startup_interactive(self, source: str = "ui_signals_connected") -> None:
        if self._startup_interactive_logged:
            return

        self._startup_interactive_logged = True
        interactive_ms = startup_elapsed_ms()
        self._startup_interactive_ms = interactive_ms

        ttff_ms = self._startup_ttff_ms
        if isinstance(ttff_ms, int):
            delta_ms = max(0, interactive_ms - ttff_ms)
            emit_startup_metric("Interactive", f"{source}, +{delta_ms}ms after TTFF")
        else:
            emit_startup_metric("Interactive", source)
        try:
            self.startup_interactive_ready.emit(str(source or "interactive"))
        except Exception:
            pass

    def _mark_startup_managers_ready(self, source: str = "managers_init_done") -> None:
        if self._startup_managers_ready_logged:
            return

        self._startup_managers_ready_logged = True
        managers_ready_ms = startup_elapsed_ms()
        self._startup_managers_ready_ms = managers_ready_ms

        details = source
        interactive_ms = self._startup_interactive_ms
        if isinstance(interactive_ms, int):
            delta_ms = max(0, managers_ready_ms - interactive_ms)
            details = f"{source}, +{delta_ms}ms after Interactive"
        elif isinstance(self._startup_ttff_ms, int):
            delta_ms = max(0, managers_ready_ms - self._startup_ttff_ms)
            details = f"{source}, +{delta_ms}ms after TTFF"

        emit_startup_metric("CoreStartupReady", details)

    def _mark_startup_post_init_done(self, source: str = "post_init_tasks") -> None:
        if self._startup_post_init_done_logged:
            return

        self._startup_post_init_done_logged = True
        post_init_ms = startup_elapsed_ms()
        self._startup_post_init_done_ms = post_init_ms

        details = source
        managers_ready_ms = self._startup_managers_ready_ms
        if isinstance(managers_ready_ms, int):
            delta_ms = max(0, post_init_ms - managers_ready_ms)
            details = f"{source}, +{delta_ms}ms after CoreStartupReady"
        elif isinstance(self._startup_interactive_ms, int):
            delta_ms = max(0, post_init_ms - self._startup_interactive_ms)
            details = f"{source}, +{delta_ms}ms after Interactive"

        emit_startup_metric("PostInitDispatched", details)
        self._startup_post_init_ready = True
        try:
            self.startup_post_init_ready.emit(str(source or "post_init"))
        except Exception:
            pass
        self._start_background_init()
        notification_controller = getattr(self, "window_notification_controller", None)
        if notification_controller is not None:
            notification_controller.schedule_startup_notification_queue(0)

    def setWindowTitle(self, title: str):
        """Override to update FluentWindow's built-in titlebar."""
        super().setWindowTitle(title)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            try:
                if not self.isActiveWindow():
                    self._release_input_interaction_states()
            except Exception:
                pass

        if event.type() == QEvent.Type.WindowStateChange:
            geometry_controller = getattr(self, "window_geometry_controller", None)
            if geometry_controller is not None:
                geometry_controller.on_window_state_change()

            try:
                effects = getattr(self, "_holiday_effects", None)
                if effects is not None:
                    QTimer.singleShot(0, effects.sync_geometry)
            except Exception:
                pass

        super().changeEvent(event)

    def hideEvent(self, event):
        try:
            self._release_input_interaction_states()
        except Exception:
            pass
        super().hideEvent(event)

    def moveEvent(self, event):
        super().moveEvent(event)
        geometry_controller = getattr(self, "window_geometry_controller", None)
        if geometry_controller is not None:
            geometry_controller.on_geometry_changed()
    
    def _force_style_refresh(self) -> None:
        """Принудительно обновляет стили всех виджетов после показа окна
        
        Необходимо потому что CSS применяется к QApplication ДО создания/показа виджетов.
        unpolish/polish заставляет Qt пересчитать стили для каждого виджета.
        """
        try:
            # unpolish/polish принудительно пересчитывает стили виджета
            for widget in self.findChildren(QWidget):
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            
            log("🎨 Принудительное обновление стилей выполнено после показа окна", "DEBUG")
        except Exception as e:
            log(f"Ошибка обновления стилей: {e}", "DEBUG")

    def _cleanup_loaded_page(self, page_name: PageName) -> None:
        page = self.get_loaded_page(page_name)
        if page is None or not hasattr(page, "cleanup"):
            return
        try:
            page.cleanup()
        except Exception as e:
            log(f"Ошибка при очистке страницы {page_name}: {e}", "DEBUG")

    def _cleanup_threaded_pages_for_close(self) -> None:
        try:
            for page_name in (
                PageName.LOGS,
                PageName.SERVERS,
                PageName.BLOCKCHECK,
                PageName.HOSTS,
            ):
                self._cleanup_loaded_page(page_name)
        except Exception as e:
            log(f"Ошибка при очистке страниц: {e}", "DEBUG")

    def _cleanup_support_managers_for_close(self) -> None:
        try:
            process_monitor_manager = getattr(self, "process_monitor_manager", None)
            if process_monitor_manager is not None:
                process_monitor_manager.stop_monitoring()
        except Exception as e:
            log(f"Ошибка остановки process_monitor_manager: {e}", "DEBUG")

        try:
            dns_ui_manager = getattr(self, "dns_ui_manager", None)
            if dns_ui_manager is not None:
                dns_ui_manager.cleanup()
        except Exception as e:
            log(f"Ошибка при очистке dns_ui_manager: {e}", "DEBUG")

        try:
            theme_handler = getattr(self, "theme_handler", None)
            theme_manager = getattr(theme_handler, "theme_manager", None) if theme_handler is not None else None
            if theme_manager is not None:
                theme_manager.cleanup()
        except Exception as e:
            log(f"Ошибка при очистке theme_manager: {e}", "DEBUG")


    def _cleanup_visual_and_proxy_resources_for_close(self) -> None:
        try:
            from ui.pages.telegram_proxy_page import _get_proxy_manager

            _get_proxy_manager().cleanup()
        except Exception:
            pass

        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is not None:
                effects.cleanup()
                self._holiday_effects = None
        except Exception as e:
            log(f"Ошибка очистки праздничных эффектов: {e}", "DEBUG")

    def _cleanup_runtime_threads_for_close(self) -> None:
        try:
            dpi_controller = getattr(self, "dpi_controller", None)
            if dpi_controller is not None:
                dpi_controller.cleanup_threads()
        except Exception as e:
            log(f"Ошибка очистки DPI controller threads: {e}", "DEBUG")

        try:
            if hasattr(self, '_dpi_start_thread') and self._dpi_start_thread:
                try:
                    if self._dpi_start_thread.isRunning():
                        self._dpi_start_thread.quit()
                        self._dpi_start_thread.wait(1000)
                except RuntimeError:
                    pass

            if hasattr(self, '_dpi_stop_thread') and self._dpi_stop_thread:
                try:
                    if self._dpi_stop_thread.isRunning():
                        self._dpi_stop_thread.quit()
                        self._dpi_stop_thread.wait(1000)
                except RuntimeError:
                    pass
        except Exception as e:
            log(f"Ошибка при очистке потоков: {e}", "❌ ERROR")

    def _cleanup_tray_for_close(self) -> None:
        try:
            tray_manager = getattr(self, "tray_manager", None)
            if tray_manager is not None:
                tray_manager.cleanup()
                self.tray_manager = None
        except Exception as e:
            log(f"Ошибка очистки системного трея: {e}", "DEBUG")
    
    def show_subscription_dialog(self) -> None:
        """Переключается на страницу Premium."""
        try:
            self.show_page(PageName.PREMIUM)
        except Exception as e:
            log(f"Ошибка при переходе на страницу Premium: {e}", level="❌ ERROR")
            
    def open_folder(self) -> None:
        """Opens the DPI folder."""
        try:
            run_hidden('explorer.exe .', shell=True)
        except Exception as e:
            self.set_status(f"Ошибка при открытии папки: {str(e)}")

    def open_connection_test(self) -> None:
        """Переключает на вкладку диагностики соединений."""
        try:
            if self.show_page(PageName.BLOCKCHECK):
                self._route_search_result(PageName.BLOCKCHECK, "diagnostics")
                self._call_loaded_page_method(
                    PageName.BLOCKCHECK,
                    "request_diagnostics_start_focus",
                )
                log("Открыта вкладка диагностики в BlockCheck", "INFO")
        except Exception as e:
            log(f"Ошибка при открытии вкладки тестирования: {e}", "❌ ERROR")
            self.set_status(f"Ошибка: {e}")

    def set_garland_enabled(self, enabled: bool) -> None:
        """Enable/disable top garland overlay in FluentWindow shell."""
        try:
            store = getattr(self, "ui_state_store", None)
            if store is not None:
                snapshot = store.snapshot()
                store.set_holiday_overlays(bool(enabled), snapshot.snowflakes_enabled)

            effects = getattr(self, "_holiday_effects", None)
            if effects is None:
                effects = HolidayEffectsManager(self)
                self._holiday_effects = effects
            effects.set_garland_enabled(bool(enabled))
        except Exception as e:
            log(f"❌ Ошибка переключения гирлянды: {e}", "ERROR")

    def set_snowflakes_enabled(self, enabled: bool) -> None:
        """Enable/disable snow overlay in FluentWindow shell."""
        try:
            store = getattr(self, "ui_state_store", None)
            if store is not None:
                snapshot = store.snapshot()
                store.set_holiday_overlays(snapshot.garland_enabled, bool(enabled))

            effects = getattr(self, "_holiday_effects", None)
            if effects is None:
                effects = HolidayEffectsManager(self)
                self._holiday_effects = effects
            effects.set_snowflakes_enabled(bool(enabled))
        except Exception as e:
            log(f"❌ Ошибка переключения снежинок: {e}", "ERROR")

    def set_window_opacity(self, value: int) -> None:
        """Устанавливает прозрачность фона окна (0–100%).

        Win11: обновляет тинт-оверлей поверх Mica (apply_aero_effect fast path).
        Win10: применяет setWindowOpacity через apply_aero_effect.
        """
        try:
            store = getattr(self, "ui_state_store", None)
            if store is not None:
                store.set_window_opacity_value(value)

            # Эффект применяется только для standard пресета
            from config.reg import get_background_preset
            if get_background_preset() != "standard":
                log(f"Transparent effect проигнорирован (не standard пресет)", "DEBUG")
                return

            from ui.theme import apply_aero_effect
            apply_aero_effect(self, value)
            log(f"Прозрачность обновлена: {value}%", "DEBUG")
        except Exception as e:
            log(f"❌ Ошибка при установке прозрачности окна: {e}", "ERROR")

    def resizeEvent(self, event):
        """Обновляем геометрию при изменении размера окна"""
        super().resizeEvent(event)
        try:
            self._update_titlebar_search_width()
        except Exception:
            pass
        geometry_controller = getattr(self, "window_geometry_controller", None)
        if geometry_controller is not None:
            geometry_controller.on_geometry_changed()
        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is not None:
                effects.sync_geometry()
        except Exception:
            pass
    
    def showEvent(self, event):
        """Первый показ окна"""
        super().showEvent(event)

        if not self._startup_ttff_logged:
            self._startup_ttff_logged = True
            self._startup_ttff_ms = startup_elapsed_ms()
            emit_startup_metric("TTFF", "first showEvent")

        # Применяем сохранённое maximized состояние при первом показе
        geometry_controller = getattr(self, "window_geometry_controller", None)
        if geometry_controller is not None:
            geometry_controller.apply_saved_maximized_state_if_needed()
        # Включаем автосохранение геометрии (после первого show + небольшой паузы)
        if geometry_controller is not None:
            QTimer.singleShot(350, geometry_controller.enable_persistence)

        try:
            effects = getattr(self, "_holiday_effects", None)
            if effects is not None:
                effects.sync_geometry()
                QTimer.singleShot(0, effects.sync_geometry)
        except Exception:
            pass

        notification_controller = getattr(self, "window_notification_controller", None)
        if notification_controller is not None:
            notification_controller.schedule_startup_notification_queue(0)

    def _init_garland_from_registry(self) -> None:
        """Загружает состояние гирлянды и снежинок из реестра при старте"""
        try:
            from config.reg import get_garland_enabled, get_snowflakes_enabled
            
            garland_saved = get_garland_enabled()
            snowflakes_saved = get_snowflakes_enabled()
            log(f"🎄 Инициализация: гирлянда={garland_saved}, снежинки={snowflakes_saved}", "DEBUG")
            
            # Проверяем премиум статус
            is_premium = False
            if hasattr(self, 'donate_checker') and self.donate_checker:
                try:
                    is_premium, _, _ = self.donate_checker.check_subscription_status(use_cache=True)
                    log(f"🎄 Премиум статус: {is_premium}", "DEBUG")
                except Exception as e:
                    log(f"🎄 Ошибка проверки премиума: {e}", "DEBUG")
            
            # Гирлянда
            should_enable_garland = is_premium and garland_saved
            self.set_garland_enabled(should_enable_garland)
            
            # Снежинки
            should_enable_snowflakes = is_premium and snowflakes_saved
            self.set_snowflakes_enabled(should_enable_snowflakes)

            # Прозрачность окна (не зависит от премиума)
            from config.reg import get_window_opacity
            opacity_saved = get_window_opacity()
            log(f"🔮 Инициализация: opacity={opacity_saved}%", "DEBUG")
            self.set_window_opacity(opacity_saved)

            # Анимации интерфейса
            from config.reg import get_animations_enabled
            if not get_animations_enabled() and hasattr(self, '_on_animations_changed'):
                self._on_animations_changed(False)

        except Exception as e:
            log(f"❌ Ошибка загрузки состояния декораций: {e}", "ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")

def window_bootstrap(*, start_in_tray: bool) -> tuple[AppContext, "LupiDPIApp"]:
    app_context = build_app_context(initial_ui_state=LupiDPIApp._build_initial_ui_state())
    install_app_context(app_context)
    window = LupiDPIApp(start_in_tray=start_in_tray, app_context=app_context)
    return app_context, window


def manager_bootstrap(window: "LupiDPIApp") -> None:
    from managers.initialization_manager import InitializationManager
    from managers.subscription_manager import SubscriptionManager
    from managers.process_monitor_manager import ProcessMonitorManager
    from managers.ui_manager import UIManager

    window.initialization_manager = InitializationManager(window)
    window.subscription_manager = SubscriptionManager(window)
    window.process_monitor_manager = ProcessMonitorManager(window)
    window.ui_manager = UIManager(window)

__all__ = ["LupiDPIApp", "window_bootstrap", "manager_bootstrap"]
