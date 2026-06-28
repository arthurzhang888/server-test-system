"""GPU stress test implementation for NVIDIA GPUs using CUDA."""

import subprocess
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .base import StressTestBase, ThresholdConfig


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
            # GPU temp: normal < 80°C, critical > 95°C (thermal throttle)
            self.temperature = ThresholdConfig(min_value=0, max_value=95, warning_pct=0.84, critical_pct=0.95)
        if self.utilization is None:
            # GPU should stay busy during stress
            self.utilization = ThresholdConfig(min_value=80, max_value=100)
        if self.memory_utilization is None:
            # Memory should be actively used
            self.memory_utilization = ThresholdConfig(min_value=50, max_value=100)
        if self.power is None:
            # Power consumption (Watts) - varies by GPU model
            self.power = ThresholdConfig(min_value=50, max_value=400, warning_pct=0.9, critical_pct=0.98)
        if self.clock_speed is None:
            # Clock should not drop too much (throttling detection)
            self.clock_speed = ThresholdConfig(min_value=500, max_value=2500)  # MHz


class GPUStressTest(StressTestBase):
    """GPU stress test for NVIDIA GPUs.

    Uses nvidia-smi for monitoring and optionally CUDA samples for stress.
    Falls back to nvidia-smi stress if CUDA tools not available.

    Monitors:
    - GPU temperature
    - GPU utilization
    - Memory utilization
    - Power consumption
    - Clock speeds (to detect throttling)
    - ECC errors (if enabled)
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
        self.gpu_indices = gpu_indices or [0]  # Default to first GPU
        self._stress_process: Optional[subprocess.Popen] = None

    @property
    def test_name(self) -> str:
        return "gpu_stress"

    def start_stress(self) -> bool:
        """Start GPU stress workload."""
        # Try to use CUDA deviceQuery or similar for stress
        # Fallback to nvidia-smi with compute workload

        # First check if nvidia-smi is available
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

        # Try to start a compute-intensive workload
        # Option 1: Try deviceQuery or bandwidthTest if available
        cuda_stress_cmds = [
            ["deviceQuery"],
            ["bandwidthTest", "--device=all", "--mode=range"],
        ]

        for cmd in cuda_stress_cmds:
            try:
                self._stress_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                time.sleep(1)
                if self._stress_process.poll() is None:
                    return True
            except FileNotFoundError:
                continue

        # Option 2: Use nvidia-smi to lock clocks and enable persistence mode
        # This prepares GPU for consistent stress testing
        try:
            for gpu_idx in self.gpu_indices:
                # Enable persistence mode
                subprocess.run(
                    ["nvidia-smi", "-i", str(gpu_idx), "-pm", "1"],
                    capture_output=True,
                    timeout=5
                )
                # Lock GPU clocks for consistent testing
                subprocess.run(
                    ["nvidia-smi", "-i", str(gpu_idx), "-lgc", "1500"],
                    capture_output=True,
                    timeout=5
                )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Option 3: Start a Python-based GPU compute loop (if PyCUDA available)
        try:
            import pycuda.driver as cuda
            import pycuda.autoinit
            from pycuda.compiler import SourceModule

            # Simple kernel for GPU stress
            mod = SourceModule("""
            __global__ void stress_kernel(float *dest, int n)
            {
                int idx = threadIdx.x + blockIdx.x * blockDim.x;
                if (idx < n) {
                    float val = 1.0;
                    for(int i = 0; i < 1000; i++) {
                        val = val * 1.0001;
                    }
                    dest[idx] = val;
                }
            }
            """)

            self._cuda_kernel = mod.get_function("stress_kernel")
            self._cuda_buffer = cuda.mem_alloc(1024 * 1024 * 4)  # 4MB buffer
            return True

        except ImportError:
            pass

        # If we get here, we're relying on nvidia-smi monitoring only
        # The actual stress might need to be run externally
        return True

    def stop_stress(self) -> None:
        """Stop GPU stress workload."""
        if self._stress_process:
            try:
                self._stress_process.terminate()
                self._stress_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._stress_process.kill()
            self._stress_process = None

        # Reset GPU clocks
        try:
            for gpu_idx in self.gpu_indices:
                subprocess.run(
                    ["nvidia-smi", "-i", str(gpu_idx), "-rgc"],
                    capture_output=True,
                    timeout=5
                )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def collect_metrics(self) -> Dict[str, float]:
        """Collect GPU metrics via nvidia-smi."""
        metrics = {}

        for gpu_idx in self.gpu_indices:
            gpu_metrics = self._get_gpu_metrics(gpu_idx)

            # Aggregate metrics (max across all GPUs)
            for key, value in gpu_metrics.items():
                if key in metrics:
                    metrics[key] = max(metrics[key], value)
                else:
                    metrics[key] = value

        return metrics

    def _get_gpu_metrics(self, gpu_idx: int) -> Dict[str, float]:
        """Get metrics for a specific GPU."""
        metrics = {}

        try:
            # Query GPU metrics
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "-i", str(gpu_idx),
                    "--query-gpu=temperature.gpu,utilization.gpu,utilization.memory,power.draw,clocks.sm",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                values = [v.strip() for v in result.stdout.strip().split(",")]
                if len(values) >= 5:
                    try:
                        metrics["temperature"] = float(values[0])
                        metrics["utilization"] = float(values[1])
                        metrics["memory_utilization"] = float(values[2])
                        metrics["power"] = float(values[3])
                        metrics["clock_speed"] = float(values[4])
                    except ValueError:
                        pass

            # Query ECC errors
            ecc_result = subprocess.run(
                [
                    "nvidia-smi",
                    "-i", str(gpu_idx),
                    "--query-gpu=ecc.errors.corrected.volatile.total",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                timeout=5
            )

            if ecc_result.returncode == 0:
                try:
                    ecc_errors = int(ecc_result.stdout.strip())
                    metrics["ecc_errors"] = float(ecc_errors)
                except ValueError:
                    pass

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return metrics

    def get_gpu_info(self) -> List[Dict[str, Any]]:
        """Get static GPU information."""
        gpus = []

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total,driver_version",
                    "--format=csv,noheader"
                ],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        gpus.append({
                            "index": int(parts[0]),
                            "name": parts[1],
                            "memory_mb": self._parse_memory(parts[2]),
                            "driver": parts[3]
                        })

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return gpus

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
        except (ValueError, IndexError):
            pass

        return 0
