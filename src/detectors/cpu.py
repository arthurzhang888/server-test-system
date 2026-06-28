import platform
import psutil
from typing import Dict, Any

from .base import BaseDetector, DetectorMode


class CPUDetector(BaseDetector):
    """Detect CPU information - model, cores, frequency, architecture."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect real CPU information using psutil and platform."""
        cpu_freq = psutil.cpu_freq()
        cpu_count = psutil.cpu_count(logical=False) or 1
        cpu_count_logical = psutil.cpu_count(logical=True) or cpu_count

        return {
            "model": platform.processor() or "Unknown",
            "brand": self._get_cpu_brand(),
            "cores": cpu_count,
            "threads": cpu_count_logical,
            "frequency_ghz": round(cpu_freq.current / 1000, 2) if cpu_freq else 0.0,
            "frequency_max_ghz": round(cpu_freq.max / 1000, 2) if cpu_freq and cpu_freq.max else 0.0,
            "architecture": platform.machine(),
            "byteorder": "little",  # Simplified for cross-platform
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated CPU data for testing."""
        return {
            "model": "Intel Xeon Gold 6448Y",
            "brand": "Intel",
            "cores": 32,
            "threads": 64,
            "frequency_ghz": 2.1,
            "frequency_max_ghz": 4.1,
            "architecture": "x86_64",
            "byteorder": "little",
        }

    def _get_cpu_brand(self) -> str:
        """Extract CPU brand from processor string."""
        processor = platform.processor().lower()
        if "intel" in processor:
            return "Intel"
        elif "amd" in processor:
            return "AMD"
        elif "arm" in processor:
            return "ARM"
        else:
            return "Unknown"
