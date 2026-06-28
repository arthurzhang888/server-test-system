import subprocess
import re
from typing import Dict, List, Any

from .base import BaseDetector, DetectorMode


class FPGADetector(BaseDetector):
    """Detect FPGA (Field Programmable Gate Array) cards.

    Uses lspci to detect Xilinx/AMD and Intel FPGA cards.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect FPGA cards using lspci."""
        fpgas = []

        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                fpgas = self._parse_lspci_output(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

        return {
            "fpgas": fpgas,
            "fpga_count": len(fpgas)
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated FPGA data."""
        return {
            "fpgas": [
                {
                    "index": 0,
                    "model": "Alveo U280",
                    "vendor": "Xilinx",
                    "device_id": "500c",
                    "vendor_id": "10ee",
                    "pci_slot": "0000:03:00.0",
                    "firmware": "1.2.3",
                    "memory_gb": 32,
                    "status": "OK",
                    "temperature_c": 45,
                    "power_watts": 75
                },
                {
                    "index": 1,
                    "model": "Stratix 10 MX",
                    "vendor": "Intel",
                    "device_id": "0b30",
                    "vendor_id": "8086",
                    "pci_slot": "0000:04:00.0",
                    "firmware": "2.0.1",
                    "memory_gb": 16,
                    "status": "OK",
                    "temperature_c": 42,
                    "power_watts": 65
                }
            ],
            "fpga_count": 2
        }

    def _parse_lspci_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse lspci output to find FPGA devices."""
        fpgas = []
        fpga_patterns = [
            (r'xilinx', 'Xilinx'),
            (r'intel.*fpga', 'Intel'),
            (r'intel.*stratix', 'Intel'),
            (r'intel.*arria', 'Intel'),
            (r'amd.*fpga', 'AMD'),
            (r'altera', 'Intel'),
            (r'lattice', 'Lattice'),
            (r'microsemi', 'Microsemi')
        ]

        for line in output.split("\n"):
            line_lower = line.lower()
            is_fpga = False
            vendor = "Unknown"

            for pattern, vendor_name in fpga_patterns:
                if re.search(pattern, line_lower):
                    is_fpga = True
                    vendor = vendor_name
                    break

            if is_fpga:
                fpga = self._parse_fpga_line(line, vendor)
                if fpga:
                    fpgas.append(fpga)

        # Assign indices after collection
        for i, fpga in enumerate(fpgas):
            fpga["index"] = i

        return fpgas

    def _parse_fpga_line(self, line: str, vendor: str) -> Dict[str, Any]:
        """Parse a single lspci line for FPGA information."""
        # Match pattern like: "03:00.0 Processing accelerators: Xilinx Corporation Device 500c"
        match = re.match(r"(\S+)\s+(.+)\s+\[(\w+):(\w+)\]", line)

        if not match:
            # Try alternative pattern without brackets
            match = re.match(r"(\S+)\s+(.+):\s+(.+)", line)
            if not match:
                return None
            pci_slot = match.group(1)
            device_type = match.group(2).strip()
            description = match.group(3).strip()
            vendor_id = "0000"
            device_id = "0000"
        else:
            pci_slot = match.group(1)
            description = match.group(2).strip()
            vendor_id = match.group(3)
            device_id = match.group(4)

        # Extract model from description
        model = self._extract_model(description, vendor)

        return {
            "model": model,
            "vendor": vendor,
            "device_id": device_id.lower(),
            "vendor_id": vendor_id.lower(),
            "pci_slot": pci_slot,
            "firmware": "unknown",
            "memory_gb": 0,
            "status": "OK",
            "temperature_c": 0,
            "power_watts": 0
        }

    def _extract_model(self, description: str, vendor: str) -> str:
        """Extract FPGA model from description."""
        desc_lower = description.lower()

        # Xilinx/AMD patterns
        if vendor == "Xilinx" or vendor == "AMD":
            if "alveo" in desc_lower:
                # Try to extract Alveo model
                match = re.search(r'alveo\s+(u?\d+)', desc_lower, re.IGNORECASE)
                if match:
                    return f"Alveo {match.group(1).upper()}"
                return "Alveo"
            elif "virtex" in desc_lower:
                return "Virtex"
            elif "kintex" in desc_lower:
                return "Kintex"

        # Intel patterns
        if vendor == "Intel":
            if "stratix" in desc_lower:
                match = re.search(r'stratix\s+(\d+\s*\w*)', desc_lower, re.IGNORECASE)
                if match:
                    return f"Stratix {match.group(1).strip()}"
                return "Stratix"
            elif "arria" in desc_lower:
                return "Arria"
            elif "agilex" in desc_lower:
                return "Agilex"

        # Return description if no specific model matched
        return description.split(":")[-1].strip() or "Unknown FPGA"
