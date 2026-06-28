"""Platform abstraction layer for cross-platform hardware detection."""

import sys
from typing import Optional

from .base import PlatformInterface
from .linux import LinuxPlatform
from .windows import WindowsPlatform


def get_platform() -> PlatformInterface:
    """Get platform interface for current OS."""
    if sys.platform == "win32":
        return WindowsPlatform()
    else:
        return LinuxPlatform()


__all__ = ["PlatformInterface", "LinuxPlatform", "WindowsPlatform", "get_platform"]
