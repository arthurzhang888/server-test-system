"""Memory (RAM/DIMM) stress test implementation."""

import subprocess
import time
import re
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from .base import StressTestBase, ThresholdConfig, MetricResult, MetricStatus, StressTestResult


class MemoryTestType(str, Enum):
    """Types of memory stress tests."""
    ALLOCATION = "allocation"      # Memory allocation stress
    READ_WRITE = "read_write"      # Sequential read/write
    RANDOM_ACCESS = "random"       # Random access pattern
    ECC = "ecc"                    # ECC error detection
    BANDWIDTH = "bandwidth"        # Memory bandwidth test


@dataclass
class MemoryStressThresholds:
    """Thresholds specific to memory stress testing."""
    # Temperature thresholds (DIMM temperature via ipmi-sensors)
    max_temperature_c: float = 85.0
    warning_temperature_c: float = 75.0

    # Memory usage thresholds
    max_memory_usage_percent: float = 95.0
    target_memory_usage_percent: float = 90.0

    # ECC error thresholds (errors per hour)
    max_ecc_errors: int = 10
    max_ce_errors: int = 100  # Correctable errors

    # Bandwidth thresholds (percentage of theoretical max)
    min_bandwidth_percent: float = 80.0

    # Latency thresholds (nanoseconds)
    max_latency_ns: float = 100.0

    # Test duration
    duration_seconds: int = 300
    warmup_seconds: int = 10


class MemoryStressTest(StressTestBase):
    """Stress test for system memory (RAM/DIMM).

    Tests performed:
    1. Memory allocation and fill test
    2. Sequential read/write bandwidth
    3. Random access pattern
    4. ECC error detection (if available)
    5. DIMM temperature monitoring (via IPMI)

    Requirements:
    - memtester (for allocation testing)
    - stress-ng (for load generation)
    - dmidecode (for DIMM info)
    - ipmitool/ipmi-sensors (for temperature)
    - stream/mlc (for bandwidth testing, optional)

    Note: Running memory stress tests will consume significant system
    memory and may impact other processes. Use with caution on production
    systems.
    """

    def __init__(
        self,
        duration_seconds: int = 300,
        sample_interval_seconds: int = 5,
        thresholds: Optional[Dict[str, ThresholdConfig]] = None,
        memory_percent: float = 80.0  # Percentage of free memory to use
    ):
        super().__init__(duration_seconds, sample_interval_seconds, thresholds)
        self.mem_thresholds = MemoryStressThresholds()
        self.memory_percent = memory_percent
        self._stress_process: Optional[subprocess.Popen] = None
        self._initial_ecc_errors: int = 0

    @property
    def test_name(self) -> str:
        return "memory_stress"

    @property
    def supported_vendors(self) -> List[str]:
        return ["generic", "samsung", "micron", "hynix", "kingston"]

    def start_stress(self) -> bool:
        """Start memory stress workload."""
        # Get available memory
        mem_info = self._get_memory_info()
        total_gb = mem_info.get("total_gb", 8)
        free_gb = mem_info.get("free_gb", 4)

        # Calculate stress memory size
        stress_gb = min(free_gb * (self.memory_percent / 100), total_gb * 0.8)
        stress_mb = int(stress_gb * 1024)

        if stress_mb < 512:  # Minimum 512MB
            print(f"Warning: Limited memory for stress test ({stress_mb}MB)")
            stress_mb = min(stress_mb, 256)

        # Method 1: Try stress-ng (most flexible)
        try:
            self._stress_process = subprocess.Popen(
                [
                    "stress-ng",
                    "--vm", "4",                    # 4 VM stressors
                    "--vm-bytes", f"{stress_mb // 4}M",  # Each gets portion
                    "--vm-keep",                    # Keep memory allocated
                    "--vm-method", "all",           # All access patterns
                    "--timeout", f"{self.duration_seconds + 60}s",
                    "--quiet"
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True

        except FileNotFoundError:
            pass

        # Method 2: Try memtester
        try:
            test_mb = min(stress_mb, 1024)  # memtester limit
            self._stress_process = subprocess.Popen(
                ["memtester", f"{test_mb}M", "1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return True

        except FileNotFoundError:
            pass

        # Method 3: Python-based memory stress
        return self._start_python_stress(stress_mb)

    def _start_python_stress(self, stress_mb: int) -> bool:
        """Fallback Python-based memory stress."""
        try:
            # Allocate memory blocks
            block_size = 64 * 1024 * 1024  # 64MB blocks
            num_blocks = stress_mb // 64

            self._memory_blocks = []
            for _ in range(num_blocks):
                # Allocate and touch memory
                block = bytearray(block_size)
                # Write pattern
                for i in range(0, block_size, 4096):
                    block[i] = i % 256
                self._memory_blocks.append(block)

            return True

        except MemoryError:
            return False

    def stop_stress(self) -> None:
        """Stop memory stress workload."""
        if self._stress_process:
            try:
                self._stress_process.terminate()
                self._stress_process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    self._stress_process.kill()
                except ProcessLookupError:
                    pass
            self._stress_process = None

        # Clean up Python memory blocks
        if hasattr(self, '_memory_blocks'):
            self._memory_blocks.clear()

    def collect_metrics(self) -> Dict[str, float]:
        """Collect current memory metrics."""
        metrics = {}

        # Memory usage
        mem_info = self._get_memory_info()
        metrics["memory_usage_percent"] = mem_info.get("usage_percent", 0)
        metrics["memory_used_gb"] = mem_info.get("used_gb", 0)
        metrics["memory_available_gb"] = mem_info.get("available_gb", 0)

        # DIMM temperatures (if available)
        temps = self._get_dimm_temperatures()
        if temps:
            metrics["dimm_max_temperature_c"] = max(temps)
            metrics["dimm_avg_temperature_c"] = sum(temps) / len(temps)

        # ECC errors
        ecc_errors = self._get_ecc_error_count()
        if ecc_errors is not None:
            metrics["ecc_errors"] = ecc_errors

        # Memory bandwidth (if stream/mlc available)
        bandwidth = self._get_memory_bandwidth()
        if bandwidth:
            metrics["memory_bandwidth_gbps"] = bandwidth

        return metrics

    def run_custom(self, duration: Optional[int] = None) -> StressTestResult:
        """Run memory stress test with custom duration."""
        duration = duration or self.mem_thresholds.duration_seconds

        # Record initial ECC error count
        self._initial_ecc_errors = self._get_ecc_error_count() or 0

        # Run the stress test
        start_time = time.time()

        if not self.start_stress():
            return StressTestResult(
                test_name=self.test_name,
                status="error",
                error_message="Failed to start memory stress workload",
                duration_seconds=0,
                metrics=[]
            )

        samples = []
        errors = []
        warnings = []

        try:
            elapsed = 0
            while elapsed < duration:
                time.sleep(self.sample_interval_seconds)
                elapsed = time.time() - start_time

                metrics = self.collect_metrics()
                samples.append({
                    "timestamp": time.time(),
                    "elapsed_seconds": elapsed,
                    "metrics": metrics
                })

                # Check thresholds
                if metrics.get("dimm_max_temperature_c", 0) > self.mem_thresholds.max_temperature_c:
                    errors.append(f"DIMM temperature {metrics['dimm_max_temperature_c']}°C exceeds threshold")

                if metrics.get("memory_usage_percent", 0) > self.mem_thresholds.max_memory_usage_percent:
                    errors.append(f"Memory usage {metrics['memory_usage_percent']}% exceeds threshold")

                # Check for new ECC errors
                current_ecc = metrics.get("ecc_errors", self._initial_ecc_errors)
                new_errors = current_ecc - self._initial_ecc_errors
                if new_errors > self.mem_thresholds.max_ecc_errors:
                    errors.append(f"ECC errors detected: {new_errors}")

                # Report progress
                if self._progress_callback:
                    pct = min(100.0, (elapsed / duration) * 100)
                    self._progress_callback(pct, metrics)

        finally:
            self.stop_stress()

        # Analyze results
        actual_duration = time.time() - start_time

        # Calculate final ECC errors
        final_ecc = self._get_ecc_error_count() or 0
        total_new_errors = final_ecc - self._initial_ecc_errors

        # Determine status
        status = "passed"
        if errors:
            status = "failed"
        elif warnings:
            status = "warning"
        elif total_new_errors > 0:
            status = "warning"
            warnings.append(f"{total_new_errors} ECC errors detected during test")

        # Convert samples to metric results
        metric_results = self._analyze_samples(samples)

        # Build error message
        error_msg = "; ".join(errors + warnings) if (errors or warnings) else ""

        return StressTestResult(
            test_name=self.test_name,
            status=status,
            error_message=error_msg,
            duration_seconds=actual_duration,
            metrics=metric_results
        )

    def _get_memory_info(self) -> Dict[str, float]:
        """Get memory information from /proc/meminfo."""
        info = {
            "total_gb": 0,
            "free_gb": 0,
            "available_gb": 0,
            "used_gb": 0,
            "usage_percent": 0
        }

        try:
            with open("/proc/meminfo", "r") as f:
                content = f.read()

            mem_total = 0
            mem_free = 0
            mem_available = 0

            for line in content.split("\n"):
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1]) / (1024 * 1024)  # Convert to GB
                elif line.startswith("MemFree:"):
                    mem_free = int(line.split()[1]) / (1024 * 1024)
                elif line.startswith("MemAvailable:"):
                    mem_available = int(line.split()[1]) / (1024 * 1024)

            info["total_gb"] = mem_total
            info["free_gb"] = mem_free
            info["available_gb"] = mem_available
            info["used_gb"] = mem_total - mem_available

            if mem_total > 0:
                info["usage_percent"] = (info["used_gb"] / mem_total) * 100

        except (FileNotFoundError, ValueError):
            pass

        return info

    def _get_dimm_temperatures(self) -> List[float]:
        """Get DIMM temperatures via ipmi-sensors or sysfs."""
        temps = []

        # Method 1: ipmi-sensors
        try:
            result = subprocess.run(
                ["ipmi-sensors", "--sensors-type", "Memory"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if " degrees C" in line:
                        match = re.search(r"(\d+\.?\d*)\s*degrees C", line)
                        if match:
                            temps.append(float(match.group(1)))

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Method 2: ipmitool sdr
        if not temps:
            try:
                result = subprocess.run(
                    ["ipmitool", "sdr", "type", "Memory"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        match = re.search(r"(\d+)\s*degrees C", line)
                        if match:
                            temps.append(float(match.group(1)))

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # Method 3: hwmon (some systems expose DIMM temps)
        if not temps:
            try:
                import glob
                for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
                    name_file = f"{hwmon}/name"
                    try:
                        with open(name_file, 'r') as f:
                            name = f.read().strip()
                            if "dimm" in name.lower() or "memory" in name.lower():
                                for temp_input in glob.glob(f"{hwmon}/temp*_input"):
                                    try:
                                        with open(temp_input, 'r') as f:
                                            temp = int(f.read().strip()) / 1000
                                            temps.append(temp)
                                    except (FileNotFoundError, ValueError):
                                        pass
                    except FileNotFoundError:
                        pass

            except Exception:
                pass

        return temps

    def _get_ecc_error_count(self) -> Optional[int]:
        """Get ECC error count from EDAC or mcelog."""
        errors = 0
        found = False

        # Method 1: EDAC (Error Detection and Correction)
        try:
            import glob

            # Look for EDAC counters
            edac_paths = glob.glob("/sys/devices/system/edac/mc/mc*/ce_count")
            for path in edac_paths:
                try:
                    with open(path, 'r') as f:
                        errors += int(f.read().strip())
                        found = True
                except (FileNotFoundError, ValueError):
                    pass

            # Also check UE (uncorrectable) errors
            ue_paths = glob.glob("/sys/devices/system/edac/mc/mc*/ue_count")
            for path in ue_paths:
                try:
                    with open(path, 'r') as f:
                        errors += int(f.read().strip())
                        found = True
                except (FileNotFoundError, ValueError):
                    pass

        except Exception:
            pass

        # Method 2: mcelog
        if not found:
            try:
                result = subprocess.run(
                    ["mcelog", "--client"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0:
                    # Parse mcelog output for memory errors
                    for line in result.stdout.split("\n"):
                        if "memory" in line.lower() and "error" in line.lower():
                            errors += 1
                            found = True

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # Method 3: ras-mc-ctl
        if not found:
            try:
                result = subprocess.run(
                    ["ras-mc-ctl", "--error-count"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        match = re.search(r"(\d+)\s*total errors", line)
                        if match:
                            errors = int(match.group(1))
                            found = True

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        return errors if found else None

    def _get_memory_bandwidth(self) -> Optional[float]:
        """Get memory bandwidth if stream or mlc is available."""
        # This would require running a bandwidth benchmark
        # For now, return None - can be enhanced with actual benchmarks
        return None

    def run_bandwidth_test(self) -> Dict[str, Any]:
        """Run memory bandwidth test using stream or available tools."""
        result = {
            "copy_gbps": None,
            "scale_gbps": None,
            "add_gbps": None,
            "triad_gbps": None
        }

        # Try stream benchmark
        try:
            proc = subprocess.run(
                ["./stream_c.exe"],  # Must be compiled locally
                capture_output=True,
                text=True,
                timeout=60,
                cwd="/tmp"  # Assume compiled in /tmp
            )

            if proc.returncode == 0:
                for line in proc.stdout.split("\n"):
                    if "Copy:" in line:
                        match = re.search(r"Copy:\s+(\d+\.?\d*)", line)
                        if match:
                            result["copy_gbps"] = float(match.group(1))
                    elif "Scale:" in line:
                        match = re.search(r"Scale:\s+(\d+\.?\d*)", line)
                        if match:
                            result["scale_gbps"] = float(match.group(1))
                    elif "Add:" in line:
                        match = re.search(r"Add:\s+(\d+\.?\d*)", line)
                        if match:
                            result["add_gbps"] = float(match.group(1))
                    elif "Triad:" in line:
                        match = re.search(r"Triad:\s+(\d+\.?\d*)", line)
                        if match:
                            result["triad_gbps"] = float(match.group(1))

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return result

    def quick_test(self) -> StressTestResult:
        """Run a quick 60-second memory stress test."""
        return self.run_custom(duration=60)

    def extended_test(self, duration: int = 1800) -> StressTestResult:
        """Run extended memory stress test (default 30 minutes)."""
        return self.run_custom(duration=duration)

    def get_dimm_info(self) -> List[Dict[str, Any]]:
        """Get detailed DIMM information."""
        dimms = []

        try:
            result = subprocess.run(
                ["dmidecode", "-t", "17"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                current_dimm = {}

                for line in result.stdout.split("\n"):
                    if line.strip().startswith("Memory Device"):
                        if current_dimm:
                            dimms.append(current_dimm)
                        current_dimm = {}
                    elif ":" in line and current_dimm is not None:
                        key, value = line.split(":", 1)
                        key = key.strip().lower().replace(" ", "_")
                        value = value.strip()
                        current_dimm[key] = value

                if current_dimm:
                    dimms.append(current_dimm)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return dimms
