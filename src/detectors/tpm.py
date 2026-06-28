import os
import subprocess
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class TPMDetector(BaseDetector):
    """Detect Trusted Platform Module (TPM) information.

    Supports TPM 1.2 and 2.0 via sysfs interface.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect TPM via sysfs."""
        tpm_path = "/sys/class/tpm/tpm0"

        if not os.path.exists(tpm_path):
            return {"present": False}

        info = {
            "present": True,
            "version": self._detect_version(tpm_path),
            "vendor": "Unknown",
            "firmware_version": "Unknown",
            "status": "unknown",
            "ek_certificate_present": False,
            "pcr_banks": [],
            "pcr_count": 0,
            "nvram_size_kb": 0,
            "clear_control": "unknown"
        }

        # Read TPM version
        try:
            with open(f"{tpm_path}/tpm_version_major", "r") as f:
                major = f.read().strip()
                info["version"] = f"{major}.0" if major == "2" else "1.2"
        except (IOError, FileNotFoundError):
            pass

        # Read device info if available (vendor, fw version)
        caps_path = f"{tpm_path}/device/caps"
        if os.path.exists(caps_path):
            try:
                with open(caps_path, "r") as f:
                    for line in f:
                        if "Manufacturer" in line:
                            parts = line.split(":")
                            if len(parts) > 1:
                                info["vendor"] = parts[1].strip()
            except (IOError, FileNotFoundError):
                pass

        # Try to get PCR info via tpm2_getcap if available
        info["pcr_banks"], info["pcr_count"] = self._get_pcr_info()

        # Check for EK certificate
        info["ek_certificate_present"] = os.path.exists(f"{tpm_path}/device/endorsement_key")

        return info

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated TPM 2.0 data."""
        return {
            "present": True,
            "version": "2.0",
            "vendor": "Intel",
            "firmware_version": "7.2.2.0",
            "status": "active",
            "ek_certificate_present": True,
            "pcr_banks": ["sha256", "sha384"],
            "pcr_count": 24,
            "nvram_size_kb": 48,
            "clear_control": "locked"
        }

    def _detect_version(self, tpm_path: str) -> str:
        """Detect TPM version from sysfs."""
        try:
            version_path = f"{tpm_path}/tpm_version_major"
            if os.path.exists(version_path):
                with open(version_path, "r") as f:
                    major = f.read().strip()
                    return f"{major}.0" if major == "2" else "1.2"

            # Fallback: check for tpm2 specific files
            if os.path.exists(f"{tpm_path}/device/tpm2"):
                return "2.0"

        except (IOError, FileNotFoundError):
            pass

        return "unknown"

    def _get_pcr_info(self) -> (List[str], int):
        """Get PCR bank algorithms and count."""
        banks = []
        pcr_count = 0

        # Try tpm2_getcap if available
        try:
            result = subprocess.run(
                ["tpm2_getcap", "pcrs"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                output = result.stdout.lower()
                if "sha256" in output:
                    banks.append("sha256")
                if "sha384" in output:
                    banks.append("sha384")
                if "sha1" in output:
                    banks.append("sha1")

                # Count PCRs from output
                pcr_count = output.count("pcr_")
                if pcr_count == 0:
                    pcr_count = 24  # Default for TPM 2.0

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Default values if tpm2_getcap not available
        if not banks:
            banks = ["sha256"]
        if pcr_count == 0:
            pcr_count = 24

        return banks, pcr_count
