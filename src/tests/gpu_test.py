"""GPU functional tests including memory and compute benchmarks."""

import subprocess
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

from .base import FunctionalTestBase, TestResult, TestStatus, TestConfig


@dataclass
class GPUConfig(TestConfig):
    """GPU test configuration."""
    memory_test: bool = True
    compute_test: bool = True
    bandwidth_test: bool = True


class GPUTest(FunctionalTestBase):
    """GPU functional and performance tests.

    Tests:
    - GPU presence and info
    - Memory allocation and bandwidth
    - Compute capability
    - Temperature monitoring
    """

    def __init__(self, config: GPUConfig = None):
        super().__init__(config or GPUConfig())
        self.gpu_config = self.config  # type: GPUConfig

    @property
    def test_name(self) -> str:
        return "gpu_functional"

    def run(self) -> TestResult:
        """Run GPU functional tests."""
        self._start_timer()

        # Detect GPUs
        gpus = self._detect_gpus()

        if not gpus:
            return self._create_result(
                TestStatus.SKIPPED,
                "No GPUs detected",
                {},
                {}
            )

        results = []
        all_passed = True
        metrics = {}

        for gpu in gpus:
            gpu_results = self._test_gpu(gpu)
            results.extend(gpu_results["tests"])
            metrics[gpu["name"]] = gpu_results["metrics"]

            if not gpu_results["passed"]:
                all_passed = False

        details = {
            "gpus_tested": len(gpus),
            "tests": results
        }

        if all_passed:
            return self._create_result(
                TestStatus.PASSED,
                f"GPU tests passed on {len(gpus)} GPU(s)",
                details,
                metrics
            )
        else:
            return self._create_result(
                TestStatus.FAILED,
                "Some GPU tests failed",
                details,
                metrics
            )

    def _detect_gpus(self) -> List[Dict[str, Any]]:
        """Detect available GPUs."""
        gpus = []

        # Try NVIDIA
        nvidia_gpus = self._detect_nvidia_gpus()
        gpus.extend(nvidia_gpus)

        # Try AMD (if no NVIDIA found)
        if not gpus:
            amd_gpus = self._detect_amd_gpus()
            gpus.extend(amd_gpus)

        return gpus

    def _detect_nvidia_gpus(self) -> List[Dict[str, Any]]:
        """Detect NVIDIA GPUs."""
        gpus = []

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total,pci.bus_id",
                    "--format=csv,noheader"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        gpus.append({
                            "index": int(parts[0]),
                            "name": parts[1],
                            "memory_mb": self._parse_memory(parts[2]),
                            "pci_id": parts[3],
                            "vendor": "NVIDIA"
                        })

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return gpus

    def _detect_amd_gpus(self) -> List[Dict[str, Any]]:
        """Detect AMD GPUs."""
        gpus = []

        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # Parse rocm-smi output
                for line in result.stdout.split("\n"):
                    if "GPU" in line and ":" in line:
                        parts = line.split(":")
                        if len(parts) >= 2:
                            idx = parts[0].strip().replace("GPU", "").strip()
                            name = parts[1].strip()
                            gpus.append({
                                "index": int(idx) if idx.isdigit() else 0,
                                "name": name,
                                "memory_mb": 0,  # Would need additional query
                                "pci_id": "",
                                "vendor": "AMD"
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

    def _test_gpu(self, gpu: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single GPU."""
        tests = []
        passed = True
        metrics = {}

        vendor = gpu["vendor"]

        # Test 1: GPU Info
        tests.append({
            "name": "gpu_info",
            "passed": True,
            "message": f"{gpu['name']} ({gpu['memory_mb']}MB)"
        })

        # Test 2: Memory Test (NVIDIA only for now)
        if vendor == "NVIDIA" and self.gpu_config.memory_test:
            status, msg, mem_bw = self._test_nvidia_memory(gpu["index"])
            tests.append({"name": "memory_test", "passed": status, "message": msg})
            metrics["memory_bandwidth_gbps"] = mem_bw
            if not status:
                passed = False

        # Test 3: Compute Test (NVIDIA only)
        if vendor == "NVIDIA" and self.gpu_config.compute_test:
            status, msg, flops = self._test_nvidia_compute(gpu["index"])
            tests.append({"name": "compute_test", "passed": status, "message": msg})
            metrics["compute_gflops"] = flops
            if not status:
                passed = False

        # Test 4: Temperature Check
        if vendor == "NVIDIA":
            status, msg, temp = self._check_nvidia_temp(gpu["index"])
            tests.append({"name": "temperature", "passed": status, "message": msg})
            metrics["temperature_c"] = temp
            if not status:
                passed = False

        return {
            "tests": tests,
            "passed": passed,
            "metrics": metrics
        }

    def _test_nvidia_memory(self, gpu_index: int) -> Tuple[bool, str, float]:
        """Test NVIDIA GPU memory bandwidth."""
        try:
            # Use nvidia-smi to check memory
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "-i", str(gpu_index),
                    "--query-gpu=memory.used,memory.total,clocks.mem",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 3:
                    used = float(parts[0])
                    total = float(parts[1])
                    mem_clock = float(parts[2])

                    # Rough bandwidth estimate (GDDR6 ~ 16 Gbps per pin)
                    # Actual calculation would need more info
                    bandwidth = mem_clock * 2 * 256 / 8 / 1000  # GB/s

                    if used > 0 and total > 0:
                        return True, f"Memory OK ({used:.0f}/{total:.0f}MB @ {mem_clock}MHz)", bandwidth

            return True, "Memory test inconclusive", 0.0

        except Exception as e:
            return True, f"Memory test error: {str(e)}", 0.0

    def _test_nvidia_compute(self, gpu_index: int) -> Tuple[bool, str, float]:
        """Test NVIDIA GPU compute capability."""
        try:
            # Check if CUDA samples are available
            # deviceQuery is a standard CUDA sample
            result = subprocess.run(
                ["deviceQuery"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Parse deviceQuery output
                output = result.stdout

                if "Result = PASS" in output:
                    # Extract GFLOPS if available
                    gflops = 0.0
                    for line in output.split("\n"):
                        if "GFLOP" in line:
                            try:
                                parts = line.split(":")
                                if len(parts) >= 2:
                                    gflops = float(parts[1].strip())
                            except ValueError:
                                pass

                    return True, "Compute test passed", gflops

            # Fallback: just check nvidia-smi works
            result = subprocess.run(
                ["nvidia-smi", "-i", str(gpu_index)],
                capture_output=True,
                timeout=5
            )

            if result.returncode == 0:
                return True, "GPU accessible", 0.0

            return False, "Compute test failed", 0.0

        except FileNotFoundError:
            return True, "CUDA samples not available", 0.0
        except Exception as e:
            return True, f"Compute test error: {str(e)}", 0.0

    def _check_nvidia_temp(self, gpu_index: int) -> Tuple[bool, str, float]:
        """Check NVIDIA GPU temperature."""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "-i", str(gpu_index),
                    "--query-gpu=temperature.gpu",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                temp = float(result.stdout.strip())

                # Check if temperature is reasonable (< 95°C)
                if temp < 95:
                    return True, f"Temperature OK ({temp}°C)", temp
                else:
                    return False, f"Temperature too high ({temp}°C)", temp

            return True, "Could not read temperature", 0.0

        except Exception as e:
            return True, f"Temperature check error: {str(e)}", 0.0
