from __future__ import annotations

import subprocess
from dataclasses import dataclass

from config import REGISTRY_PATH
from log import log


@dataclass(slots=True)
class NetworkPageData:
    adapters: list[tuple[str, str]]
    dns_info: dict[str, dict[str, list[str]]]
    ipv6_available: bool
    force_dns_active: bool


class NetworkPageController:
    def __init__(self) -> None:
        self._dns_manager = self._new_dns_manager()

    @property
    def dns_manager(self):
        return self._dns_manager

    @staticmethod
    def _new_dns_manager():
        from .dns_core import DNSManager

        return DNSManager()

    @staticmethod
    def _new_force_dns_manager():
        from .dns_force import DNSForceManager

        return DNSForceManager()

    @staticmethod
    def detect_ipv6_availability() -> bool:
        try:
            from .dns_force import DNSForceManager

            return bool(DNSForceManager.check_ipv6_connectivity())
        except Exception as exc:
            log(f"Ошибка проверки IPv6 у провайдера: {exc}", "DEBUG")
            return False

    def load_page_data(self) -> NetworkPageData:
        ipv6_available = self.detect_ipv6_availability()

        from .dns_core import refresh_exclusion_cache
        from .dns_force import ensure_default_force_dns

        all_adapters = self._dns_manager.get_network_adapters_fast(
            include_ignored=True,
            include_disconnected=True,
        )
        filtered = [
            (name, desc)
            for name, desc in all_adapters
            if not self._dns_manager.should_ignore_adapter(name, desc)
        ]
        adapter_names = [name for name, _ in all_adapters]
        dns_info = self._dns_manager.get_all_dns_info_fast(adapter_names)

        ensure_default_force_dns()
        force_dns_active = self._new_force_dns_manager().is_force_dns_enabled()

        return NetworkPageData(
            adapters=filtered,
            dns_info=dns_info,
            ipv6_available=ipv6_available,
            force_dns_active=force_dns_active,
        )

    def refresh_dns_info(self, adapter_names: list[str]) -> dict[str, dict[str, list[str]]]:
        return self._dns_manager.get_all_dns_info_fast(adapter_names)

    def apply_auto_dns(self, adapters: list[str]) -> int:
        success_count = 0
        for adapter in adapters:
            ok_v4, _ = self._dns_manager.set_auto_dns(adapter, "IPv4")
            ok_v6, _ = self._dns_manager.set_auto_dns(adapter, "IPv6")
            if ok_v4 and ok_v6:
                success_count += 1
        self._dns_manager.flush_dns_cache()
        return success_count

    def apply_provider_dns(
        self,
        adapters: list[str],
        ipv4: list[str],
        ipv6: list[str],
        *,
        ipv6_available: bool,
    ) -> int:
        success_count = 0
        for adapter in adapters:
            ok_v4, _ = self._dns_manager.set_custom_dns(
                adapter,
                ipv4[0],
                ipv4[1] if len(ipv4) > 1 else None,
                "IPv4",
            )
            ok_v6 = True
            if ipv6_available and ipv6:
                ok_v6, _ = self._dns_manager.set_custom_dns(
                    adapter,
                    ipv6[0],
                    ipv6[1] if len(ipv6) > 1 else None,
                    "IPv6",
                )
            if ok_v4 and ok_v6:
                success_count += 1
        self._dns_manager.flush_dns_cache()
        return success_count

    def apply_custom_dns(self, adapters: list[str], primary: str, secondary: str | None) -> int:
        success_count = 0
        for adapter in adapters:
            ok, _ = self._dns_manager.set_custom_dns(adapter, primary, secondary, "IPv4")
            if ok:
                success_count += 1
        self._dns_manager.flush_dns_cache()
        return success_count

    def get_force_dns_status(self) -> bool:
        return self._new_force_dns_manager().is_force_dns_enabled()

    def enable_force_dns(self, *, include_disconnected: bool = False) -> tuple[bool, int, int, str]:
        return self._new_force_dns_manager().enable_force_dns(include_disconnected=include_disconnected)

    def disable_force_dns(self, *, reset_to_auto: bool) -> tuple[bool, str]:
        return self._new_force_dns_manager().disable_force_dns(reset_to_auto=reset_to_auto)

    def flush_dns_cache(self) -> tuple[bool, str]:
        return self._dns_manager.flush_dns_cache()

    def run_connectivity_test(self, test_hosts: list[tuple[str, str]]) -> list[tuple[str, str, bool]]:
        results: list[tuple[str, str, bool]] = []
        for name, host in test_hosts:
            try:
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", "2000", host],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                results.append((name, host, result.returncode == 0))
            except Exception:
                results.append((name, host, False))
        return results

    @staticmethod
    def should_show_isp_dns_warning(
        adapters: list[tuple[str, str]],
        dns_info: dict[str, dict[str, list[str]]],
        *,
        force_dns_active: bool,
    ) -> bool:
        from .dns_core import _normalize_alias

        if force_dns_active:
            return False

        try:
            from config.reg import reg

            if reg(REGISTRY_PATH, "ISPDNSInfoShown"):
                return False
        except Exception:
            pass

        has_adapters = False
        all_dhcp = True
        for name, _desc in adapters:
            has_adapters = True
            clean = _normalize_alias(name)
            adapter_data = dns_info.get(clean, {"ipv4": [], "ipv6": []})
            ipv4 = DNSProviderCardProxy.normalize_dns_list(adapter_data.get("ipv4", []))
            if ipv4:
                all_dhcp = False
                break
        return bool(has_adapters and all_dhcp)

    @staticmethod
    def mark_isp_dns_warning_shown() -> None:
        try:
            from config.reg import reg

            reg(REGISTRY_PATH, "ISPDNSInfoShown", 1)
        except Exception:
            pass


class DNSProviderCardProxy:
    @staticmethod
    def normalize_dns_list(value) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.replace(",", " ").split() if item.strip()]
        if isinstance(value, list):
            result: list[str] = []
            for item in value:
                item_s = str(item).strip()
                if item_s:
                    result.append(item_s)
            return result
        return []
