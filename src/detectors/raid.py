import subprocess
import re
from typing import Dict, List, Any, Optional
from pathlib import Path

from .base import BaseDetector, DetectorMode


class RAIDDetector(BaseDetector):
    """Detect RAID controllers and their configuration.

    Supports LSI/Broadcom (StorCLI), Adaptec (arcconf), and HP/HPE (ssacli).
    Uses layered detection: lspci for basic info, vendor tools for details.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect RAID controllers using lspci and vendor tools."""
        # Layer 1: Detect controllers via lspci
        controllers = self._detect_via_lspci()

        if not controllers:
            return {"controllers": [], "controller_count": 0}

        # Layer 2: Enrich with vendor tool data if available
        for controller in controllers:
            vendor = controller.get("vendor", "").lower()
            tool_data = {}

            if "lsi" in vendor or "broadcom" in vendor or "mega" in vendor:
                tool_data = self._get_storcli_info(controller["index"])
            elif "adaptec" in vendor or "smart" in vendor:
                tool_data = self._get_arcconf_info(controller["index"])
            elif "hp" in vendor or "hpe" in vendor or "smart array" in vendor:
                tool_data = self._get_ssacli_info(controller["index"])

            if tool_data:
                controller.update(tool_data)
                controller["tool_available"] = True
            else:
                controller["tool_available"] = False

        return {
            "controllers": controllers,
            "controller_count": len(controllers)
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated RAID controller data."""
        return {
            "controllers": [
                {
                    "index": 0,
                    "model": "LSI MegaRAID 9361-8i",
                    "vendor": "LSI/Broadcom",
                    "firmware": "4.680.00-8188",
                    "driver": "megaraid_sas",
                    "pci_slot": "0000:05:00.0",
                    "detected_by": "storcli",
                    "tool_available": True,
                    "arrays": [
                        {
                            "id": 0,
                            "raid_level": "RAID5",
                            "size_gb": 5760,
                            "status": "Optimal",
                            "drives": 3,
                            "cache_policy": "WriteBack"
                        }
                    ],
                    "physical_drives": [
                        {
                            "enclosure": 0,
                            "slot": 0,
                            "model": "ST2000NM0008",
                            "size_gb": 1920,
                            "status": "Online",
                            "health": "Good"
                        },
                        {
                            "enclosure": 0,
                            "slot": 1,
                            "model": "ST2000NM0008",
                            "size_gb": 1920,
                            "status": "Online",
                            "health": "Good"
                        },
                        {
                            "enclosure": 0,
                            "slot": 2,
                            "model": "ST2000NM0008",
                            "size_gb": 1920,
                            "status": "Online",
                            "health": "Good"
                        }
                    ],
                    "battery": {
                        "present": True,
                        "status": "Optimal",
                        "charge_percent": 98
                    }
                }
            ],
            "controller_count": 1
        }

    def _detect_via_lspci(self) -> List[Dict[str, Any]]:
        """Detect RAID controllers using lspci."""
        controllers = []

        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return controllers

            for line in result.stdout.split("\n"):
                if any(keyword in line.lower() for keyword in
                       ["raid", "sas", "scsi", "mass storage"]):
                    controller = self._parse_lspci_line(line)
                    if controller:
                        controllers.append(controller)

        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

        return controllers

    def _parse_lspci_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single lspci line for RAID controller info."""
        match = re.match(r"(\S+)\s+(.+)\s+\[(\w+)\]", line)
        if not match:
            return None

        pci_slot = match.group(1)
        description = match.group(2)

        # Determine vendor
        vendor = "Unknown"
        desc_lower = description.lower()
        if any(v in desc_lower for v in ["lsi", "broadcom", "mega"]):
            vendor = "LSI/Broadcom"
        elif any(v in desc_lower for v in ["adaptec", "microsemi"]):
            vendor = "Adaptec"
        elif any(v in desc_lower for v in ["hp", "hpe", "smart array"]):
            vendor = "HP/HPE"
        elif "intel" in desc_lower:
            vendor = "Intel"

        return {
            "index": len([c for c in []]),  # Will be set by caller
            "model": description.strip(),
            "vendor": vendor,
            "pci_slot": pci_slot,
            "detected_by": "lspci"
        }

    def _get_storcli_info(self, controller_index: int) -> Dict[str, Any]:
        """Get RAID info using StorCLI (LSI/Broadcom)."""
        # Placeholder - will be implemented in Task 2
        return {}

    def _get_arcconf_info(self, controller_index: int) -> Dict[str, Any]:
        """Get RAID info using arcconf (Adaptec)."""
        # Placeholder - will be implemented in Task 2
        return {}

    def _get_ssacli_info(self, controller_index: int) -> Dict[str, Any]:
        """Get RAID info using ssacli (HP/HPE)."""
        # Placeholder - will be implemented in Task 2
        return {}
