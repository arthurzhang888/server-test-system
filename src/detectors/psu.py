import subprocess
import re
from typing import Dict, List, Any

from .base import BaseDetector, DetectorMode


class PSUDetector(BaseDetector):
    """Detect Power Supply Units (PSU) status.

    Uses IPMI sensor data or lm-sensors to get PSU information.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect PSU information via IPMI."""
        psus = []

        # Try IPMI first
        try:
            result = subprocess.run(
                ["ipmitool", "sdr", "type", "Power Supply"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                psus = self._parse_ipmi_psu_output(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Calculate totals
        total_capacity = sum(
            psu.get("rated_capacity_watts", 0) for psu in psus
        ) or sum(psu.get("output_watts", 0) * 2 for psu in psus)

        total_output = sum(psu.get("output_watts", 0) for psu in psus)

        load_percent = 0
        if total_capacity > 0:
            load_percent = round((total_output / total_capacity) * 100, 1)

        return {
            "psu_count": len(psus),
            "redundant": len(psus) >= 2,
            "psus": psus,
            "total_capacity_watts": total_capacity,
            "total_output_watts": total_output,
            "load_percent": load_percent
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated PSU data."""
        return {
            "psu_count": 2,
            "redundant": True,
            "psus": [
                {
                    "id": 1,
                    "present": True,
                    "status": "OK",
                    "input_voltage": 220,
                    "input_voltage_status": "ok",
                    "output_watts": 450,
                    "temperature_c": 35,
                    "fan_rpm": 3200,
                    "model": "DPS-750AB-1",
                    "serial": "ABC123456",
                    "part_number": "865408-B21"
                },
                {
                    "id": 2,
                    "present": True,
                    "status": "OK",
                    "input_voltage": 220,
                    "input_voltage_status": "ok",
                    "output_watts": 420,
                    "temperature_c": 33,
                    "fan_rpm": 3100,
                    "model": "DPS-750AB-1",
                    "serial": "ABC123457",
                    "part_number": "865408-B21"
                }
            ],
            "total_capacity_watts": 1500,
            "total_output_watts": 870,
            "load_percent": 58
        }

    def _parse_ipmi_psu_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse IPMI power supply sensor output."""
        psus = []

        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            # Example line: "PSU1 Status | 01h | ok  | 10.1 | Presence detected"
            parts = [p.strip() for p in line.split("|")]

            if len(parts) >= 2:
                name = parts[0]
                status = parts[2] if len(parts) > 2 else "unknown"

                # Extract PSU ID from name
                psu_id = 1
                id_match = re.search(r'PSU\s*(\d+)', name, re.IGNORECASE)
                if id_match:
                    psu_id = int(id_match.group(1))

                psu = {
                    "id": psu_id,
                    "present": "presence" in line.lower() or status == "ok",
                    "status": "OK" if status == "ok" else status,
                    "input_voltage": 0,
                    "input_voltage_status": "unknown",
                    "output_watts": 0,
                    "temperature_c": 0,
                    "fan_rpm": 0,
                    "model": "Unknown"
                }
                psus.append(psu)

        return psus
