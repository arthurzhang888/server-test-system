import subprocess
import re
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class NVMeHealthDetector(BaseDetector):
    """Detect NVMe device health information using nvme-cli.

    Retrieves SMART log data including health percentage, temperature,
    available spare, data read/written, power statistics, and error counts.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect real NVMe health information using nvme-cli."""
        devices = self._list_nvme_devices()
        device_health = []

        for device in devices:
            health = self._get_smart_log(device)
            if health:
                device_health.append(health)

        return {
            "devices": device_health,
            "device_count": len(device_health),
            "overall_health": self._calculate_overall_health(device_health),
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated NVMe health data for testing."""
        devices = [
            {
                "device": "nvme0",
                "model": "Samsung PM1735",
                "serial": "S123456789",
                "health_percentage": 98,
                "temperature_celsius": 45,
                "available_spare_percentage": 100,
                "data_read_tb": 12.5,
                "data_written_tb": 8.3,
                "power_on_hours": 8760,
                "power_cycles": 150,
                "media_errors": 0,
                "unsafe_shutdowns": 3,
                "predicted_life_remaining_percentage": 95,
                "critical_warning": 0,
            },
            {
                "device": "nvme1",
                "model": "Intel P4610",
                "serial": "I987654321",
                "health_percentage": 92,
                "temperature_celsius": 52,
                "available_spare_percentage": 98,
                "data_read_tb": 45.2,
                "data_written_tb": 32.1,
                "power_on_hours": 17520,
                "power_cycles": 230,
                "media_errors": 2,
                "unsafe_shutdowns": 7,
                "predicted_life_remaining_percentage": 88,
                "critical_warning": 0,
            },
        ]

        return {
            "devices": devices,
            "device_count": len(devices),
            "overall_health": self._calculate_overall_health(devices),
        }

    def _list_nvme_devices(self) -> List[str]:
        """List available NVMe devices using nvme list command."""
        devices = []
        try:
            result = subprocess.run(
                ["nvme", "list", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                for device in data.get("Devices", []):
                    devices.append(device.get("DevicePath", "").replace("/dev/", ""))
        except Exception:
            # Fallback: try to find NVMe devices manually
            try:
                import os
                for entry in os.listdir("/sys/block"):
                    if entry.startswith("nvme"):
                        devices.append(entry)
            except Exception:
                pass

        return devices

    def _get_smart_log(self, device: str) -> Dict[str, Any]:
        """Get SMART log data for a specific NVMe device."""
        try:
            result = subprocess.run(
                ["nvme", "smart-log", f"/dev/{device}", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                return self._parse_smart_log(device, data)
        except Exception:
            pass
        return None

    def _parse_smart_log(self, device: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse NVMe SMART log data into standardized format."""
        device_info = self._get_device_info(device)

        # NVMe returns values that need conversion
        # Data units are in 1000 blocks of 512 bytes
        data_units_read = data.get("data_units_read", 0)
        data_units_written = data.get("data_units_written", 0)

        # Convert to TB (1000 * 512 bytes per unit = 512000 bytes = 0.000512 GB)
        data_read_tb = round(data_units_read * 512000 / (1024**4), 2)
        data_written_tb = round(data_units_written * 512000 / (1024**4), 2)

        # Temperature is in Kelvin, convert to Celsius
        temperature = data.get("temperature", 0)
        if temperature > 273:
            temperature_celsius = temperature - 273
        else:
            temperature_celsius = temperature

        # Percentage used is the inverse of health
        percentage_used = data.get("percentage_used", 0)
        health_percentage = max(0, 100 - percentage_used)

        # Available spare
        available_spare = data.get("available_spare", 100)

        # Power statistics
        power_on_hours = data.get("power_on_hours", 0)
        power_cycles = data.get("power_cycles", 0)

        # Error statistics
        media_errors = data.get("media_errors", 0)
        unsafe_shutdowns = data.get("unsafe_shutdowns", 0)

        # Critical warning flags
        critical_warning = data.get("critical_warning", 0)

        # Predicted remaining life (based on percentage used)
        predicted_life_remaining = max(0, 100 - percentage_used)

        return {
            "device": device,
            "model": device_info.get("model", "Unknown"),
            "serial": device_info.get("serial", "Unknown"),
            "health_percentage": health_percentage,
            "temperature_celsius": temperature_celsius,
            "available_spare_percentage": available_spare,
            "data_read_tb": data_read_tb,
            "data_written_tb": data_written_tb,
            "power_on_hours": power_on_hours,
            "power_cycles": power_cycles,
            "media_errors": media_errors,
            "unsafe_shutdowns": unsafe_shutdowns,
            "predicted_life_remaining_percentage": predicted_life_remaining,
            "critical_warning": critical_warning,
        }

    def _get_device_info(self, device: str) -> Dict[str, str]:
        """Get model and serial information for a device."""
        info = {"model": "Unknown", "serial": "Unknown"}
        try:
            result = subprocess.run(
                ["nvme", "id-ctrl", f"/dev/{device}", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                info["model"] = data.get("mn", "Unknown").strip()
                info["serial"] = data.get("sn", "Unknown").strip()
        except Exception:
            pass
        return info

    def _calculate_overall_health(self, devices: List[Dict[str, Any]]) -> str:
        """Calculate overall health status from device health data."""
        if not devices:
            return "unknown"

        # Check for critical warnings
        for device in devices:
            if device.get("critical_warning", 0) > 0:
                return "critical"

        # Check for media errors
        for device in devices:
            if device.get("media_errors", 0) > 0:
                return "degraded"

        # Check health percentages
        min_health = min(d.get("health_percentage", 100) for d in devices)
        if min_health < 50:
            return "poor"
        elif min_health < 80:
            return "fair"
        elif min_health < 90:
            return "good"
        else:
            return "excellent"
