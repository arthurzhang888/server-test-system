import os
import re
import subprocess
from typing import Dict, Any, Optional

from .base import BaseDetector, DetectorMode


class ChassisDetector(BaseDetector):
    """Detect chassis/enclosure information.

    Uses sysfs (/sys/class/dmi/id/) and dmidecode to gather chassis
    information including type, manufacturer, serial numbers, asset tags,
    rack location, power state, LED status, and lock status.
    """

    # Chassis type mapping per DMI specification
    CHASSIS_TYPES = {
        1: "Other",
        2: "Unknown",
        3: "Desktop",
        4: "Low Profile Desktop",
        5: "Pizza Box",
        6: "Mini Tower",
        7: "Tower",
        8: "Portable",
        9: "Laptop",
        10: "Notebook",
        11: "Hand Held",
        12: "Docking Station",
        13: "All in One",
        14: "Sub Notebook",
        15: "Space-saving",
        16: "Lunch Box",
        17: "Main Server Chassis",
        18: "Expansion Chassis",
        19: "Sub Chassis",
        20: "Bus Expansion Chassis",
        21: "Peripheral Chassis",
        22: "RAID Chassis",
        23: "Rack Mount Chassis",
        24: "Sealed-case PC",
        25: "Multi-system Chassis",
        26: "Compact PCI",
        27: "Advanced TCA",
        28: "Blade",
        29: "Blade Enclosure",
        30: "Tablet",
        31: "Convertible",
        32: "Detachable",
        33: "IoT Gateway",
        34: "Embedded PC",
        35: "Mini PC",
        36: "Stick PC",
    }

    def detect_real(self) -> Dict[str, Any]:
        """Detect real chassis information via sysfs and dmidecode.

        Returns:
            Dictionary containing chassis information.
        """
        info = {
            "type": "Unknown",
            "type_raw": 0,
            "manufacturer": "Unknown",
            "model": "Unknown",
            "serial": "Unknown",
            "asset_tag": "Unknown",
            "service_tag": "Unknown",
            "rack_location": "Unknown",
            "power_state": "Unknown",
            "led_status": "Unknown",
            "lock_status": "Unknown",
            "version": "Unknown",
            "sku": "Unknown",
        }

        # Try sysfs first (no root required)
        dmi_path = "/sys/class/dmi/id"
        if os.path.exists(dmi_path):
            info["manufacturer"] = self._read_dmi_file(f"{dmi_path}/chassis_vendor")
            info["serial"] = self._read_dmi_file(f"{dmi_path}/chassis_serial")
            info["asset_tag"] = self._read_dmi_file(f"{dmi_path}/chassis_asset_tag")
            info["version"] = self._read_dmi_file(f"{dmi_path}/chassis_version")
            info["model"] = self._read_dmi_file(f"{dmi_path}/product_name")
            info["sku"] = self._read_dmi_file(f"{dmi_path}/product_sku")

            # Service tag is often same as asset tag or serial
            service_tag = self._read_dmi_file(f"{dmi_path}/product_serial")
            if service_tag != "Unknown":
                info["service_tag"] = service_tag

        # Try dmidecode for more details including chassis type
        dmi_info = self._get_dmidecode_info()
        info.update(dmi_info)

        # Detect power state from ACPI or other sources
        info["power_state"] = self._detect_power_state()

        # Detect LED status if available
        info["led_status"] = self._detect_led_status()

        # Detect lock status if available
        info["lock_status"] = self._detect_lock_status()

        # Try to determine rack location from various sources
        info["rack_location"] = self._detect_rack_location()

        return info

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated chassis data for testing."""
        return {
            "type": "Rack Mount Chassis",
            "type_raw": 23,
            "manufacturer": "Dell Inc.",
            "model": "PowerEdge R750",
            "serial": "C8J7XH2",
            "asset_tag": "SERVER-001",
            "service_tag": "C8J7XH2",
            "rack_location": "Rack-A12-U24",
            "power_state": "On",
            "led_status": "Green",
            "lock_status": "Unlocked",
            "version": "1.0",
            "sku": "PE-R750-BASE",
        }

    def _read_dmi_file(self, path: str) -> str:
        """Read DMI file from sysfs."""
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    value = f.read().strip()
                    return value if value else "Unknown"
        except (IOError, FileNotFoundError, PermissionError):
            pass
        return "Unknown"

    def _get_dmidecode_info(self) -> Dict[str, Any]:
        """Get chassis info via dmidecode."""
        info = {
            "type": "Unknown",
            "type_raw": 0,
        }

        try:
            result = subprocess.run(
                ["dmidecode", "-t", "3"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                output = result.stdout

                # Parse chassis type
                type_match = re.search(r'Type:\s*(\d+|\w+)', output, re.IGNORECASE)
                if type_match:
                    type_str = type_match.group(1)
                    if type_str.isdigit():
                        type_num = int(type_str)
                        info["type_raw"] = type_num
                        info["type"] = self.CHASSIS_TYPES.get(type_num, "Unknown")

                # Parse manufacturer
                mfg_match = re.search(r'Manufacturer:\s*(.+)', output, re.IGNORECASE)
                if mfg_match:
                    info["manufacturer"] = mfg_match.group(1).strip()

                # Parse version
                ver_match = re.search(r'Version:\s*(.+)', output, re.IGNORECASE)
                if ver_match:
                    info["version"] = ver_match.group(1).strip()

                # Parse serial
                serial_match = re.search(r'Serial Number:\s*(.+)', output, re.IGNORECASE)
                if serial_match:
                    info["serial"] = serial_match.group(1).strip()

                # Parse asset tag
                asset_match = re.search(r'Asset Tag:\s*(.+)', output, re.IGNORECASE)
                if asset_match:
                    info["asset_tag"] = asset_match.group(1).strip()

                # Parse lock status from dmidecode
                lock_match = re.search(r'Lock:\s*(Present|Not Present)', output, re.IGNORECASE)
                if lock_match:
                    info["lock_status"] = "Locked" if lock_match.group(1).lower() == "present" else "Unlocked"

                # Parse power state if available
                power_match = re.search(r'Power Supply State:\s*(\w+)', output, re.IGNORECASE)
                if power_match:
                    info["power_state"] = power_match.group(1).strip()

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return info

    def _detect_power_state(self) -> str:
        """Detect system power state."""
        # Check ACPI power state
        acpi_path = "/sys/power/state"
        if os.path.exists(acpi_path):
            try:
                with open(acpi_path, "r") as f:
                    states = f.read().strip()
                    # If we can read this, system is likely on
                    if states:
                        return "On"
            except (IOError, PermissionError):
                pass

        # Check if ACPI is available
        if os.path.exists("/sys/firmware/acpi"):
            return "On"

        # Default to unknown
        return "Unknown"

    def _detect_led_status(self) -> str:
        """Detect chassis LED status if available."""
        # Some systems expose LED status via sysfs
        led_paths = [
            "/sys/class/leds/status_led/brightness",
            "/sys/class/leds/identify/brightness",
        ]

        for led_path in led_paths:
            if os.path.exists(led_path):
                try:
                    with open(led_path, "r") as f:
                        brightness = int(f.read().strip())
                        return "On" if brightness > 0 else "Off"
                except (IOError, ValueError, PermissionError):
                    continue

        # Check for Dell-specific LED status via ipmitool if available
        try:
            result = subprocess.run(
                ["ipmitool", "sdr", "type", "0x09"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and "ok" in result.stdout.lower():
                return "Green"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return "Unknown"

    def _detect_lock_status(self) -> str:
        """Detect chassis lock status."""
        # Most systems don't expose this via sysfs
        # Return Unknown unless we have specific information
        return "Unknown"

    def _detect_rack_location(self) -> str:
        """Detect rack location from various sources."""
        # Try to get from IPMI fru if available
        try:
            result = subprocess.run(
                ["ipmitool", "fru", "print"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # Look for rack location in FRU data
                for line in result.stdout.splitlines():
                    if "rack" in line.lower() or "location" in line.lower():
                        match = re.search(r':\s*(.+)', line)
                        if match:
                            return match.group(1).strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Try to construct from asset tag or other identifiers
        return "Unknown"
