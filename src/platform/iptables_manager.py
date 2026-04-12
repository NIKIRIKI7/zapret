"""Linux iptables/nftables management for nfqws DPI bypass.

На Linux nfqws не перехватывает пакеты сам — нужно направить трафик
в NFQUEUE через iptables/nftables правила. Этот модуль управляет
жизненным циклом этих правил.

Пример использования:
    manager = IptablesManager(queue_num=200)
    manager.setup(rules=["--filter-tcp-port=443", "--filter-tcp-port=80"])
    # ... запускаем nfqws ...
    manager.cleanup()
"""

from __future__ import annotations

import subprocess
import shlex
from typing import List, Optional
from log import log


class IptablesManager:
    """Управление iptables правилами для nfqws."""

    def __init__(
        self,
        queue_num: int = 200,
        use_nftables: bool = False,
    ):
        """
        Args:
            queue_num: Номер NFQUEUE для направления трафика
            use_nftables: Если True, использовать nftables вместо iptables
        """
        self.queue_num = queue_num
        self.use_nftables = use_nftables
        self._rules_applied = False
        self._applied_rules: List[str] = []

    def _run_cmd(self, cmd: List[str], description: str = "") -> bool:
        """Выполняет команду iptables/nftables."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                if description:
                    log(f"✅ {description}", "DEBUG")
                return True
            else:
                error_msg = result.stderr.strip() if result.stderr else "unknown error"
                log(f"⚠ {description} failed: {error_msg}", "WARNING")
                return False
        except FileNotFoundError:
            log(f"⚠ Команда не найдена: {cmd[0]}", "WARNING")
            return False
        except subprocess.TimeoutExpired:
            log(f"⚠ Таймаут команды: {' '.join(cmd)}", "WARNING")
            return False
        except Exception as e:
            log(f"⚠ Ошибка выполнения {description}: {e}", "WARNING")
            return False

    def _parse_preset_rules(self, preset_content: str) -> List[dict]:
        """Парсит пресет и извлекает фильтры для iptables.

        Примеры:
            --filter-tcp-port=443   → {"proto": "tcp", "port": "443"}
            --filter-tcp-port=80    → {"proto": "tcp", "port": "80"}
            --filter-udp-port=53    → {"proto": "udp", "port": "53"}
        """
        rules = []
        for line in preset_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # TCP ports
            if "--filter-tcp-port=" in line.lower():
                port = line.split("--filter-tcp-port=", 1)[1].strip().split()[0]
                rules.append({"proto": "tcp", "port": port})

            # UDP ports
            elif "--filter-udp-port=" in line.lower():
                port = line.split("--filter-udp-port=", 1)[1].strip().split()[0]
                rules.append({"proto": "udp", "port": port})

        return rules

    def setup(self, preset_content: Optional[str] = None, ports: Optional[List[str]] = None) -> bool:
        """Настраивает iptables правила для nfqws.

        Args:
            preset_content: Содержимое пресета для автоматического извлечения портов
            ports: Явный список портов в формате "tcp:443", "udp:53"

        Returns:
            True если правила успешно применены
        """
        if self._rules_applied:
            log("iptables правила уже применены", "DEBUG")
            return True

        # Определяем правила
        target_ports = []
        if ports:
            for port_spec in ports:
                if ":" in port_spec:
                    proto, port = port_spec.split(":", 1)
                    target_ports.append({"proto": proto, "port": port})
                else:
                    # По умолчанию TCP
                    target_ports.append({"proto": "tcp", "port": port_spec})
        elif preset_content:
            target_ports = self._parse_preset_rules(preset_content)

        # Если нет специфичных портов, ловим весь TCP/UDP трафик
        if not target_ports:
            target_ports = [
                {"proto": "tcp", "port": "80"},
                {"proto": "tcp", "port": "443"},
            ]

        log(f"Настройка iptables для nfqws (queue={self.queue_num}): {target_ports}", "INFO")

        success = True

        for rule in target_ports:
            proto = rule["proto"]
            port = rule["port"]

            # IPv4 правила
            cmd = [
                "iptables", "-t", "mangle",
                "-I", "OUTPUT",
                "-p", proto,
                "--dport", str(port),
                "-j", "NFQUEUE",
                "--queue-num", str(self.queue_num),
                "--queue-bypass",
            ]
            if self._run_cmd(cmd, f"iptables: {proto}/{port} → NFQUEUE:{self.queue_num}"):
                self._applied_rules.append(f"iptables -t mangle -I OUTPUT -p {proto} --dport {port} -j NFQUEUE --queue-num {self.queue_num}")
            else:
                success = False

            # IPv6 правила (если ip6tables доступен)
            cmd_v6 = [
                "ip6tables", "-t", "mangle",
                "-I", "OUTPUT",
                "-p", proto,
                "--dport", str(port),
                "-j", "NFQUEUE",
                "--queue-num", str(self.queue_num),
                "--queue-bypass",
            ]
            if self._run_cmd(cmd_v6, f"ip6tables: {proto}/{port} → NFQUEUE:{self.queue_num}"):
                self._applied_rules.append(f"ip6tables -t mangle -I OUTPUT -p {proto} --dport {port} -j NFQUEUE --queue-num {self.queue_num}")

        self._rules_applied = success
        if success:
            log(f"✅ iptables правила применены ({len(self._applied_rules)} правил)", "INFO")
        else:
            log("⚠ Некоторые iptables правила не применены", "WARNING")

        return success

    def cleanup(self) -> bool:
        """Удаляет все применённые iptables правила.

        Returns:
            True если все правила успешно удалены
        """
        if not self._rules_applied and not self._applied_rules:
            return True  # Ничего не нужно чистить

        log("Очистка iptables правил nfqws...", "INFO")
        success = True

        # Удаляем правила в обратном порядке
        for rule in reversed(self._applied_rules):
            parts = shlex.split(rule)
            # Заменяем -I (insert) на -D (delete)
            if "-I" in parts:
                idx = parts.index("-I")
                parts[idx] = "-D"

            cmd = parts
            if not self._run_cmd(cmd, f"Удаление правила: {rule}"):
                success = False

        self._rules_applied = False
        self._applied_rules.clear()

        if success:
            log("✅ Все iptables правила удалены", "INFO")
        else:
            log("⚠ Некоторые iptables правила не удалены", "WARNING")

        return success

    def flush_all(self) -> bool:
        """Полная очистка таблицы mangle (аварийный режим).

        WARNING: Удаляет ВСЕ правила mangle, не только наши!
        """
        log("⚠ Аварийная очистка iptables mangle...", "WARNING")
        try:
            subprocess.run(
                ["iptables", "-t", "mangle", "-F"],
                capture_output=True, timeout=10
            )
            subprocess.run(
                ["ip6tables", "-t", "mangle", "-F"],
                capture_output=True, timeout=10
            )
            self._rules_applied = False
            self._applied_rules.clear()
            log("✅ Таблица mangle очищена", "INFO")
            return True
        except Exception as e:
            log(f"❌ Ошибка аварийной очистки: {e}", "ERROR")
            return False

    @staticmethod
    def is_available() -> bool:
        """Проверяет доступны ли iptables/ip6tables."""
        try:
            subprocess.run(["iptables", "--version"], capture_output=True, timeout=3)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def is_nftables_available() -> bool:
        """Проверяет доступен ли nft."""
        try:
            subprocess.run(["nft", "--version"], capture_output=True, timeout=3)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
