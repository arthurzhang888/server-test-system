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

        # Assign proper indices after collection
        for i, controller in enumerate(controllers):
            controller["index"] = i

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
            "model": description.strip(),
            "vendor": vendor,
            "pci_slot": pci_slot,
            "detected_by": "lspci"
        }

    def _get_storcli_info(self, controller_index: int) -> Dict[str, Any]:
        """Get RAID info using StorCLI (LSI/Broadcom)."""
        info = {
            "arrays": [],
            "physical_drives": [],
            "battery": {"present": False}
        }

        try:
            # Check if storcli exists
            result = subprocess.run(
                ["which", "storcli64"],
                capture_output=True,
                timeout=2
            )
            if result.returncode != 0:
                return info

            # Get controller info
            ctrl_result = subprocess.run(
                ["storcli64", f"/c{controller_index}", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if ctrl_result.returncode == 0:
                # Parse basic controller info
                for line in ctrl_result.stdout.split("\n"):
                    if "Firmware Version" in line:
                        parts = line.split("=")
                        if len(parts) > 1:
                            info["firmware"] = parts[1].strip()

            # Get virtual drives (arrays)
            vd_result = subprocess.run(
                ["storcli64", f"/c{controller_index}", "/vall", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if vd_result.returncode == 0:
                info["arrays"] = self._parse_storcli_vd_output(vd_result.stdout)

            # Get physical drives
            pd_result = subprocess.run(
                ["storcli64", f"/c{controller_index}", "/eall", "/sall", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if pd_result.returncode == 0:
                info["physical_drives"] = self._parse_storcli_pd_output(pd_result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return info

    def _parse_storcli_vd_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse StorCLI virtual drive output."""
        arrays = []
        # Simplified parsing - real implementation would be more robust
        for line in output.split("\n"):
            if "RAID" in line and "Optimal" in line:
                parts = line.split()
                if len(parts) >= 4:
                    arrays.append({
                        "id": len(arrays),
                        "raid_level": parts[1] if len(parts) > 1 else "Unknown",
                        "status": "Optimal",
                        "size_gb": 0,  # Would need size parsing
                        "drives": 0
                    })
        return arrays

    def _parse_storcli_pd_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse StorCLI physical drive output."""
        drives = []
        for line in output.split("\n"):
            if "HDD" in line or "SSD" in line:
                parts = line.split()
                if len(parts) >= 3:
                    drives.append({
                        "enclosure": 0,
                        "slot": len(drives),
                        "model": parts[0] if parts else "Unknown",
                        "size_gb": 0,
                        "status": "Online"
                    })
        return drives

    def _get_arcconf_info(self, controller_index: int) -> Dict[str, Any]:
        """Get RAID info using arcconf (Adaptec)."""
        info = {
            "arrays": [],
            "physical_drives": [],
            "battery": {"present": False}
        }

        try:
            # Check if arcconf exists
            result = subprocess.run(
                ["which", "arcconf"],
                capture_output=True,
                timeout=2
            )
            if result.returncode != 0:
                return info

            # Get controller info
            ctrl_result = subprocess.run(
                ["arcconf", "getconfig", str(controller_index + 1)],
                capture_output=True,
                text=True,
                timeout=10
            )

            if ctrl_result.returncode == 0:
                info.update(self._parse_arcconf_output(ctrl_result.stdout))

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return info

    def _parse_arcconf_output(self, output: str) -> Dict[str, Any]:
        """Parse arcconf getconfig output."""
        result = {
            "arrays": [],
            "physical_drives": [],
            "battery": {"present": False}
        }

        current_section = None
        current_drive = None
        current_array = None

        for line in output.split("\n"):
            line = line.strip()

            # Detect section
            if "Controller Battery Information" in line:
                current_section = "battery"
                result["battery"]["present"] = True
            elif "Logical Device information" in line:
                current_section = "arrays"
            elif "Physical Device information" in line:
                current_section = "drives"
            elif line.startswith("Logical Device number"):
                if current_array:
                    result["arrays"].append(current_array)
                current_array = {
                    "id": int(line.split()[-1]),
                    "raid_level": "Unknown",
                    "status": "Unknown",
                    "size_gb": 0,
                    "drives": 0
                }
            elif line.startswith("Device #"):
                if current_drive:
                    result["physical_drives"].append(current_drive)
                current_drive = {
                    "enclosure": 0,
                    "slot": len(result["physical_drives"]),
                    "model": "Unknown",
                    "size_gb": 0,
                    "status": "Online"
                }

            # Parse battery info
            elif current_section == "battery":
                if "Status" in line and ":" in line:
                    result["battery"]["status"] = line.split(":")[1].strip()
                elif "Remaining Charge" in line and ":" in line:
                    charge_match = re.search(r'(\d+)', line)
                    if charge_match:
                        result["battery"]["charge_percent"] = int(charge_match.group(1))

            # Parse array info
            elif current_section == "arrays" and current_array:
                if "RAID level" in line:
                    raid_match = re.search(r'RAID level\s*:\s*(\w+)', line, re.IGNORECASE)
                    if raid_match:
                        current_array["raid_level"] = raid_match.group(1).upper()
                elif "Status of logical device" in line:
                    current_array["status"] = line.split(":")[1].strip()
                elif "Size" in line:
                    size_match = re.search(r'(\d+)\s*GB', line, re.IGNORECASE)
                    if size_match:
                        current_array["size_gb"] = int(size_match.group(1))

            # Parse drive info
            elif current_section == "drives" and current_drive:
                if "State" in line:
                    current_drive["status"] = line.split(":")[1].strip()
                elif "Model" in line:
                    current_drive["model"] = line.split(":")[1].strip()
                elif "Size" in line:
                    size_match = re.search(r'(\d+)\s*GB', line, re.IGNORECASE)
                    if size_match:
                        current_drive["size_gb"] = int(size_match.group(1))

        # Add last entries
        if current_array:
            result["arrays"].append(current_array)
        if current_drive:
            result["physical_drives"].append(current_drive)

        return result

    def _get_ssacli_info(self, controller_index: int) -> Dict[str, Any]:
        """Get RAID info using ssacli (HP/HPE)."""
        info = {
            "arrays": [],
            "physical_drives": [],
            "battery": {"present": False}
        }

        try:
            # Check if ssacli exists (also try hpacucli for older systems)
            for cmd in ["ssacli", "hpacucli"]:
                result = subprocess.run(
                    ["which", cmd],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    tool = cmd
                    break
            else:
                return info

            # Get controller detail
            ctrl_result = subprocess.run(
                [tool, f"ctrl slot={controller_index}", "show", "detail"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if ctrl_result.returncode == 0:
                # Parse battery/cache info
                if "Cache Status" in ctrl_result.stdout or "Battery" in ctrl_result.stdout:
                    info["battery"]["present"] = True
                    info["battery"]["status"] = "OK" if "OK" in ctrl_result.stdout else "Unknown"

            # Get logical drives (arrays)
            ld_result = subprocess.run(
                [tool, f"ctrl slot={controller_index}", "ld", "all", "show", "detail"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if ld_result.returncode == 0:
                info["arrays"] = self._parse_ssacli_ld_output(ld_result.stdout)

            # Get physical drives
            pd_result = subprocess.run(
                [tool, f"ctrl slot={controller_index}", "pd", "all", "show", "detail"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if pd_result.returncode == 0:
                info["physical_drives"] = self._parse_ssacli_pd_output(pd_result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return info

    def _parse_ssacli_ld_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse ssacli logical drive output."""
        arrays = []
        current_array = None

        for line in output.split("\n"):
            line = line.strip()

            if line.startswith("Logical Drive:"):
                if current_array:
                    arrays.append(current_array)
                current_array = {
                    "id": len(arrays),
                    "raid_level": "Unknown",
                    "status": "Unknown",
                    "size_gb": 0,
                    "drives": 0
                }
            elif current_array:
                if "RAID" in line and "Level" in line:
                    # Match patterns like "RAID Level: RAID 5" or "RAID Level: RAID5"
                    # First try to match "RAID 5" or "RAID5" after the colon
                    raid_match = re.search(r'RAID\s*(\d+)', line, re.IGNORECASE)
                    if raid_match:
                        current_array["raid_level"] = f"RAID{raid_match.group(1)}"
                elif "Status:" in line:
                    current_array["status"] = line.split(":")[1].strip()
                elif "Size:" in line:
                    size_match = re.search(r'(\d+(?:\.\d+)?)\s*(GB|TB)', line, re.IGNORECASE)
                    if size_match:
                        size = float(size_match.group(1))
                        unit = size_match.group(2).upper()
                        current_array["size_gb"] = size if unit == "GB" else int(size * 1024)

        if current_array:
            arrays.append(current_array)

        return arrays

    def _parse_ssacli_pd_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse ssacli physical drive output."""
        drives = []
        current_drive = None

        for line in output.split("\n"):
            line = line.strip()

            if "physicaldrive" in line.lower():
                if current_drive:
                    drives.append(current_drive)
                current_drive = {
                    "enclosure": 0,
                    "slot": len(drives),
                    "model": "Unknown",
                    "size_gb": 0,
                    "status": "OK"
                }
            elif current_drive:
                if "Status:" in line:
                    current_drive["status"] = line.split(":")[1].strip()
                elif "Model:" in line:
                    current_drive["model"] = line.split(":")[1].strip()
                elif "Size:" in line:
                    size_match = re.search(r'(\d+(?:\.\d+)?)\s*(GB|TB)', line, re.IGNORECASE)
                    if size_match:
                        size = float(size_match.group(1))
                        unit = size_match.group(2).upper()
                        current_drive["size_gb"] = size if unit == "GB" else int(size * 1024)

        if current_drive:
            drives.append(current_drive)

        return drives
