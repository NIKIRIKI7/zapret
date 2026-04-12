"""OS detection and platform constants."""

import sys

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"


def get_os_name() -> str:
    """Returns platform name: 'windows', 'linux', or 'unknown'."""
    if IS_WINDOWS:
        return "windows"
    if IS_LINUX:
        return "linux"
    return "unknown"


def is_admin_capable() -> bool:
    """Check if we can potentially get admin rights.
    
    Windows: Always possible (with UAC prompt).
    Linux: Requires pkexec/polkit or already root.
    """
    if IS_WINDOWS:
        return True
    if IS_LINUX:
        import os
        return os.geteuid() == 0  # Already root
    return False
