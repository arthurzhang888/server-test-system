"""Base interface for platform-specific hardware detection."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class PlatformInterface(ABC):
    """Abstract base class for platform-specific operations.

    Provides abstraction for:
    - Command execution
    - Hardware detection methods
    - Path handling
    - System information gathering
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return platform name (linux, windows, etc)."""
        pass

    @abstractmethod
    def execute_command(
        self,
        command: List[str],
        timeout: int = 30,
        capture_output: bool = True
    ) -> tuple[int, str, str]:
        """Execute a system command.

        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        pass

    @abstractmethod
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information."""
        pass

    @abstractmethod
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory information."""
        pass

    @abstractmethod
    def get_storage_devices(self) -> List[Dict[str, Any]]:
        """Get storage device list."""
        pass

    @abstractmethod
    def get_network_interfaces(self) -> List[Dict[str, Any]]:
        """Get network interface list."""
        pass

    @abstractmethod
    def get_gpu_info(self) -> List[Dict[str, Any]]:
        """Get GPU information."""
        pass

    @abstractmethod
    def get_pci_devices(self) -> List[Dict[str, Any]]:
        """Get PCI device list."""
        pass

    @abstractmethod
    def get_usb_devices(self) -> List[Dict[str, Any]]:
        """Get USB device list."""
        pass

    @abstractmethod
    def get_dmi_info(self, dmi_type: int) -> Dict[str, str]:
        """Get DMI/SMBIOS information."""
        pass

    @abstractmethod
    def read_sysctl(self, key: str) -> Optional[str]:
        """Read system parameter (sysctl on BSD/macOS, registry on Windows)."""
        pass

    @abstractmethod
    def path_exists(self, path: str) -> bool:
        """Check if path exists (handles platform-specific paths)."""
        pass

    @abstractmethod
    def read_file(self, path: str, default: str = "") -> str:
        """Read file contents (if applicable for platform)."""
        pass
