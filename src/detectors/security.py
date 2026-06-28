import os
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class SecurityDetector(BaseDetector):
    """Detect security features like SGX, SEV, TXT, and memory encryption.

    Checks sysfs paths for Intel SGX (Software Guard Extensions),
    AMD SEV (Secure Encrypted Virtualization), Intel TXT (Trusted
    Execution Technology), and memory encryption capabilities.
    """

    # Sysfs paths for security features
    SGX_PATH = "/sys/devices/system/cpu/sgx"
    SEV_PATH = "/sys/devices/system/cpu/sev"
    TXT_PATH = "/sys/firmware/txt"

    def detect_real(self) -> Dict[str, Any]:
        """Detect security features via sysfs."""
        info = {
            "sgx": self._detect_sgx(),
            "sev": self._detect_sev(),
            "txt": self._detect_txt(),
            "memory_encryption": self._detect_memory_encryption()
        }
        return info

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated security feature data."""
        return {
            "sgx": {
                "present": True,
                "enabled": True,
                "flc": True,
                "epc_size_mb": 128,
                "version": "2"
            },
            "sev": {
                "present": True,
                "enabled": True,
                "es": True,
                "snp": True,
                "firmware_version": "1.51"
            },
            "txt": {
                "present": True,
                "enabled": True,
                "bios_measured": True,
                "error": None
            },
            "memory_encryption": {
                "supported": True,
                "type": "both",
                "total_encrypted_memory_mb": 1024
            }
        }

    def _detect_sgx(self) -> Dict[str, Any]:
        """Detect Intel SGX (Software Guard Extensions).

        Returns:
            Dictionary with SGX presence, enablement, and capabilities.
        """
        sgx_info = {
            "present": False,
            "enabled": False,
            "flc": False,
            "epc_size_mb": 0,
            "version": None
        }

        if not os.path.exists(self.SGX_PATH):
            return sgx_info

        sgx_info["present"] = True

        # Check for SGX enablement via CPU capabilities
        enabled_path = f"{self.SGX_PATH}/enabled"
        if os.path.exists(enabled_path):
            try:
                with open(enabled_path, "r") as f:
                    content = f.read().strip()
                    sgx_info["enabled"] = content in ("1", "true", "enabled")
            except (IOError, FileNotFoundError):
                pass

        # Check for FLC (Flexible Launch Control)
        flc_path = f"{self.SGX_PATH}/flc"
        if os.path.exists(flc_path):
            try:
                with open(flc_path, "r") as f:
                    content = f.read().strip()
                    sgx_info["flc"] = content in ("1", "true", "enabled")
            except (IOError, FileNotFoundError):
                pass

        # Get EPC (Enclave Page Cache) size
        epc_path = f"{self.SGX_PATH}/epc_size"
        if os.path.exists(epc_path):
            try:
                with open(epc_path, "r") as f:
                    # EPC size is typically in bytes, convert to MB
                    epc_bytes = int(f.read().strip())
                    sgx_info["epc_size_mb"] = epc_bytes // (1024 * 1024)
            except (IOError, FileNotFoundError, ValueError):
                pass

        # Detect SGX version
        version_path = f"{self.SGX_PATH}/version"
        if os.path.exists(version_path):
            try:
                with open(version_path, "r") as f:
                    sgx_info["version"] = f.read().strip()
            except (IOError, FileNotFoundError):
                pass

        return sgx_info

    def _detect_sev(self) -> Dict[str, Any]:
        """Detect AMD SEV (Secure Encrypted Virtualization).

        Returns:
            Dictionary with SEV presence, enablement, and capabilities.
        """
        sev_info = {
            "present": False,
            "enabled": False,
            "es": False,
            "snp": False,
            "firmware_version": None
        }

        if not os.path.exists(self.SEV_PATH):
            return sev_info

        sev_info["present"] = True

        # Check SEV enablement
        enabled_path = f"{self.SEV_PATH}/enabled"
        if os.path.exists(enabled_path):
            try:
                with open(enabled_path, "r") as f:
                    content = f.read().strip()
                    sev_info["enabled"] = content in ("1", "true", "enabled")
            except (IOError, FileNotFoundError):
                pass

        # Check for SEV-ES (Encrypted State)
        es_path = f"{self.SEV_PATH}/es"
        if os.path.exists(es_path):
            try:
                with open(es_path, "r") as f:
                    content = f.read().strip()
                    sev_info["es"] = content in ("1", "true", "enabled")
            except (IOError, FileNotFoundError):
                pass

        # Check for SEV-SNP (Secure Nested Paging)
        snp_path = f"{self.SEV_PATH}/snp"
        if os.path.exists(snp_path):
            try:
                with open(snp_path, "r") as f:
                    content = f.read().strip()
                    sev_info["snp"] = content in ("1", "true", "enabled")
            except (IOError, FileNotFoundError):
                pass

        # Get firmware version
        fw_path = f"{self.SEV_PATH}/firmware_version"
        if os.path.exists(fw_path):
            try:
                with open(fw_path, "r") as f:
                    sev_info["firmware_version"] = f.read().strip()
            except (IOError, FileNotFoundError):
                pass

        return sev_info

    def _detect_txt(self) -> Dict[str, Any]:
        """Detect Intel TXT (Trusted Execution Technology).

        Returns:
            Dictionary with TXT presence, enablement, and status.
        """
        txt_info = {
            "present": False,
            "enabled": False,
            "bios_measured": False,
            "error": None
        }

        if not os.path.exists(self.TXT_PATH):
            return txt_info

        txt_info["present"] = True

        # Check TXT enablement
        enabled_path = f"{self.TXT_PATH}/enabled"
        if os.path.exists(enabled_path):
            try:
                with open(enabled_path, "r") as f:
                    content = f.read().strip()
                    txt_info["enabled"] = content in ("1", "true", "enabled")
            except (IOError, FileNotFoundError):
                pass

        # Check if BIOS was measured
        measured_path = f"{self.TXT_PATH}/bios_measured"
        if os.path.exists(measured_path):
            try:
                with open(measured_path, "r") as f:
                    content = f.read().strip()
                    txt_info["bios_measured"] = content in ("1", "true", "yes")
            except (IOError, FileNotFoundError):
                pass

        # Check for TXT errors
        error_path = f"{self.TXT_PATH}/error"
        if os.path.exists(error_path):
            try:
                with open(error_path, "r") as f:
                    error_content = f.read().strip()
                    if error_content and error_content != "0":
                        txt_info["error"] = error_content
            except (IOError, FileNotFoundError):
                pass

        return txt_info

    def _detect_memory_encryption(self) -> Dict[str, Any]:
        """Detect memory encryption capabilities.

        Returns:
            Dictionary with memory encryption support and type.
        """
        mem_info = {
            "supported": False,
            "type": None,
            "total_encrypted_memory_mb": 0
        }

        # Check for memory encryption sysfs path
        memenc_path = "/sys/devices/system/cpu/memory_encryption"
        if os.path.exists(memenc_path):
            mem_info["supported"] = True

            # Determine type based on SEV/SGX presence
            has_sev = os.path.exists(self.SEV_PATH)
            has_sgx = os.path.exists(self.SGX_PATH)

            if has_sev and has_sgx:
                mem_info["type"] = "both"
            elif has_sev:
                mem_info["type"] = "sev"
            elif has_sgx:
                mem_info["type"] = "sgx"

            # Try to get total encrypted memory size
            size_path = f"{memenc_path}/total_size"
            if os.path.exists(size_path):
                try:
                    with open(size_path, "r") as f:
                        mem_bytes = int(f.read().strip())
                        mem_info["total_encrypted_memory_mb"] = mem_bytes // (1024 * 1024)
                except (IOError, FileNotFoundError, ValueError):
                    pass

        return mem_info
