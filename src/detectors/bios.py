import os
import re
import subprocess
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class BIOSDetector(BaseDetector):
    """Detect BIOS/UEFI firmware information.

    Uses dmidecode or sysfs to gather BIOS, system, and secure boot info.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect BIOS info via dmidecode and sysfs."""
        info = {
            "type": "Unknown",
            "vendor": "Unknown",
            "version": "Unknown",
            "date": "Unknown",
            "rom_size_mb": 0,
            "characteristics": [],
            "secure_boot": {
                "supported": False,
                "enabled": False,
                "mode": "unknown"
            },
            "boot_mode": "unknown",
            "system_serial": "Unknown",
            "system_uuid": "Unknown",
            "sku_number": "Unknown",
            "family": "Unknown"
        }

        # Try sysfs first (no root required)
        dmi_path = "/sys/class/dmi/id"
        if os.path.exists(dmi_path):
            info["vendor"] = self._read_dmi_file(f"{dmi_path}/bios_vendor")
            info["version"] = self._read_dmi_file(f"{dmi_path}/bios_version")
            info["date"] = self._read_dmi_file(f"{dmi_path}/bios_date")
            info["system_serial"] = self._read_dmi_file(f"{dmi_path}/product_serial")
            info["system_uuid"] = self._read_dmi_file(f"{dmi_path}/product_uuid")
            info["sku_number"] = self._read_dmi_file(f"{dmi_path}/product_sku")
            info["family"] = self._read_dmi_file(f"{dmi_path}/product_family")

        # Try dmidecode for more details
        dmi_info = self._get_dmidecode_info()
        info.update(dmi_info)

        # Detect UEFI vs Legacy and Secure Boot
        info["boot_mode"] = self._detect_boot_mode()
        info["secure_boot"] = self._detect_secure_boot()
        info["type"] = "UEFI" if info["boot_mode"] == "UEFI" else "Legacy BIOS"

        return info

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated UEFI data."""
        return {
            "type": "UEFI",
            "vendor": "Dell Inc.",
            "version": "2.8.1",
            "date": "2024-03-15",
            "rom_size_mb": 32,
            "characteristics": [
                "ACPI",
                "USB Legacy",
                "UEFI Boot",
                "Secure Boot"
            ],
            "secure_boot": {
                "supported": True,
                "enabled": True,
                "mode": "user"
            },
            "boot_mode": "UEFI",
            "system_serial": "ABC123456",
            "system_uuid": "4c4c4544-0035-4d10-8051-c7c04f503432",
            "sku_number": "PE-R750",
            "family": "PowerEdge"
        }

    def _read_dmi_file(self, path: str) -> str:
        """Read DMI file from sysfs."""
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    return f.read().strip()
        except (IOError, FileNotFoundError, PermissionError):
            pass
        return "Unknown"

    def _get_dmidecode_info(self) -> Dict[str, Any]:
        """Get BIOS info via dmidecode."""
        info = {
            "characteristics": [],
            "rom_size_mb": 0
        }

        try:
            result = subprocess.run(
                ["dmidecode", "-t", "0,1"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                output = result.stdout

                # Parse characteristics
                if "ACPI" in output or "is supported" in output:
                    info["characteristics"].append("ACPI")
                if "USB Legacy" in output:
                    info["characteristics"].append("USB Legacy")
                if "UEFI" in output:
                    info["characteristics"].append("UEFI Boot")
                if "Secure Boot" in output:
                    info["characteristics"].append("Secure Boot")

                # Parse ROM size
                size_match = re.search(r'ROM Size: (\d+)\s*(kB|MB)', output, re.IGNORECASE)
                if size_match:
                    size = int(size_match.group(1))
                    unit = size_match.group(2).lower()
                    info["rom_size_mb"] = size if unit == "mb" else size // 1024

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return info

    def _detect_boot_mode(self) -> str:
        """Detect UEFI or Legacy boot mode."""
        # Check for EFI vars
        if os.path.exists("/sys/firmware/efi"):
            return "UEFI"

        # Check efivars if mounted
        if os.path.exists("/sys/firmware/efi/efivars"):
            return "UEFI"

        return "Legacy"

    def _detect_secure_boot(self) -> Dict[str, Any]:
        """Detect Secure Boot status."""
        secure_boot = {
            "supported": False,
            "enabled": False,
            "mode": "unknown"
        }

        # Check SecureBoot variable
        sb_path = "/sys/firmware/efi/efivars/SecureBoot-*"
        try:
            import glob
            sb_files = glob.glob(sb_path)
            if sb_files:
                secure_boot["supported"] = True
                try:
                    with open(sb_files[0], "rb") as f:
                        data = f.read()
                        # SecureBoot variable is 5 bytes: 4 byte attr + 1 byte value
                        if len(data) >= 5:
                            secure_boot["enabled"] = data[4] == 1
                except (IOError, PermissionError):
                    pass

        except Exception:
            pass

        return secure_boot
