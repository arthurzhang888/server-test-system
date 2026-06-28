"""GPU stress test implementation supporting multiple vendors.

Supported GPUs:
- NVIDIA (nvidia-smi, CUDA)
- AMD (rocm-smi, ROCm)
- 海光 DCU (hygon-smi or rocm-smi)
- 寒武纪 MLU (cnmon)
- 华为昇腾 NPU (npu-smi)
- 摩尔线程 MUSA (mthreads-gmi)
"""

import subprocess
import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .base import StressTestBase, ThresholdConfig


class GPUVendor(str, Enum):
    """GPU vendor types."""
    NVIDIA = "nvidia"
    AMD = "amd"
    HYGON = "hygon"  # 海光
    CAMBRICON = "cambricon"  # 寒武纪
    ASCEND = "ascend"  # 华为昇腾
    MOORE_THREADS = "moore_threads"  # 摩尔线程
    UNKNOWN = "unknown"


@dataclass
class GPUInfo:
    """GPU information structure."""
    index: int
    name: str
    vendor: GPUVendor
    memory_mb: int
    driver_version: str
    pci_id: str = ""


@dataclass
class GPUThresholds:
    """Predefined threshold configurations for GPU stress test."""
    temperature: ThresholdConfig = None
    utilization: ThresholdConfig = None
    memory_utilization: ThresholdConfig = None
    power: ThresholdConfig = None
    clock_speed: ThresholdConfig = None

    def __post_init__(self):
        if self.temperature is None:
            self.temperature = ThresholdConfig(min_value=0, max_value=95, warning_pct=0.84, critical_pct=0.95)
        if self.utilization is None:
            self.utilization = ThresholdConfig(min_value=80, max_value=100)
        if self.memory_utilization is None:
            self.memory_utilization = ThresholdConfig(min_value=50, max_value=100)
        if self.power is None:
            self.power = ThresholdConfig(min_value=50, max_value=400, warning_pct=0.9, critical_pct=0.98)
        if self.clock_speed is None:
            self.clock_speed = ThresholdConfig(min_value=500, max_value=2500)


class GPUStressTest(StressTestBase):
    """Universal GPU stress test for NVIDIA, AMD, and domestic GPUs.

    Auto-detects GPU vendor and uses appropriate tools for monitoring
    and stress testing.
    """

    def __init__(
        self,
        duration_seconds: int = 300,
        sample_interval_seconds: int = 5,
        gpu_indices: Optional[List[int]] = None,
        thresholds: Optional[GPUThresholds] = None
    ):
        thresholds = thresholds or GPUThresholds()
        super().__init__(
            duration_seconds=duration_seconds,
            sample_interval_seconds=sample_interval_seconds,
            thresholds={
                "temperature": thresholds.temperature,
                "utilization": thresholds.utilization,
                "memory_utilization": thresholds.memory_utilization,
                "power": thresholds.power,
                "clock_speed": thresholds.clock_speed,
            }
        )
        self.gpu_indices = gpu_indices
        self._detected_gpus: List[GPUInfo] = []
        self._stress_threads: List[threading.Thread] = []
        self._stop_stress = threading.Event()

    @property
    def test_name(self) -> str:
        return "gpu_stress"

    def _detect_gpus(self) -> List[GPUInfo]:
        """Detect all available GPUs from various vendors."""
        gpus = []

        # Try each vendor detection
        detectors = [
            self._detect_nvidia,
            self._detect_amd,
            self._detect_hygon,
            self._detect_cambricon,
            self._detect_ascend,
            self._detect_moore_threads,
        ]

        for detector in detectors:
            try:
                vendor_gpus = detector()
                gpus.extend(vendor_gpus)
            except Exception:
                pass

        return gpus

    def _detect_nvidia(self) -> List[GPUInfo]:
        """Detect NVIDIA GPUs."""
        gpus = []
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.total,pci.bus_id,driver_version",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 5:
                        gpus.append(GPUInfo(
                            index=int(parts[0]),
                            name=parts[1],
                            vendor=GPUVendor.NVIDIA,
                            memory_mb=self._parse_memory(parts[2]),
                            pci_id=parts[3],
                            driver_version=parts[4]
                        ))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return gpus

    def _detect_amd(self) -> List[GPUInfo]:
        """Detect AMD GPUs via rocm-smi."""
        gpus = []
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname", "--showdriverversion", "--json"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                for card in data.get("card_list", []):
                    gpus.append(GPUInfo(
                        index=card.get("card_index", 0),
                        name=card.get("product_name", "AMD GPU"),
                        vendor=GPUVendor.AMD,
                        memory_mb=card.get("memory_available", 0),
                        pci_id=card.get("pci_bus", ""),
                        driver_version=data.get("driver_version", "")
                    ))
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        return gpus

    def _detect_hygon(self) -> List[GPUInfo]:
        """Detect 海光 DCU GPUs."""
        gpus = []
        # 海光通常使用 hygon-smi 或兼容 rocm-smi
        try:
            # Try hygon-smi first
            result = subprocess.run(
                ["hygon-smi", "-L"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for idx, line in enumerate(result.stdout.split("\n")):
                    if "DCU" in line or "GPU" in line:
                        name = line.split(":")[-1].strip() if ":" in line else "Hygon DCU"
                        gpus.append(GPUInfo(
                            index=idx,
                            name=name,
                            vendor=GPUVendor.HYGON,
                            memory_mb=0,
                            driver_version="",
                            pci_id=""
                        ))
        except FileNotFoundError:
            # Fallback to rocm-smi for Hygon
            try:
                result = subprocess.run(
                    ["rocm-smi", "--showproductname"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and "Hygon" in result.stdout:
                    # Parse as Hygon GPUs
                    for idx, line in enumerate(result.stdout.split("\n")):
                        if "Hygon" in line:
                            gpus.append(GPUInfo(
                                index=idx,
                                name="Hygon DCU",
                                vendor=GPUVendor.HYGON,
                                memory_mb=0,
                                driver_version="",
                                pci_id=""
                            ))
            except FileNotFoundError:
                pass
        return gpus

    def _detect_cambricon(self) -> List[GPUInfo]:
        """Detect 寒武纪 MLU cards."""
        gpus = []
        try:
            # cnmon is the Cambricon monitoring tool
            result = subprocess.run(
                ["cnmon"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.split("\n")
                for idx, line in enumerate(lines):
                    if "MLU" in line:
                        # Parse MLU info
                        parts = line.split()
                        name = "MLU"
                        for part in parts:
                            if "MLU" in part:
                                name = part
                                break
                        gpus.append(GPUInfo(
                            index=idx,
                            name=name,
                            vendor=GPUVendor.CAMBRICON,
                            memory_mb=0,
                            driver_version="",
                            pci_id=""
                        ))
        except FileNotFoundError:
            # Try cnmon -L for list
            try:
                result = subprocess.run(
                    ["cnmon", "-L"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for idx, line in enumerate(result.stdout.split("\n")):
                        if "mlu" in line.lower():
                            gpus.append(GPUInfo(
                                index=idx,
                                name="Cambricon MLU",
                                vendor=GPUVendor.CAMBRICON,
                                memory_mb=0,
                                driver_version="",
                                pci_id=""
                            ))
            except FileNotFoundError:
                pass
        return gpus

    def _detect_ascend(self) -> List[GPUInfo]:
        """Detect 华为昇腾 NPU cards."""
        gpus = []
        try:
            # npu-smi is Huawei Ascend tool
            result = subprocess.run(
                ["npu-smi", "info"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.split("\n")
                current_npu = None
                for line in lines:
                    if line.startswith("|"):
                        # Parse table format
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 4 and parts[1].isdigit():
                            idx = int(parts[1])
                            name = parts[2] if len(parts) > 2 else "Ascend NPU"
                            gpus.append(GPUInfo(
                                index=idx,
                                name=name,
                                vendor=GPUVendor.ASCEND,
                                memory_mb=0,
                                driver_version="",
                                pci_id=""
                            ))
        except FileNotFoundError:
            pass
        return gpus

    def _detect_moore_threads(self) -> List[GPUInfo]:
        """Detect 摩尔线程 MTT GPUs."""
        gpus = []
        try:
            # mthreads-gmi is Moore Threads GPU management interface
            result = subprocess.run(
                ["mthreads-gmi", "-L"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for idx, line in enumerate(result.stdout.split("\n")):
                    if "MTT" in line or "GPU" in line:
                        name = "MTT GPU"
                        if "MTT" in line:
                            parts = line.split()
                            for part in parts:
                                if "MTT" in part:
                                    name = part
                                    break
                        gpus.append(GPUInfo(
                            index=idx,
                            name=name,
                            vendor=GPUVendor.MOORE_THREADS,
                            memory_mb=0,
                            driver_version="",
                            pci_id=""
                        ))
        except FileNotFoundError:
            # Try mthreads-smi as alternative
            try:
                result = subprocess.run(
                    ["mthreads-smi", "-l"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for idx, line in enumerate(result.stdout.split("\n")):
                        if "GPU" in line:
                            gpus.append(GPUInfo(
                                index=idx,
                                name="Moore Threads GPU",
                                vendor=GPUVendor.MOORE_THREADS,
                                memory_mb=0,
                                driver_version="",
                                pci_id=""
                            ))
            except FileNotFoundError:
                pass
        return gpus

    def start_stress(self) -> bool:
        """Start GPU stress workload for detected GPUs."""
        self._detected_gpus = self._detect_gpus()

        if not self._detected_gpus:
            return False

        self._stop_stress.clear()
        self._stress_threads = []

        # Start stress for each detected GPU based on vendor
        for gpu in self._detected_gpus:
            if gpu.vendor == GPUVendor.NVIDIA:
                self._start_nvidia_stress(gpu)
            elif gpu.vendor == GPUVendor.AMD:
                self._start_amd_stress(gpu)
            elif gpu.vendor == GPUVendor.HYGON:
                self._start_hygon_stress(gpu)
            elif gpu.vendor == GPUVendor.CAMBRICON:
                self._start_cambricon_stress(gpu)
            elif gpu.vendor == GPUVendor.ASCEND:
                self._start_ascend_stress(gpu)
            elif gpu.vendor == GPUVendor.MOORE_THREADS:
                self._start_moore_threads_stress(gpu)

        return len(self._stress_threads) > 0

    def _start_nvidia_stress(self, gpu: GPUInfo) -> None:
        """Start NVIDIA GPU stress."""
        # Try CUDA samples
        cuda_cmds = [
            ["deviceQuery"],
            ["bandwidthTest", "--device", str(gpu.index), "--mode=range"],
        ]
        for cmd in cuda_cmds:
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1)
                if proc.poll() is None:
                    self._stress_threads.append(("nvidia", proc))
                    return
            except FileNotFoundError:
                continue

    def _start_amd_stress(self, gpu: GPUInfo) -> None:
        """Start AMD GPU stress via ROCm."""
        # Try rocm bandwidth test or stress
        try:
            proc = subprocess.Popen(
                ["rocm-bandwidth-test", "-d", str(gpu.index)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._stress_threads.append(("amd", proc))
        except FileNotFoundError:
            pass

    def _start_hygon_stress(self, gpu: GPUInfo) -> None:
        """Start 海光 DCU stress."""
        # Hygon uses ROCm-compatible tools
        try:
            proc = subprocess.Popen(
                ["hygon-smi", "-d", str(gpu.index), "--ecc", "-e", "yes"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._stress_threads.append(("hygon", proc))
        except FileNotFoundError:
            pass

    def _start_cambricon_stress(self, gpu: GPUInfo) -> None:
        """Start 寒武纪 MLU stress."""
        # Cambricon has specific stress tools
        try:
            proc = subprocess.Popen(
                ["cnperf", "-dev", str(gpu.index)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._stress_threads.append(("cambricon", proc))
        except FileNotFoundError:
            pass

    def _start_ascend_stress(self, gpu: GPUInfo) -> None:
        """Start 华为昇腾 NPU stress."""
        # Ascend has specific stress test tools
        try:
            proc = subprocess.Popen(
                ["npu-smi", "stress", "-i", str(gpu.index)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._stress_threads.append(("ascend", proc))
        except FileNotFoundError:
            pass

    def _start_moore_threads_stress(self, gpu: GPUInfo) -> None:
        """Start 摩尔线程 GPU stress."""
        try:
            proc = subprocess.Popen(
                ["mthreads-gmi", "stress", "-i", str(gpu.index)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._stress_threads.append(("moore_threads", proc))
        except FileNotFoundError:
            pass

    def stop_stress(self) -> None:
        """Stop all GPU stress workloads."""
        self._stop_stress.set()

        for vendor, proc in self._stress_threads:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        self._stress_threads = []

        # Reset clocks for NVIDIA
        for gpu in self._detected_gpus:
            if gpu.vendor == GPUVendor.NVIDIA:
                try:
                    subprocess.run(
                        ["nvidia-smi", "-i", str(gpu.index), "-rgc"],
                        capture_output=True, timeout=5
                    )
                except:
                    pass

    def collect_metrics(self) -> Dict[str, float]:
        """Collect metrics from all GPUs."""
        metrics = {}

        for gpu in self._detected_gpus:
            gpu_metrics = self._get_metrics_by_vendor(gpu)

            # Aggregate metrics
            for key, value in gpu_metrics.items():
                full_key = f"gpu{gpu.index}_{key}"
                metrics[full_key] = value

        return metrics

    def _get_metrics_by_vendor(self, gpu: GPUInfo) -> Dict[str, float]:
        """Get metrics based on GPU vendor."""
        if gpu.vendor == GPUVendor.NVIDIA:
            return self._get_nvidia_metrics(gpu.index)
        elif gpu.vendor == GPUVendor.AMD:
            return self._get_amd_metrics(gpu.index)
        elif gpu.vendor == GPUVendor.HYGON:
            return self._get_hygon_metrics(gpu.index)
        elif gpu.vendor == GPUVendor.CAMBRICON:
            return self._get_cambricon_metrics(gpu.index)
        elif gpu.vendor == GPUVendor.ASCEND:
            return self._get_ascend_metrics(gpu.index)
        elif gpu.vendor == GPUVendor.MOORE_THREADS:
            return self._get_moore_threads_metrics(gpu.index)
        return {}

    def _get_nvidia_metrics(self, idx: int) -> Dict[str, float]:
        """Get NVIDIA GPU metrics."""
        metrics = {}
        try:
            result = subprocess.run(
                ["nvidia-smi", "-i", str(idx),
                 "--query-gpu=temperature.gpu,utilization.gpu,utilization.memory,power.draw,clocks.sm",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                values = [v.strip() for v in result.stdout.strip().split(",")]
                if len(values) >= 5:
                    metrics["temperature"] = float(values[0])
                    metrics["utilization"] = float(values[1])
                    metrics["memory_utilization"] = float(values[2])
                    metrics["power"] = float(values[3])
                    metrics["clock_speed"] = float(values[4])
        except:
            pass
        return metrics

    def _get_amd_metrics(self, idx: int) -> Dict[str, float]:
        """Get AMD GPU metrics via rocm-smi."""
        metrics = {}
        try:
            result = subprocess.run(
                ["rocm-smi", "-d", str(idx), "--showtemp", "--showuse", "--showpower", "--json"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                card = data.get("card_list", [{}])[0] if "card_list" in data else {}
                metrics["temperature"] = card.get("temperature", 0)
                metrics["utilization"] = card.get("gpu_use", 0)
                metrics["power"] = card.get("average_graphics_package_power", 0)
        except:
            pass
        return metrics

    def _get_hygon_metrics(self, idx: int) -> Dict[str, float]:
        """Get 海光 DCU metrics."""
        metrics = {}
        try:
            # Try hygon-smi first
            result = subprocess.run(
                ["hygon-smi", "-d", str(idx), "--query-gpu=temperature.gpu,utilization.gpu,power.draw",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                values = [v.strip() for v in result.stdout.strip().split(",")]
                if len(values) >= 3:
                    metrics["temperature"] = float(values[0])
                    metrics["utilization"] = float(values[1])
                    metrics["power"] = float(values[2])
        except:
            # Fallback to rocm-smi
            try:
                result = subprocess.run(
                    ["rocm-smi", "-d", str(idx), "--showtemp", "--showuse"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    # Parse text output
                    for line in result.stdout.split("\n"):
                        if "Temperature" in line:
                            metrics["temperature"] = float(line.split()[-1].replace("C", ""))
                        if "GPU use" in line:
                            metrics["utilization"] = float(line.split()[-1].replace("%", ""))
            except:
                pass
        return metrics

    def _get_cambricon_metrics(self, idx: int) -> Dict[str, float]:
        """Get 寒武纪 MLU metrics."""
        metrics = {}
        try:
            result = subprocess.run(
                ["cnmon"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Parse cnmon output for specific MLU
                lines = result.stdout.split("\n")
                for line in lines:
                    if f"mlu{idx}" in line.lower() or line.startswith(f"| {idx} "):
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if "C" in part and i > 0:
                                try:
                                    metrics["temperature"] = float(part.replace("C", "").replace("°", ""))
                                except:
                                    pass
                            if "%" in part:
                                try:
                                    metrics["utilization"] = float(part.replace("%", ""))
                                except:
                                    pass
        except:
            pass
        return metrics

    def _get_ascend_metrics(self, idx: int) -> Dict[str, float]:
        """Get 华为昇腾 NPU metrics."""
        metrics = {}
        try:
            result = subprocess.run(
                ["npu-smi", "info", "-t", "usages", "-i", str(idx)],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Parse npu-smi output
                for line in result.stdout.split("\n"):
                    if "Ai Core" in line or "NPU" in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if "%" in part:
                                try:
                                    metrics["utilization"] = float(part.replace("%", ""))
                                except:
                                    pass

            # Get temperature
            temp_result = subprocess.run(
                ["npu-smi", "info", "-t", "temperature", "-i", str(idx)],
                capture_output=True, text=True, timeout=5
            )
            if temp_result.returncode == 0:
                for line in temp_result.stdout.split("\n"):
                    if "C" in line:
                        try:
                            metrics["temperature"] = float(line.split()[-1].replace("C", "").replace("°", ""))
                        except:
                            pass
        except:
            pass
        return metrics

    def _get_moore_threads_metrics(self, idx: int) -> Dict[str, float]:
        """Get 摩尔线程 GPU metrics."""
        metrics = {}
        try:
            result = subprocess.run(
                ["mthreads-gmi", "-q", "-i", str(idx)],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Temperature" in line:
                        try:
                            metrics["temperature"] = float(line.split(":")[-1].strip().replace("C", ""))
                        except:
                            pass
                    if "GPU Utilization" in line or "Utilization" in line:
                        try:
                            metrics["utilization"] = float(line.split(":")[-1].strip().replace("%", ""))
                        except:
                            pass
                    if "Power Draw" in line:
                        try:
                            metrics["power"] = float(line.split(":")[-1].strip().replace("W", ""))
                        except:
                            pass
        except:
            pass
        return metrics

    def _parse_memory(self, memory_str: str) -> int:
        """Parse memory string to MB."""
        try:
            parts = memory_str.split()
            if len(parts) >= 1:
                value = float(parts[0])
                unit = parts[1].lower() if len(parts) > 1 else "mib"
                if "gib" in unit or "gb" in unit:
                    return int(value * 1024)
                elif "mib" in unit or "mb" in unit:
                    return int(value)
        except:
            pass
        return 0

    def get_detected_gpus(self) -> List[GPUInfo]:
        """Return list of detected GPUs."""
        if not self._detected_gpus:
            self._detected_gpus = self._detect_gpus()
        return self._detected_gpus
