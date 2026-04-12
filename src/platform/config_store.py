"""Linux config store — JSON-based replacement for Windows Registry."""

from __future__ import annotations

import json
import os
from typing import Any


class LinuxConfigStore:
    """
    Эмулирует сохранение настроек окна и других ключей через JSON.
    Используется на Linux вместо winreg.
    """

    def __init__(self, config_dir: str | None = None, filename: str = "registry_config.json"):
        if config_dir is None:
            config_dir = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
            config_dir = os.path.join(config_dir, "zapret2")

        self.config_dir = config_dir
        self.config_file = os.path.join(self.config_dir, filename)
        self._ensure_dir()
        self._load()

    def _ensure_dir(self) -> None:
        os.makedirs(self.config_dir, exist_ok=True)

    def _load(self) -> None:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.data: dict[str, Any] = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.data = {}
        else:
            self.data = {}

    def _save(self) -> None:
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except OSError as e:
            try:
                from log import log
                log(f"Ошибка сохранения конфига: {e}", "WARNING")
            except ImportError:
                print(f"[WARNING] Ошибка сохранения конфига: {e}")

    def get_value(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set_value(self, key: str, value: Any) -> None:
        self.data[key] = value
        self._save()

    def delete_value(self, key: str) -> bool:
        if key in self.data:
            del self.data[key]
            self._save()
            return True
        return False

    def get_dword(self, key: str, default: int = 0) -> int:
        """Эмуляция REG_DWORD для совместимости с кодом Windows."""
        try:
            return int(self.data.get(key, default))
        except (TypeError, ValueError):
            return default


# Singleton
linux_store: LinuxConfigStore | None = None


def get_linux_store() -> LinuxConfigStore:
    global linux_store
    if linux_store is None:
        linux_store = LinuxConfigStore()
    return linux_store
