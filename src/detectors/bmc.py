import subprocess
import re
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class BMCDetector(BaseDetector):
    """Detect BMC (Baseboard Management Controller) information.

    Supports IPMI status detection, BMC version, IP address, and sensor readings.
    In real mode, attempts to use ipmitool command if available.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect real BMC information using ipmitool if available.

        Returns:
            Dictionary containing BMC information, or empty dict if ipmitool is unavailable.
        """
        result = {
            "bmc_version": "",
            "ipmi_enabled": False,
            "bmc_ip": "",
            "sensors": [],
        }

        # Check if ipmitool is available
        if not self._is_ipmitool_available():
            return result

        try:
            # Get BMC version
            result["bmc_version"] = self._get_bmc_version()

            # Get BMC IP address
            result["bmc_ip"] = self._get_bmc_ip()

            # Get sensor readings
            result["sensors"] = self._get_sensors()

            # IPMI is considered enabled if we got any data
            result["ipmi_enabled"] = bool(
                result["bmc_version"] or result["sensors"]
            )

        except Exception:
            # If any command fails, return partial/empty data
            pass

        return result

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated BMC data for testing."""
        return {
            "bmc_version": "2.45",
            "ipmi_enabled": True,
            "bmc_ip": "192.168.1.100",
            "sensors": [
                {"name": "CPU Temp", "value": 45, "unit": "C"},
                {"name": "Fan 1", "value": 3000, "unit": "RPM"},
            ],
        }

    def _is_ipmitool_available(self) -> bool:
        """Check if ipmitool command is available on the system."""
        try:
            subprocess.run(
                ["which", "ipmitool"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _get_bmc_version(self) -> str:
        """Get BMC firmware version using ipmitool."""
        try:
            result = subprocess.run(
                ["ipmitool", "mc", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Parse version from output
                for line in result.stdout.splitlines():
                    if "Firmware Revision" in line:
                        match = re.search(r"Firmware Revision\s*:\s*([\d.]+)", line)
                        if match:
                            return match.group(1)
            return ""
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ""

    def _get_bmc_ip(self) -> str:
        """Get BMC IP address using ipmitool."""
        try:
            result = subprocess.run(
                ["ipmitool", "lan", "print", "1"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Parse IP from output
                for line in result.stdout.splitlines():
                    if "IP Address" in line and "Source" not in line:
                        match = re.search(r"IP Address\s*:\s*([\d.]+)", line)
                        if match:
                            return match.group(1)
            return ""
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ""

    def _get_sensors(self) -> List[Dict[str, Any]]:
        """Get sensor readings using ipmitool."""
        sensors = []
        try:
            result = subprocess.run(
                ["ipmitool", "sensor", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.split("|")
                    if len(parts) >= 4:
                        name = parts[0].strip()
                        value_str = parts[1].strip()
                        unit = parts[2].strip() if len(parts) > 2 else ""

                        # Try to parse numeric value
                        try:
                            value = float(value_str)
                            sensors.append({
                                "name": name,
                                "value": value,
                                "unit": unit if unit else "raw",
                            })
                        except ValueError:
                            # Skip non-numeric readings
                            continue
            return sensors
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return sensors
