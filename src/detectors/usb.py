import subprocess
import re
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class USBDetector(BaseDetector):
    """Detect USB controllers and connected devices.

    Uses lsusb to gather USB bus, controller, and device information.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect USB via lsusb."""
        controllers = []
        devices = []

        try:
            result = subprocess.run(
                ["lsusb"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                controllers, devices = self._parse_lsusb_output(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return {
            "controllers": controllers,
            "devices": devices,
            "controller_count": len(controllers),
            "device_count": len(devices)
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated USB data."""
        return {
            "controllers": [
                {
                    "bus": 1,
                    "id": "1d6b:0002",
                    "vendor": "Linux Foundation",
                    "product": "2.0 root hub",
                    "speed": "480M",
                    "usb_version": "2.0"
                },
                {
                    "bus": 2,
                    "id": "1d6b:0003",
                    "vendor": "Linux Foundation",
                    "product": "3.0 root hub",
                    "speed": "5000M",
                    "usb_version": "3.0"
                }
            ],
            "devices": [
                {
                    "bus": 1,
                    "device": 2,
                    "id": "046b:ff01",
                    "vendor": "American Power Conversion",
                    "product": "UPS",
                    "speed": "1.5M",
                    "class": "HID",
                    "connected": True
                },
                {
                    "bus": 2,
                    "device": 3,
                    "id": "0781:5567",
                    "vendor": "SanDisk Corp.",
                    "product": "Cruzer Blade",
                    "speed": "480M",
                    "class": "Mass Storage",
                    "connected": True
                }
            ],
            "controller_count": 2,
            "device_count": 2
        }

    def _parse_lsusb_output(self, output: str) -> (List[Dict], List[Dict]):
        """Parse lsusb output into controllers and devices."""
        controllers = []
        devices = []

        for line in output.strip().split("\n"):
            # Parse: Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
            match = re.match(
                r'Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+([0-9a-f]{4}):([0-9a-f]{4})\s+(.+)',
                line,
                re.IGNORECASE
            )

            if match:
                bus = int(match.group(1))
                device = int(match.group(2))
                vendor_id = match.group(3).lower()
                product_id = match.group(4).lower()
                name = match.group(5).strip()

                # Parse vendor and product from name
                parts = name.split(" ", 1)
                vendor = parts[0] if parts else "Unknown"
                product = parts[1] if len(parts) > 1 else "Unknown"

                usb_id = f"{vendor_id}:{product_id}"

                # Determine if controller (root hub) or device
                if "root hub" in name.lower():
                    # Estimate USB version from product ID
                    usb_version = "2.0"
                    speed = "480M"
                    if product_id == "0003":
                        usb_version = "3.0"
                        speed = "5000M"
                    elif product_id == "0004":
                        usb_version = "3.1"
                        speed = "10000M"

                    controllers.append({
                        "bus": bus,
                        "id": usb_id,
                        "vendor": vendor,
                        "product": product,
                        "speed": speed,
                        "usb_version": usb_version
                    })
                else:
                    # Regular USB device
                    # Estimate speed (would need lsusb -v for accurate speed)
                    device_class = self._guess_device_class(name)

                    devices.append({
                        "bus": bus,
                        "device": device,
                        "id": usb_id,
                        "vendor": vendor,
                        "product": product,
                        "speed": "Unknown",  # Would need detailed query
                        "class": device_class,
                        "connected": True
                    })

        return controllers, devices

    def _guess_device_class(self, name: str) -> str:
        """Guess device class from product name."""
        name_lower = name.lower()

        if any(kw in name_lower for kw in ["keyboard", "mouse", "hid"]):
            return "HID"
        elif any(kw in name_lower for kw in ["storage", "disk", "flash", "ssd"]):
            return "Mass Storage"
        elif any(kw in name_lower for kw in ["camera", "webcam", "video"]):
            return "Video"
        elif any(kw in name_lower for kw in ["audio", "sound", "headset", "mic"]):
            return "Audio"
        elif any(kw in name_lower for kw in ["ups", "battery", "power"]):
            return "Power"
        elif any(kw in name_lower for kw in ["ethernet", "network", "wifi", "wireless"]):
            return "Network"
        elif any(kw in name_lower for kw in ["bluetooth"]):
            return "Bluetooth"
        elif any(kw in name_lower for kw in ["hub"]):
            return "Hub"
        else:
            return "Unknown"
