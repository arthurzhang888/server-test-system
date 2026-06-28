import subprocess
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class GPUDetector(BaseDetector):
    """Detect GPU information - model, memory, driver version.

    Supports NVIDIA GPUs via nvidia-ml-py (pynvml) or nvidia-smi command.
    Gracefully degrades to empty list if no GPUs are detected.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect real GPU information using nvidia-ml-py or nvidia-smi."""
        gpus = self._detect_nvidia_gpus()

        if not gpus:
            # Try to detect AMD GPUs
            gpus = self._detect_amd_gpus()

        return {
            "gpus": gpus,
            "gpu_count": len(gpus),
            "vendor": self._determine_vendor(gpus),
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated GPU data for testing (NVIDIA A100)."""
        return {
            "gpus": [
                {"index": 0, "name": "NVIDIA A100", "memory_gb": 80, "driver": "535.54.03"}
            ],
            "gpu_count": 1,
            "vendor": "NVIDIA",
        }

    def _detect_nvidia_gpus(self) -> List[Dict[str, Any]]:
        """Try to detect NVIDIA GPUs using pynvml or nvidia-smi."""
        gpus = []

        # Try pynvml first
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            driver_version = pynvml.nvmlSystemGetDriverVersion()

            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                memory_gb = round(memory_info.total / (1024**3))

                gpus.append({
                    "index": i,
                    "name": name.decode() if isinstance(name, bytes) else name,
                    "memory_gb": memory_gb,
                    "driver": driver_version.decode() if isinstance(driver_version, bytes) else driver_version,
                })

            pynvml.nvmlShutdown()
            return gpus
        except ImportError:
            pass  # pynvml not installed
        except Exception:
            pass  # pynvml failed, try nvidia-smi

        # Fallback to nvidia-smi command
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.total,driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        gpus.append({
                            "index": int(parts[0]),
                            "name": parts[1],
                            "memory_gb": self._parse_memory(parts[2]),
                            "driver": parts[3],
                        })
            return gpus
        except FileNotFoundError:
            pass  # nvidia-smi not found
        except Exception:
            pass  # nvidia-smi failed

        return gpus

    def _detect_amd_gpus(self) -> List[Dict[str, Any]]:
        """Try to detect AMD GPUs using rocm-smi."""
        gpus = []

        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname", "--showmeminfo", "vram"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Basic parsing - AMD detection is more complex
                # This is a simplified version
                pass
        except FileNotFoundError:
            pass
        except Exception:
            pass

        return gpus

    def _parse_memory(self, memory_str: str) -> int:
        """Parse memory string like '8192 MiB' to GB."""
        try:
            # Extract number before MiB or similar
            parts = memory_str.split()
            if len(parts) >= 1:
                value = float(parts[0])
                if len(parts) == 1:
                    # No unit provided, assume it's already in GB
                    return int(value)
                unit = parts[1].lower()
                if "gib" in unit or "gb" in unit:
                    return int(value)
                elif "mib" in unit or "mb" in unit:
                    return int(value / 1024)
        except (ValueError, IndexError):
            pass
        return 0

    def _determine_vendor(self, gpus: List[Dict[str, Any]]) -> str:
        """Determine GPU vendor from detected GPUs."""
        if not gpus:
            return "Unknown"

        name = gpus[0].get("name", "").lower()
        if "nvidia" in name:
            return "NVIDIA"
        elif "amd" in name or "radeon" in name:
            return "AMD"
        elif "intel" in name:
            return "Intel"
        elif "huawei" in name or "ascend" in name:
            return "Huawei"
        elif "mthreads" in name or "mtt" in name:
            return "Moore Threads"
        else:
            return "Unknown"
