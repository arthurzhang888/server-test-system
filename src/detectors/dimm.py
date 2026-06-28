import subprocess
import re
from typing import Dict, Any, List, Optional

from .base import BaseDetector, DetectorMode


class DIMMDetector(BaseDetector):
    """Detect individual DIMM information - slots, size, type, speed, errors."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect real DIMM information using dmidecode -t 17."""
        dimms = self._parse_dmidecode()

        return {
            "dimms": dimms,
            "total_slots": len(dimms),
            "populated_slots": sum(1 for d in dimms if d.get("size_gb", 0) > 0),
            "total_memory_gb": round(sum(d.get("size_gb", 0) for d in dimms), 2),
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated DIMM data for testing."""
        return {
            "dimms": [
                {
                    "slot": "DIMM_A1",
                    "size_gb": 64.0,
                    "type": "DDR5",
                    "speed_mhz": 4800,
                    "configured_speed_mhz": 4400,
                    "manufacturer": "Samsung",
                    "serial_number": "S123456789",
                    "part_number": "M393A8G40AB2-CWE",
                    "rank": "2R",
                    "voltage_v": 1.1,
                    "ecc": True,
                    "temperature_c": 42,
                    "correctable_errors": 0,
                    "uncorrectable_errors": 0,
                    "status": "Present",
                },
                {
                    "slot": "DIMM_A2",
                    "size_gb": 64.0,
                    "type": "DDR5",
                    "speed_mhz": 4800,
                    "configured_speed_mhz": 4400,
                    "manufacturer": "Samsung",
                    "serial_number": "S987654321",
                    "part_number": "M393A8G40AB2-CWE",
                    "rank": "2R",
                    "voltage_v": 1.1,
                    "ecc": True,
                    "temperature_c": 44,
                    "correctable_errors": 2,
                    "uncorrectable_errors": 0,
                    "status": "Present",
                },
                {
                    "slot": "DIMM_B1",
                    "size_gb": 0,
                    "type": None,
                    "speed_mhz": None,
                    "configured_speed_mhz": None,
                    "manufacturer": None,
                    "serial_number": None,
                    "part_number": None,
                    "rank": None,
                    "voltage_v": None,
                    "ecc": None,
                    "temperature_c": None,
                    "correctable_errors": None,
                    "uncorrectable_errors": None,
                    "status": "Empty",
                },
            ],
            "total_slots": 16,
            "populated_slots": 2,
            "total_memory_gb": 128.0,
        }

    def _parse_dmidecode(self) -> List[Dict[str, Any]]:
        """Parse dmidecode -t 17 output to extract DIMM information."""
        try:
            result = subprocess.run(
                ["dmidecode", "-t", "17"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return []
            return self._parse_memory_devices(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            return []

    def _parse_memory_devices(self, output: str) -> List[Dict[str, Any]]:
        """Parse dmidecode output for Memory Device entries."""
        dimms = []
        current_dimm: Dict[str, Any] = {}

        for line in output.splitlines():
            line = line.rstrip()

            # New memory device section starts - either "Handle" line with type 17
            # or standalone "Memory Device" header
            if ("Handle" in line and "DMI type 17" in line) or line.strip() == "Memory Device":
                if current_dimm:
                    dimms.append(current_dimm)
                current_dimm = {"status": "Present"}
                continue

            if not current_dimm:
                continue

            # Parse fields
            if match := re.match(r"\s*Locator:\s*(.+)", line):
                current_dimm["slot"] = match.group(1).strip()
            elif match := re.match(r"\s*Size:\s*(.+)", line):
                size_str = match.group(1).strip()
                current_dimm["size_gb"] = self._parse_size(size_str)
                if "No Module Installed" in size_str or size_str == "0 MB":
                    current_dimm["status"] = "Empty"
            elif match := re.match(r"\s*Type:\s*(.+)", line):
                mem_type = match.group(1).strip()
                if mem_type not in ["Unknown", "Other"]:
                    current_dimm["type"] = mem_type
            elif match := re.match(r"\s*Speed:\s*(\d+)\s*MT/s", line):
                current_dimm["speed_mhz"] = int(match.group(1))
            elif match := re.match(r"\s*Configured.*Speed:\s*(\d+)\s*MT/s", line):
                current_dimm["configured_speed_mhz"] = int(match.group(1))
            elif match := re.match(r"\s*Manufacturer:\s*(.+)", line):
                mfg = match.group(1).strip()
                if mfg not in ["Unknown", "Not Specified", "0000"]:
                    current_dimm["manufacturer"] = mfg
            elif match := re.match(r"\s*Serial Number:\s*(.+)", line):
                sn = match.group(1).strip()
                if sn not in ["Unknown", "Not Specified", "00000000"]:
                    current_dimm["serial_number"] = sn
            elif match := re.match(r"\s*Part Number:\s*(.+)", line):
                pn = match.group(1).strip()
                if pn not in ["Unknown", "Not Specified"]:
                    current_dimm["part_number"] = pn
            elif match := re.match(r"\s*Rank:\s*(.+)", line):
                rank = match.group(1).strip()
                if rank not in ["Unknown"]:
                    current_dimm["rank"] = rank
            elif match := re.match(r"\s*Configured.*Voltage:\s*(\d+)\s*mV", line):
                current_dimm["voltage_v"] = int(match.group(1)) / 1000
            elif match := re.match(r"\s*Error Correction Type:\s*(.+)", line):
                ecc_type = match.group(1).strip()
                current_dimm["ecc"] = "ECC" in ecc_type

        if current_dimm:
            dimms.append(current_dimm)

        # Filter out empty entries without slot info
        return [d for d in dimms if "slot" in d]

    def _parse_size(self, size_str: str) -> float:
        """Parse size string to GB."""
        if "No Module Installed" in size_str or size_str == "0 MB":
            return 0.0

        # Handle MB
        if match := re.match(r"(\d+)\s*MB", size_str):
            return round(int(match.group(1)) / 1024, 2)

        # Handle GB
        if match := re.match(r"(\d+)\s*GB", size_str):
            return float(match.group(1))

        # Handle TB
        if match := re.match(r"(\d+)\s*TB", size_str):
            return float(match.group(1)) * 1024

        return 0.0

    def get_dimm_temperatures(self) -> Dict[str, Optional[float]]:
        """Get DIMM temperatures from IPMI or sensor data where available."""
        # This would typically read from IPMI sensors or thermal zones
        # For now, return empty dict in real mode
        return {}

    def get_ecc_errors(self) -> List[Dict[str, Any]]:
        """Get ECC error counts from EDAC or mcelog where available."""
        # This would parse /sys/devices/system/edac/mc/ on Linux
        errors = []
        try:
            import glob
            mc_paths = glob.glob("/sys/devices/system/edac/mc/mc*")
            for mc_path in mc_paths:
                error_info = {"memory_controller": mc_path.split("/")[-1]}

                # Try to read CE (correctable) count
                ce_file = f"{mc_path}/ce_count"
                try:
                    with open(ce_file) as f:
                        error_info["correctable_errors"] = int(f.read().strip())
                except (FileNotFoundError, ValueError):
                    pass

                # Try to read UE (uncorrectable) count
                ue_file = f"{mc_path}/ue_count"
                try:
                    with open(ue_file) as f:
                        error_info["uncorrectable_errors"] = int(f.read().strip())
                except (FileNotFoundError, ValueError):
                    pass

                if "correctable_errors" in error_info or "uncorrectable_errors" in error_info:
                    errors.append(error_info)
        except Exception:
            pass

        return errors
