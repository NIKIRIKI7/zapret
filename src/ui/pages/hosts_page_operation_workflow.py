"""Helper-слой фоновых операций Hosts page."""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QThread

from hosts.page_controller import HostsPageController


def start_hosts_operation(
    *,
    hosts_manager,
    applying: bool,
    operation: str,
    payload,
    on_operation_complete: Callable[[bool, str], None],
):
    if not hosts_manager or applying:
        return None

    worker = HostsPageController.create_operation_worker(hosts_manager, operation, payload)
    thread = QThread()

    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(on_operation_complete)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()

    return {
        "applying": True,
        "current_operation": operation,
        "worker": worker,
        "thread": thread,
    }


def reset_all_service_profiles_ui(
    *,
    service_combos: dict,
    is_fluent_combo: Callable[[object], bool],
    checkbox_cls,
    get_building_state: Callable[[], bool],
    set_building_state: Callable[[bool], None],
    update_profile_visual: Callable[[str], None],
) -> dict[str, str]:
    reset_plan = HostsPageController.build_reset_selection_plan()
    new_selection = dict(reset_plan.new_selection)
    HostsPageController.save_user_selection(new_selection)

    was_building = get_building_state()
    set_building_state(True)
    try:
        for control in service_combos.values():
            if is_fluent_combo(control):
                control.blockSignals(True)
                control.setCurrentIndex(0)
                control.blockSignals(False)
            elif isinstance(control, checkbox_cls):
                control.setChecked(False)
    finally:
        set_building_state(was_building)

    for service_name in list(service_combos.keys()):
        update_profile_visual(service_name)

    return new_selection


def complete_hosts_operation(
    *,
    current_operation: str | None,
    success: bool,
    message: str,
    hosts_path: str,
    invalidate_cache: Callable[[], None],
    update_ui: Callable[[], None],
    sync_selections_from_hosts: Callable[[], None],
    reset_profiles_ui: Callable[[], None],
    hide_error: Callable[[], None],
    show_error: Callable[[str], None],
):
    completion_plan = HostsPageController.build_operation_completion_plan(
        operation=current_operation,
        success=success,
        message=message,
        hosts_path=hosts_path,
    )

    invalidate_cache()
    update_ui()
    sync_selections_from_hosts()

    if completion_plan.reset_profiles:
        reset_profiles_ui()

    if completion_plan.clear_error:
        hide_error()
    else:
        show_error(completion_plan.error_message)

    return {
        "current_operation": None,
        "applying": False,
    }
