import subprocess
import shutil
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class PCIeDetector(BaseDetector):
    """Detect PCIe devices, slots, and bandwidth information."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect real PCIe devices using lspci command.

        Returns:
            Dictionary containing detected PCIe device information.
            If lspci is not available, returns empty device list.
        """
        devices = self._get_lspci_devices()
        return {
            "devices": devices,
            "device_count": len(devices),
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated PCIe device data for testing."""
        return {
            "devices": [
                {"slot": "00:00.0", "type": "Host bridge", "vendor": "Intel"},
                {"slot": "01:00.0", "type": "VGA controller", "vendor": "NVIDIA"},
                {"slot": "02:00.0", "type": "Ethernet controller", "vendor": "Intel"},
            ],
            "device_count": 3,
        }

    def _get_lspci_devices(self) -> List[Dict[str, str]]:
        """Execute lspci command and parse output.

        Returns:
            List of device dictionaries with slot, type, and vendor info.
            Returns empty list if lspci is not available or fails.
        """
        if not shutil.which("lspci"):
            return []

        try:
            result = subprocess.run(
                ["lspci"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return []

            return self._parse_lspci_output(result.stdout)
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            return []

    def _parse_lspci_output(self, output: str) -> List[Dict[str, str]]:
        """Parse lspci command output into device dictionaries.

        Args:
            output: Raw output from lspci command.

        Returns:
            List of parsed device dictionaries.
        """
        devices = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            # lspci output format: "00:00.0 Host bridge: Intel Corporation ..."
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue

            slot = parts[0]
            remainder = parts[2]

            # Split by colon to separate type and vendor
            type_vendor = remainder.split(":", 1)
            device_type = type_vendor[0].strip()
            vendor = type_vendor[1].strip().split()[0] if len(type_vendor) > 1 else "Unknown"

            devices.append({
                "slot": slot,
                "type": device_type,
                "vendor": vendor,
            })

        return devices
