import subprocess
import re
from typing import Dict, List, Any

from .base import BaseDetector, DetectorMode


class SensorDetector(BaseDetector):
    """Detect temperature and fan sensors.

    Uses IPMI sensor data to get temperature and fan readings.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect sensors via IPMI."""
        temperatures = []
        fans = []

        try:
            # Get all sensor data
            result = subprocess.run(
                ["ipmitool", "sdr", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                temperatures, fans = self._parse_ipmi_sensor_output(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return {
            "sensors": {
                "temperatures": temperatures,
                "fans": fans
            },
            "threshold_alerts": [],
            "sensor_count": {
                "temperatures": len(temperatures),
                "fans": len(fans)
            }
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated sensor data."""
        return {
            "sensors": {
                "temperatures": [
                    {"name": "CPU0 Temp", "value": 45, "unit": "C", "status": "ok"},
                    {"name": "CPU1 Temp", "value": 43, "unit": "C", "status": "ok"},
                    {"name": "Inlet Temp", "value": 25, "unit": "C", "status": "ok"},
                    {"name": "PCH Temp", "value": 52, "unit": "C", "status": "ok"},
                    {"name": "PSU1 Temp", "value": 35, "unit": "C", "status": "ok"},
                    {"name": "PSU2 Temp", "value": 33, "unit": "C", "status": "ok"}
                ],
                "fans": [
                    {"name": "Fan 1 Front", "rpm": 3200, "percent": 40, "status": "ok"},
                    {"name": "Fan 2 Front", "rpm": 3150, "percent": 40, "status": "ok"},
                    {"name": "Fan 3 Front", "rpm": 3100, "percent": 40, "status": "ok"},
                    {"name": "Fan 4 Rear", "rpm": 3300, "percent": 42, "status": "ok"},
                    {"name": "Fan 5 Rear", "rpm": 3250, "percent": 42, "status": "ok"}
                ]
            },
            "threshold_alerts": [],
            "sensor_count": {
                "temperatures": 6,
                "fans": 5
            }
        }

    def _parse_ipmi_sensor_output(self, output: str) -> (List[Dict], List[Dict]):
        """Parse IPMI sensor output for temperatures and fans."""
        temperatures = []
        fans = []

        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            # Example: "CPU0 Temp      | 45h | ok  |  3.1 | 45 degrees C"
            parts = [p.strip() for p in line.split("|")]

            if len(parts) < 2:
                continue

            name = parts[0]
            reading = parts[-1] if len(parts) > 4 else ""

            # Parse temperature
            if "degrees" in reading.lower() or "temp" in name.lower():
                temp_match = re.search(r'(\d+)\s*degrees', reading, re.IGNORECASE)
                if temp_match:
                    temp = {
                        "name": name.strip(),
                        "value": int(temp_match.group(1)),
                        "unit": "C",
                        "status": "ok" if "ok" in line.lower() else "unknown"
                    }
                    temperatures.append(temp)

            # Parse fan
            elif "rpm" in reading.lower() or "fan" in name.lower():
                rpm_match = re.search(r'(\d+)\s*RPM', reading, re.IGNORECASE)
                if rpm_match:
                    rpm_val = int(rpm_match.group(1))
                    fan = {
                        "name": name.strip(),
                        "rpm": rpm_val,
                        "percent": min(100, max(0, rpm_val // 100)),  # Rough estimate
                        "status": "ok" if "ok" in line.lower() else "unknown"
                    }
                    fans.append(fan)

        return temperatures, fans
