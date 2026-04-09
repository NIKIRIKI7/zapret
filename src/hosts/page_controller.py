from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal

from log import log
from utils import get_system32_path


@dataclass(slots=True)
class HostsOperationResult:
    success: bool
    message: str


@dataclass(slots=True)
class HostsRuntimeState:
    active_domains: set[str]
    adobe_active: bool
    accessible: bool
    error_message: str | None


@dataclass(slots=True)
class HostsOperationCompletionPlan:
    reset_profiles: bool
    clear_error: bool
    error_message: str


class HostsOperationWorker(QObject):
    """Background worker for hosts operations."""

    finished = pyqtSignal(bool, str)

    def __init__(self, controller: "HostsPageController", hosts_manager, operation: str, payload=None):
        super().__init__()
        self._controller = controller
        self._hosts_manager = hosts_manager
        self._operation = operation
        self._payload = payload

    def run(self):
        try:
            result = self._controller.execute_operation(
                hosts_manager=self._hosts_manager,
                operation=self._operation,
                payload=self._payload,
            )
            self.finished.emit(result.success, result.message)
        except Exception as e:
            log(f"Ошибка в HostsOperationWorker: {e}", "ERROR")
            self.finished.emit(False, str(e))


class HostsPageController:
    @staticmethod
    def create_operation_worker(hosts_manager, operation: str, payload=None) -> HostsOperationWorker:
        controller = HostsPageController()
        return HostsOperationWorker(controller, hosts_manager, operation, payload)

    @staticmethod
    def execute_operation(*, hosts_manager, operation: str, payload=None) -> HostsOperationResult:
        success = False
        message = ""

        if operation == "apply_selection":
            service_dns = payload or {}
            success = hosts_manager.apply_service_dns_selections(service_dns)
            if success:
                message = "Применено"
            else:
                message = getattr(hosts_manager, "last_status", None) or "Ошибка"

        elif operation == "clear_all":
            success = hosts_manager.clear_hosts_file()
            if success:
                message = "Hosts очищен"
            else:
                message = getattr(hosts_manager, "last_status", None) or "Ошибка"

        elif operation == "adobe_add":
            success = hosts_manager.add_adobe_domains()
            if success:
                message = "Adobe заблокирован"
            else:
                message = getattr(hosts_manager, "last_status", None) or "Ошибка"

        elif operation == "adobe_remove":
            success = hosts_manager.remove_adobe_domains()
            if success:
                message = "Adobe разблокирован"
            else:
                message = getattr(hosts_manager, "last_status", None) or "Ошибка"

        return HostsOperationResult(success=success, message=message)

    @staticmethod
    def restore_hosts_permissions() -> HostsOperationResult:
        from hosts.hosts import restore_hosts_permissions

        success, message = restore_hosts_permissions()
        return HostsOperationResult(success=bool(success), message=str(message or ""))

    @staticmethod
    def read_runtime_state(hosts_manager) -> HostsRuntimeState:
        if hosts_manager is None:
            return HostsRuntimeState(
                active_domains=set(),
                adobe_active=False,
                accessible=False,
                error_message=None,
            )

        error_message: str | None = None
        accessible = False
        active_domains: set[str] = set()
        adobe_active = False

        try:
            accessible = bool(hosts_manager.is_hosts_file_accessible())
        except Exception as exc:
            error_message = str(exc)

        if error_message is None:
            try:
                active_domains = set(hosts_manager.get_active_domains() or set())
            except Exception as exc:
                error_message = str(exc)
                active_domains = set()

        try:
            adobe_active = bool(hosts_manager.is_adobe_domains_active())
        except Exception:
            adobe_active = False

        return HostsRuntimeState(
            active_domains=active_domains,
            adobe_active=adobe_active,
            accessible=accessible,
            error_message=error_message,
        )

    @staticmethod
    def build_operation_completion_plan(*, operation: str | None, success: bool, message: str, hosts_path: str) -> HostsOperationCompletionPlan:
        if success:
            return HostsOperationCompletionPlan(
                reset_profiles=operation == "clear_all",
                clear_error=True,
                error_message="",
            )

        return HostsOperationCompletionPlan(
            reset_profiles=False,
            clear_error=False,
            error_message=f"{message}\nПуть: {hosts_path}",
        )

    @staticmethod
    def get_hosts_path_str() -> str:
        import os

        try:
            if os.name == "nt":
                sys_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
                if sys_root:
                    return os.path.join(sys_root, "System32", "drivers", "etc", "hosts")
            return os.path.join(get_system32_path(), "drivers", "etc", "hosts")
        except Exception:
            return os.path.join(get_system32_path(), "drivers", "etc", "hosts")
