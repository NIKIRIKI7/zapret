from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ui.support_request_actions import prepare_strategy_scan_support_request


@dataclass(slots=True)
class StrategyScanRunLogState:
    path: Path | None
    created: bool


@dataclass(slots=True)
class StrategyApplyResult:
    strategy_name: str
    applied_target: str
    selected_file_name: str


@dataclass(slots=True)
class StrategyScanStartPlan:
    target: str
    scan_protocol: str
    udp_games_scope: str
    mode: str
    resume_next_index: int
    resume_available: bool
    keep_current_results: bool
    scan_cursor: int
    status_text: str


@dataclass(slots=True)
class StrategyScanFinishPlan:
    total_available: int
    working_count: int
    total_count: int
    cancelled: bool
    baseline_accessible: bool
    status_text: str
    log_message: str | None
    support_status_code: str
    notification_kind: str
    baseline_variant: str


class StrategyScanPageController:
    @staticmethod
    def normalize_udp_games_scope(scope: str) -> str:
        raw = (scope or "").strip().lower()
        if raw in {"games_only", "games", "only_games", "targeted"}:
            return "games_only"
        return "all"

    @staticmethod
    def default_target_for_protocol(scan_protocol: str) -> str:
        protocol = (scan_protocol or "").strip().lower()
        if protocol == "stun_voice":
            return "stun.l.google.com:19302"
        if protocol == "udp_games":
            return "stun.cloudflare.com:3478"
        return "discord.com"

    @staticmethod
    def stun_target_parts(value: str, default_port: int = 3478) -> tuple[str, int]:
        raw = (value or "").strip()
        if not raw:
            return "", default_port

        if raw.upper().startswith("STUN:"):
            raw = raw[5:].strip()

        raw = re.sub(r"^https?://", "", raw, flags=re.IGNORECASE)
        raw = raw.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
        if not raw:
            return "", default_port

        if raw.startswith("["):
            right = raw.find("]")
            if right > 1:
                host = raw[1:right].strip()
                rest = raw[right + 1 :].strip()
                if rest.startswith(":"):
                    try:
                        port = int(rest[1:])
                        if 1 <= port <= 65535:
                            return host, port
                    except ValueError:
                        pass
                return host, default_port

        if raw.count(":") == 1:
            host, port_str = raw.rsplit(":", 1)
            host = host.strip()
            if host:
                try:
                    port = int(port_str)
                    if 1 <= port <= 65535:
                        return host, port
                except ValueError:
                    pass
                return host, default_port

        return raw, default_port

    @staticmethod
    def format_stun_target(host: str, port: int) -> str:
        host = (host or "").strip()
        if not host:
            return ""
        if ":" in host and not host.startswith("["):
            return f"[{host}]:{int(port)}"
        return f"{host}:{int(port)}"

    @staticmethod
    def normalize_target_domain(value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return ""
        try:
            from blockcheck.targets import _normalize_domain

            return _normalize_domain(raw)
        except Exception:
            return raw.lower()

    def normalize_target_input(self, value: str, scan_protocol: str) -> str:
        protocol = (scan_protocol or "").strip().lower()
        if protocol in {"stun_voice", "udp_games"}:
            host, port = self.stun_target_parts(value)
            if not host:
                return ""
            return self.format_stun_target(host, port)
        return self.normalize_target_domain(value)

    def resolve_games_ipset_paths(self, udp_games_scope: str = "all") -> list[str]:
        scope = self.normalize_udp_games_scope(udp_games_scope)

        explicit_game_files = (
            "ipset-roblox.txt",
            "ipset-amazon.txt",
            "ipset-steam.txt",
            "ipset-epicgames.txt",
            "ipset-epic.txt",
            "ipset-lol-ru.txt",
            "ipset-lol-euw.txt",
            "ipset-tankix.txt",
        )

        list_dirs: list[Path] = []

        appdata = (os.environ.get("APPDATA") or "").strip()
        if appdata:
            list_dirs.extend(
                [
                    Path(appdata) / "ZapretTwoDev" / "lists",
                    Path(appdata) / "ZapretTwo" / "lists",
                ]
            )

        try:
            from config import APPDATA_DIR, get_zapret_userdata_dir

            app_channel_dir = (APPDATA_DIR or "").strip()
            if app_channel_dir:
                list_dirs.append(Path(app_channel_dir) / "lists")

            user_data_dir = (get_zapret_userdata_dir() or "").strip()
            if user_data_dir:
                list_dirs.append(Path(user_data_dir) / "lists")
        except Exception:
            pass

        try:
            from config import MAIN_DIRECTORY

            list_dirs.append(Path(MAIN_DIRECTORY) / "lists")
        except Exception:
            list_dirs.append(Path.cwd() / "lists")

        files: list[str] = []
        seen: set[str] = set()
        for base_dir in list_dirs:
            if scope == "all":
                ipset_all = base_dir / "ipset-all.txt"
                key_all = str(ipset_all)
                if key_all not in seen:
                    seen.add(key_all)
                    if ipset_all.exists():
                        return [str(ipset_all)]

            for filename in explicit_game_files:
                candidate = base_dir / filename
                key = str(candidate)
                if key in seen:
                    continue
                seen.add(key)
                if candidate.exists():
                    files.append(str(candidate))

            if scope == "games_only":
                continue

            try:
                for candidate in sorted(base_dir.glob("ipset-*.txt")):
                    key = str(candidate)
                    if key in seen:
                        continue
                    seen.add(key)
                    if candidate.exists():
                        files.append(str(candidate))
            except OSError:
                continue

        if files:
            return files

        if scope == "games_only":
            return ["lists/ipset-roblox.txt"]
        return ["lists/ipset-all.txt"]

    def load_quick_domains(self) -> list[str]:
        try:
            from blockcheck.targets import load_domains

            raw_domains = load_domains()
        except Exception:
            raw_domains = []

        normalized_domains: list[str] = []
        seen: set[str] = set()
        for raw in raw_domains:
            domain = self.normalize_target_domain(str(raw))
            if not domain or domain in seen:
                continue
            seen.add(domain)
            normalized_domains.append(domain)

        return normalized_domains

    def load_quick_stun_targets(self) -> list[str]:
        try:
            from blockcheck.targets import get_default_stun_targets

            raw_targets = get_default_stun_targets()
        except Exception:
            raw_targets = []

        targets: list[str] = []
        seen: set[str] = set()
        for item in raw_targets:
            value = str(item.get("value", ""))
            normalized = self.normalize_target_input(value, "stun_voice")
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            targets.append(normalized)

        return targets

    def plan_scan_start(
        self,
        *,
        raw_target_input: str,
        scan_protocol: str,
        udp_games_scope: str,
        mode: str,
        previous_target: str,
        previous_protocol: str,
        previous_scope: str,
        result_rows_count: int,
        table_row_count: int,
        starting_status_text: str,
    ) -> StrategyScanStartPlan:
        target = self.normalize_target_input(raw_target_input, scan_protocol)
        if not target:
            target = self.default_target_for_protocol(scan_protocol)

        prev_target_key = self.target_key(previous_target, previous_protocol, previous_scope)
        target_key = self.target_key(target, scan_protocol, udp_games_scope)

        resume_next_index = self.get_resume_index(target, scan_protocol, udp_games_scope)
        resume_available = resume_next_index > 0

        keep_current_results = (
            resume_available
            and previous_protocol == scan_protocol
            and previous_scope == udp_games_scope
            and prev_target_key == target_key
            and result_rows_count == resume_next_index
            and table_row_count == result_rows_count
        )

        scan_cursor = resume_next_index if resume_available else 0
        if resume_available:
            status_text = f"Возобновление сканирования с [{scan_cursor + 1}]..."
        else:
            status_text = starting_status_text

        return StrategyScanStartPlan(
            target=target,
            scan_protocol=scan_protocol,
            udp_games_scope=udp_games_scope,
            mode=mode,
            resume_next_index=resume_next_index,
            resume_available=resume_available,
            keep_current_results=keep_current_results,
            scan_cursor=scan_cursor,
            status_text=status_text,
        )

    @staticmethod
    def resume_state_path() -> Path:
        try:
            from config import APPDATA_DIR

            base_dir = Path(APPDATA_DIR)
        except Exception:
            try:
                from config import MAIN_DIRECTORY

                base_dir = Path(MAIN_DIRECTORY)
            except Exception:
                base_dir = Path.cwd()
        return base_dir / "strategy_scan_resume.json"

    @staticmethod
    def target_key(
        target: str,
        scan_protocol: str = "tcp_https",
        udp_games_scope: str = "all",
    ) -> str:
        normalized_target = (target or "").strip().lower()
        normalized_protocol = (scan_protocol or "tcp_https").strip().lower() or "tcp_https"
        if not normalized_target:
            return ""

        if normalized_protocol == "udp_games":
            scope = (udp_games_scope or "all").strip().lower()
            if scope not in {"all", "games_only"}:
                scope = "all"
            return f"{normalized_protocol}|{scope}|{normalized_target}"

        return f"{normalized_protocol}|{normalized_target}"

    def load_resume_state(self) -> dict:
        path = self.resume_state_path()
        empty_state = {"domains": {}}
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return empty_state

            domains = data.get("domains")
            if isinstance(domains, dict):
                cleaned_domains = {}
                for raw_key, raw_value in domains.items():
                    raw_key_str = str(raw_key).strip().lower()
                    if not raw_key_str:
                        continue
                    if "|" in raw_key_str:
                        parts = raw_key_str.split("|")
                        if len(parts) == 2 and parts[0] == "udp_games":
                            key = f"udp_games|all|{parts[1]}"
                        else:
                            key = raw_key_str
                    else:
                        key = self.target_key(raw_key_str, "tcp_https")
                    if not key:
                        continue
                    if isinstance(raw_value, dict):
                        raw_index = raw_value.get("next_index", 0)
                    else:
                        raw_index = raw_value
                    try:
                        next_index = max(0, int(raw_index))
                    except Exception:
                        next_index = 0
                    cleaned_domains[key] = {"next_index": next_index}
                return {"domains": cleaned_domains}

            key = self.target_key(str(data.get("target", "") or ""))
            try:
                next_index = max(0, int(data.get("next_index", 0) or 0))
            except Exception:
                next_index = 0
            if key and next_index > 0:
                return {"domains": {key: {"next_index": next_index}}}
            return empty_state
        except Exception:
            return empty_state

    def write_resume_state(self, state: dict) -> None:
        path = self.resume_state_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get_resume_index(self, target: str, scan_protocol: str, udp_games_scope: str = "all") -> int:
        key = self.target_key(target, scan_protocol, udp_games_scope)
        if not key:
            return 0
        state = self.load_resume_state()
        domains = state.get("domains", {})
        entry = domains.get(key, {})

        if not entry and (scan_protocol or "").strip().lower() == "udp_games":
            legacy_key = f"udp_games|{(target or '').strip().lower()}"
            entry = domains.get(legacy_key, {})

        if not entry and (scan_protocol or "").strip().lower() == "tcp_https":
            legacy_key = (target or "").strip().lower()
            entry = domains.get(legacy_key, {})
        try:
            return max(0, int(entry.get("next_index", 0) or 0))
        except Exception:
            return 0

    def save_resume_state(
        self,
        target: str,
        scan_protocol: str,
        next_index: int,
        udp_games_scope: str = "all",
    ) -> None:
        key = self.target_key(target, scan_protocol, udp_games_scope)
        if not key:
            return
        state = self.load_resume_state()
        domains = state.setdefault("domains", {})
        domains[key] = {"next_index": max(0, int(next_index))}
        self.write_resume_state(state)

    def clear_resume_state(self, target: str, scan_protocol: str, udp_games_scope: str = "all") -> None:
        key = self.target_key(target, scan_protocol, udp_games_scope)
        if not key:
            return
        state = self.load_resume_state()
        domains = state.get("domains", {})
        if key in domains:
            del domains[key]

        if (scan_protocol or "").strip().lower() == "udp_games":
            legacy_key = f"udp_games|{(target or '').strip().lower()}"
            if legacy_key in domains:
                del domains[legacy_key]

        if (scan_protocol or "").strip().lower() == "tcp_https":
            legacy_key = (target or "").strip().lower()
            if legacy_key in domains:
                del domains[legacy_key]

        if domains:
            state["domains"] = domains
            self.write_resume_state(state)
        else:
            path = self.resume_state_path()
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass

    @staticmethod
    def _sanitize_slug(value: str, fallback: str) -> str:
        raw = (value or "").strip().lower()
        cleaned = "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in raw)
        cleaned = cleaned.strip("_")
        return cleaned or fallback

    @staticmethod
    def _resolve_log_dir() -> Path:
        try:
            from config import LOGS_FOLDER

            log_dir = Path(LOGS_FOLDER)
        except Exception:
            log_dir = Path.cwd() / "logs"

        try:
            from log import global_logger

            active_log = getattr(global_logger, "log_file", None)
            if isinstance(active_log, str) and active_log.strip():
                resolved_dir = Path(active_log).parent
                if str(resolved_dir):
                    log_dir = resolved_dir
        except Exception:
            pass

        return log_dir

    def make_run_log_path(
        self,
        target: str,
        mode: str,
        scan_protocol: str,
        udp_games_scope: str = "all",
    ) -> Path:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_mode = self._sanitize_slug(mode, "mode")
        safe_protocol = self._sanitize_slug(scan_protocol, "protocol")
        safe_scope = self._sanitize_slug(udp_games_scope, "scope")
        safe_target = self._sanitize_slug(target, "target")
        scope_suffix = f"_{safe_scope}" if scan_protocol == "udp_games" else ""
        filename = (
            f"blockcheck_run_{ts}_strategy_scan_{safe_mode}_{safe_protocol}"
            f"{scope_suffix}_{safe_target}.log"
        )
        return self._resolve_log_dir() / filename

    def start_run_log(
        self,
        *,
        target: str,
        mode: str,
        scan_protocol: str,
        resume_index: int,
        udp_games_scope: str = "all",
    ) -> StrategyScanRunLogState:
        primary_path = self.make_run_log_path(
            target=target,
            mode=mode,
            scan_protocol=scan_protocol,
            udp_games_scope=udp_games_scope,
        )
        candidates = [primary_path]

        try:
            from config import APPDATA_DIR

            candidates.append(Path(APPDATA_DIR) / "logs" / primary_path.name)
        except Exception:
            pass

        candidates.append(Path.cwd() / "logs" / primary_path.name)

        tried: set[Path] = set()
        for path in candidates:
            if path in tried:
                continue
            tried.add(path)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", encoding="utf-8-sig") as f:
                    f.write(f"=== Strategy Scan Run Log ({datetime.now():%Y-%m-%d %H:%M:%S}) ===\n")
                    f.write(f"Mode: {mode}\n")
                    f.write(f"Protocol: {scan_protocol}\n")
                    if scan_protocol == "udp_games":
                        f.write(f"UDP games scope: {udp_games_scope}\n")
                    f.write(f"Target: {target}\n")
                    f.write(f"Resume index: {max(0, int(resume_index))}\n")
                    f.write("=" * 70 + "\n\n")
                return StrategyScanRunLogState(path=path, created=True)
            except Exception:
                continue

        return StrategyScanRunLogState(path=None, created=False)

    @staticmethod
    def append_run_log(path: Path | None, message: str) -> None:
        if path is None:
            return
        try:
            text = str(message or "")
            if not text.endswith("\n"):
                text += "\n"
            with path.open("a", encoding="utf-8-sig") as f:
                f.write(text)
        except Exception:
            pass

    def prepare_support(
        self,
        *,
        run_log_file: Path | None,
        target: str,
        protocol_label: str,
        mode_label: str,
        scan_protocol: str,
    ):
        return prepare_strategy_scan_support_request(
            run_log_file=str(run_log_file) if run_log_file is not None else None,
            target=target,
            protocol_label=protocol_label,
            mode_label=mode_label,
            resume_state_path=self.resume_state_path(),
            scan_protocol=scan_protocol,
        )

    def finalize_scan_report(
        self,
        report,
        *,
        scan_target: str,
        scan_protocol: str,
        scan_udp_games_scope: str,
        scan_mode: str,
        scan_cursor: int,
        result_rows: list[dict],
    ) -> StrategyScanFinishPlan:
        working = sum(1 for row in result_rows if row.get("success"))

        if report is None:
            if scan_cursor > 0:
                self.save_resume_state(
                    scan_target,
                    scan_protocol,
                    scan_cursor,
                    scan_udp_games_scope,
                )
            return StrategyScanFinishPlan(
                total_available=0,
                working_count=working,
                total_count=scan_cursor,
                cancelled=False,
                baseline_accessible=False,
                status_text="Ошибка сканирования",
                log_message="ERROR: Strategy scan execution failed",
                support_status_code="ready_after_error",
                notification_kind="none",
                baseline_variant="stun" if scan_protocol in {"stun_voice", "udp_games"} else "tcp",
            )

        total_available = max(0, int(getattr(report, "total_available", 0) or 0))

        if report.cancelled:
            if scan_cursor > 0:
                self.save_resume_state(
                    scan_target,
                    scan_protocol,
                    scan_cursor,
                    scan_udp_games_scope,
                )
            else:
                self.clear_resume_state(
                    scan_target,
                    scan_protocol,
                    scan_udp_games_scope,
                )
        else:
            full_scan_completed = (
                scan_mode == "full"
                and total_available > 0
                and report.total_tested >= total_available
            )
            if full_scan_completed:
                self.clear_resume_state(
                    scan_target,
                    scan_protocol,
                    scan_udp_games_scope,
                )
            else:
                self.save_resume_state(
                    scan_target,
                    scan_protocol,
                    report.total_tested,
                    scan_udp_games_scope,
                )

        total_count = max(scan_cursor, report.total_tested)
        elapsed = report.elapsed_seconds

        if report.cancelled:
            status_text = f"Отменено. Протестировано: {total_count}, рабочих: {working} ({elapsed:.1f}s)"
        else:
            status_text = f"Готово. Протестировано: {total_count}, рабочих: {working} ({elapsed:.1f}s)"

        if report.baseline_accessible:
            notification_kind = "baseline_accessible"
        elif working > 0:
            notification_kind = "found"
        else:
            notification_kind = "not_found"

        return StrategyScanFinishPlan(
            total_available=total_available,
            working_count=working,
            total_count=total_count,
            cancelled=bool(report.cancelled),
            baseline_accessible=bool(report.baseline_accessible),
            status_text=status_text,
            log_message=f"\n{status_text}",
            support_status_code="ready",
            notification_kind=notification_kind,
            baseline_variant="stun" if scan_protocol in {"stun_voice", "udp_games"} else "tcp",
        )

    @staticmethod
    def generate_blob_lines_for_apply(strategy_args: str) -> list[str]:
        try:
            from launcher_common.blobs import find_used_blobs, get_blobs

            used = find_used_blobs(strategy_args)
            if not used:
                return []
            blobs = get_blobs()
            return [f"--blob={name}:{blobs[name]}" for name in sorted(used) if name in blobs]
        except Exception:
            return []

    @staticmethod
    def prepend_strategy_block(existing_content: str, strategy_lines: list[str], blob_lines: list[str]) -> str:
        normalized = (existing_content or "").replace("\r\n", "\n").replace("\r", "\n")
        all_lines = normalized.split("\n")

        first_filter_idx = len(all_lines)
        filter_prefixes = ("--filter-tcp", "--filter-udp", "--filter-l7")
        for idx, raw_line in enumerate(all_lines):
            if raw_line.strip().startswith(filter_prefixes):
                first_filter_idx = idx
                break

        prefix_lines = all_lines[:first_filter_idx]
        body_lines = all_lines[first_filter_idx:]

        while prefix_lines and not prefix_lines[-1].strip():
            prefix_lines.pop()

        prefix_set = {line.strip() for line in prefix_lines if line.strip()}
        missing_blob_lines = [line for line in blob_lines if line.strip() and line.strip() not in prefix_set]
        if missing_blob_lines:
            if prefix_lines and prefix_lines[-1].strip():
                prefix_lines.append("")
            prefix_lines.extend(missing_blob_lines)

        cleaned_strategy_lines = [line.strip() for line in strategy_lines if line and line.strip()]

        if prefix_lines and prefix_lines[-1].strip():
            prefix_lines.append("")

        result_lines = list(prefix_lines)
        result_lines.extend(cleaned_strategy_lines)

        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)

        if body_lines:
            result_lines.extend(["", "--new", ""])
            result_lines.extend(body_lines)

        return "\n".join(result_lines).rstrip("\n") + "\n"

    def apply_strategy(
        self,
        *,
        strategy_args: str,
        strategy_name: str,
        scan_target: str,
        scan_protocol: str,
        scan_udp_games_scope: str,
    ) -> StrategyApplyResult:
        from core.presets.direct_facade import DirectPresetFacade
        from core.presets.direct_runtime_events import notify_direct_preset_saved

        facade = DirectPresetFacade.from_launch_method("direct_zapret2")
        selected_file_name = str(facade.get_selected_file_name() or "").strip()
        if not selected_file_name:
            raise RuntimeError("Не удалось определить выбранный пресет")

        target = scan_target or self.default_target_for_protocol(scan_protocol)
        blob_lines = self.generate_blob_lines_for_apply(strategy_args)

        if scan_protocol == "stun_voice":
            target_host, target_port = self.stun_target_parts(target)
            if not target_host:
                target_host = "stun.l.google.com"
                target_port = 19302

            new_strategy_lines = [
                "--wf-udp-out=443-65535",
                "--filter-l7=stun,discord",
                "--payload=stun,discord_ip_discovery",
                strategy_args,
            ]
            applied_target = f"voice (probe: {self.format_stun_target(target_host, target_port)})"
        elif scan_protocol == "udp_games":
            games_ipset_paths = self.resolve_games_ipset_paths(scan_udp_games_scope)
            probe_host, probe_port = self.stun_target_parts(target)
            if not probe_host:
                probe_host = "stun.cloudflare.com"
                probe_port = 3478

            new_strategy_lines = [
                "--wf-udp-out=443,50000-65535",
                "--filter-udp=443,50000-65535",
                *[f"--ipset={path}" for path in games_ipset_paths],
                strategy_args,
            ]
            shown_paths = ", ".join(games_ipset_paths[:3])
            if len(games_ipset_paths) > 3:
                shown_paths += f", ... (+{len(games_ipset_paths) - 3})"
            applied_target = (
                f"Games UDP ipsets ({shown_paths}), "
                f"probe {self.format_stun_target(probe_host, probe_port)}"
            )
        else:
            normalized_target = self.normalize_target_domain(target) or "discord.com"
            new_strategy_lines = [
                "--filter-tcp=443",
                f"--hostlist-domains={normalized_target}",
                "--out-range=-d8",
                strategy_args,
            ]
            applied_target = normalized_target

        existing_content = facade.read_selected_source_text()
        updated_content = self.prepend_strategy_block(
            existing_content=existing_content,
            strategy_lines=new_strategy_lines,
            blob_lines=blob_lines,
        )

        facade.save_source_text_by_file_name(selected_file_name, updated_content)
        notify_direct_preset_saved("direct_zapret2", selected_file_name)

        return StrategyApplyResult(
            strategy_name=strategy_name,
            applied_target=applied_target,
            selected_file_name=selected_file_name,
        )
