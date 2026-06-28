import psutil
from typing import Dict, Any

from .base import BaseDetector, DetectorMode


class MemoryDetector(BaseDetector):
    """Detect memory information - total, available, type, ECC status."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect real memory information using psutil."""
        mem = psutil.virtual_memory()

        return {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "percent_used": mem.percent,
            "type": self._detect_memory_type(),
            "ecc": None,  # Would need dmidecode or similar for ECC detection
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated memory data for testing."""
        return {
            "total_gb": 512.0,
            "available_gb": 480.5,
            "used_gb": 31.5,
            "percent_used": 6.2,
            "type": "DDR4",
            "ecc": True,
            "speed_mhz": 3200,
            "slots_total": 16,
            "slots_used": 16,
        }

    def _detect_memory_type(self) -> str:
        """Attempt to detect memory type (DDR4/DDR5 etc)."""
        # Real implementation would use dmidecode or similar
        return "Unknown"
