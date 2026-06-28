import subprocess
import re
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class IBDetector(BaseDetector):
    """Detect InfiniBand network devices."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect InfiniBand via ibstat."""
        devices = []

        try:
            result = subprocess.run(
                ["ibstat"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                devices = self._parse_ibstat_output(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return {
            "present": len(devices) > 0,
            "device_count": len(devices),
            "devices": devices
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated IB data."""
        return {
            "present": True,
            "device_count": 2,
            "devices": [
                {
                    "name": "mlx5_0",
                    "guid": "0x0002c90300a0e7c0",
                    "vendor": "Mellanox",
                    "model": "ConnectX-6",
                    "firmware_version": "20.28.4512",
                    "ports": [
                        {
                            "port_num": 1,
                            "state": "Active",
                            "phys_state": "LinkUp",
                            "rate": "200 Gb/sec",
                            "lid": 12
                        }
                    ]
                },
                {
                    "name": "mlx5_1",
                    "guid": "0x0002c90300a0e7c1",
                    "vendor": "Mellanox",
                    "model": "ConnectX-6",
                    "firmware_version": "20.28.4512",
                    "ports": [
                        {
                            "port_num": 1,
                            "state": "Active",
                            "phys_state": "LinkUp",
                            "rate": "200 Gb/sec",
                            "lid": 13
                        }
                    ]
                }
            ]
        }

    def _parse_ibstat_output(self, output: str) -> List[Dict]:
        """Parse ibstat output."""
        devices = []
        current_device = None

        for line in output.split("\n"):
            if "CA '" in line:
                match = re.search(r"CA '(\w+)'", line)
                if match:
                    if current_device:
                        devices.append(current_device)
                    current_device = {
                        "name": match.group(1),
                        "guid": "",
                        "vendor": "Mellanox",
                        "model": "Unknown",
                        "firmware_version": "",
                        "ports": []
                    }
            elif current_device:
                if "CA type:" in line:
                    current_device["model"] = line.split(":")[1].strip()
                elif "Firmware version:" in line:
                    current_device["firmware_version"] = line.split(":")[1].strip()

        if current_device:
            devices.append(current_device)

        return devices
