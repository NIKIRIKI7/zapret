from __future__ import annotations

import glob
import os
import subprocess
from dataclasses import dataclass

from config import LOGS_FOLDER, MAX_DEBUG_LOG_FILES, MAX_LOG_FILES, get_winws_exe_for_method
from launcher_common import get_current_runner
from log import LOG_FILE, cleanup_old_logs, global_logger, log
from support_request_bundle import prepare_support_request


@dataclass(slots=True)
class LogsListState:
    entries: list[dict]
    current_log_file: str
    cleanup_deleted: int
    cleanup_errors: list[str]
    cleanup_total: int


@dataclass(slots=True)
class LogsStatsState:
    app_logs: int
    debug_logs: int
    total_size_mb: float
    max_logs: int
    max_debug_logs: int


class LogsPageController:
    def get_current_log_file(self) -> str:
        return getattr(global_logger, "log_file", LOG_FILE)

    def list_logs(self, *, run_cleanup: bool) -> LogsListState:
        cleanup_deleted = 0
        cleanup_errors: list[str] = []
        cleanup_total = 0

        if run_cleanup:
            cleanup_deleted, cleanup_errors, cleanup_total = cleanup_old_logs(LOGS_FOLDER, MAX_LOG_FILES)

        log_files: list[str] = []
        log_files.extend(glob.glob(os.path.join(LOGS_FOLDER, "zapret_log_*.txt")))
        log_files.extend(glob.glob(os.path.join(LOGS_FOLDER, "zapret_[0-9]*.log")))
        log_files.extend(glob.glob(os.path.join(LOGS_FOLDER, "blockcheck_run_*.log")))
        log_files.sort(key=os.path.getmtime, reverse=True)

        current_log = self.get_current_log_file()
        entries: list[dict] = []
        for index, log_path in enumerate(log_files):
            size_kb = os.path.getsize(log_path) / 1024
            is_current = log_path == current_log
            if is_current:
                display = f"📍 {os.path.basename(log_path)} ({size_kb:.1f} KB) - ТЕКУЩИЙ"
            else:
                display = f"{os.path.basename(log_path)} ({size_kb:.1f} KB)"
            entries.append(
                {
                    "index": index,
                    "path": log_path,
                    "size_kb": size_kb,
                    "display": display,
                    "is_current": is_current,
                }
            )

        return LogsListState(
            entries=entries,
            current_log_file=current_log,
            cleanup_deleted=cleanup_deleted,
            cleanup_errors=cleanup_errors,
            cleanup_total=cleanup_total,
        )

    def build_stats(self) -> LogsStatsState:
        app_logs = glob.glob(os.path.join(LOGS_FOLDER, "zapret_log_*.txt"))
        app_logs.extend(glob.glob(os.path.join(LOGS_FOLDER, "zapret_[0-9]*.log")))
        app_logs.extend(glob.glob(os.path.join(LOGS_FOLDER, "blockcheck_run_*.log")))
        debug_logs = glob.glob(os.path.join(LOGS_FOLDER, "zapret_winws2_debug_*.log"))
        all_files = app_logs + debug_logs
        total_size = sum(os.path.getsize(path) for path in all_files) / 1024 / 1024
        return LogsStatsState(
            app_logs=len(app_logs),
            debug_logs=len(debug_logs),
            total_size_mb=total_size,
            max_logs=MAX_LOG_FILES,
            max_debug_logs=MAX_DEBUG_LOG_FILES,
        )

    def resolve_winws_exe_name(self, launch_method: str) -> str:
        try:
            return os.path.basename(get_winws_exe_for_method(launch_method)) or "winws.exe"
        except Exception:
            return "winws.exe"

    def get_running_runner_source(self, launch_method: str, orchestra_runner):
        direct_runner = get_current_runner()

        orchestra_running = bool(orchestra_runner and orchestra_runner.is_running())
        direct_running = bool(direct_runner and direct_runner.is_running())

        if launch_method == "orchestra":
            if orchestra_running:
                return "orchestra", orchestra_runner
            if direct_running:
                return "direct", direct_runner
            return None, None

        if direct_running:
            return "direct", direct_runner
        if orchestra_running:
            return "orchestra", orchestra_runner
        return None, None

    def get_runner_pid(self, runner):
        if not runner:
            return "?"

        try:
            get_pid = getattr(runner, "get_pid", None)
            if callable(get_pid):
                pid = get_pid()
                if pid:
                    return pid
        except Exception:
            pass

        try:
            get_info = getattr(runner, "get_current_strategy_info", None)
            if callable(get_info):
                info = get_info()
                pid = info.get("pid") if isinstance(info, dict) else None
                if pid:
                    return pid
        except Exception:
            pass

        try:
            process = getattr(runner, "running_process", None)
            pid = getattr(process, "pid", None)
            if pid:
                return pid
        except Exception:
            pass

        return "?"

    def get_orchestra_log_path(self, orchestra_runner):
        try:
            if orchestra_runner:
                if orchestra_runner.current_log_id and orchestra_runner.debug_log_path:
                    if os.path.exists(orchestra_runner.debug_log_path):
                        return orchestra_runner.debug_log_path

                logs = orchestra_runner.get_log_history()
                if logs:
                    latest_log = logs[0]
                    log_path = os.path.join(LOGS_FOLDER, latest_log["filename"])
                    if os.path.exists(log_path):
                        return log_path
        except Exception as exc:
            log(f"Ошибка получения пути лога оркестратора: {exc}", "DEBUG")

        try:
            pattern = os.path.join(LOGS_FOLDER, "orchestra_*.log")
            files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
            if files:
                return files[0]
        except Exception as exc:
            log(f"Ошибка fallback поиска лога: {exc}", "DEBUG")

        log("Лог оркестратора не найден для отправки", "WARNING")
        return None

    def prepare_support_bundle(self, *, current_log_file: str, orchestra_runner):
        candidate_paths = [
            current_log_file,
            self.get_current_log_file(),
            self.get_orchestra_log_path(orchestra_runner),
            os.path.join(LOGS_FOLDER, "commands_full.log"),
            os.path.join(LOGS_FOLDER, "last_command.txt"),
        ]
        return prepare_support_request(
            bundle_prefix="support_logs",
            context_label="Логи приложения",
            candidate_paths=candidate_paths,
            recent_patterns=("zapret_winws2_debug_*.log", "blockcheck_run_*.log"),
            extra_note="Если проблема связана с оркестратором, в архив по возможности добавлен и его свежий лог.",
        )

    def open_logs_folder(self) -> None:
        subprocess.run(["explorer", LOGS_FOLDER], check=False)
