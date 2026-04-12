"""XDG Autostart support for Linux.

Creates/removes .desktop files in ~/.config/autostart/ for Zapret2.
"""

from __future__ import annotations

import os
import sys
from typing import Optional
from log import log

IS_LINUX = sys.platform.startswith("linux")


class XDGAutostartManager:
    """Manages XDG autostart entries for Linux."""

    def __init__(
        self,
        app_name: str = "Zapret2",
        exec_path: Optional[str] = None,
        icon_path: Optional[str] = None,
    ):
        self.app_name = app_name
        self.exec_path = exec_path or sys.executable
        self.icon_path = icon_path

        # XDG autostart directory
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        self.autostart_dir = os.path.join(xdg_config_home, "autostart")
        self.desktop_file = os.path.join(self.autostart_dir, f"{app_name.lower()}.desktop")

    def _ensure_dir(self) -> bool:
        """Ensure autostart directory exists."""
        try:
            os.makedirs(self.autostart_dir, exist_ok=True)
            return True
        except OSError as e:
            log(f"Failed to create autostart dir: {e}", "ERROR")
            return False

    def is_enabled(self) -> bool:
        """Check if autostart is enabled (desktop file exists)."""
        return os.path.exists(self.desktop_file)

    def enable(self) -> bool:
        """Create .desktop file for autostart."""
        if not IS_LINUX:
            log("XDG autostart is Linux-only", "DEBUG")
            return False

        if not self._ensure_dir():
            return False

        # Determine the command to run
        if getattr(sys, "frozen", False):
            # Running as PyInstaller bundle
            exec_cmd = sys.executable
        else:
            # Running as script
            script_path = os.path.abspath(sys.argv[0])
            exec_cmd = f"{sys.executable} {script_path}"

        desktop_content = f"""[Desktop Entry]
Type=Application
Name={self.app_name}
Comment=DPI Bypass Tool
Exec={exec_cmd} --tray
Icon={self.icon_path or ''}
Terminal=false
Categories=Network;
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
"""

        try:
            with open(self.desktop_file, "w", encoding="utf-8") as f:
                f.write(desktop_content)
            log(f"✅ XDG autostart enabled: {self.desktop_file}", "INFO")
            return True
        except OSError as e:
            log(f"Failed to write desktop file: {e}", "ERROR")
            return False

    def disable(self) -> bool:
        """Remove .desktop file."""
        if not IS_LINUX:
            return True

        try:
            if os.path.exists(self.desktop_file):
                os.remove(self.desktop_file)
                log(f"✅ XDG autostart disabled: {self.desktop_file}", "INFO")
            return True
        except OSError as e:
            log(f"Failed to remove desktop file: {e}", "ERROR")
            return False


# Singleton instance
_xdg_autostart: Optional[XDGAutostartManager] = None


def get_xdg_autostart_manager() -> XDGAutostartManager:
    """Get or create XDG autostart manager."""
    global _xdg_autostart
    if _xdg_autostart is None:
        _xdg_autostart = XDGAutostartManager()
    return _xdg_autostart
