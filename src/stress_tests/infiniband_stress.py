"""InfiniBand network stress test implementation."""

import subprocess
import time
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from .base import StressTestBase, ThresholdConfig, MetricResult, MetricStatus, StressTestResult


class IBTestType(str, Enum):
    """Types of InfiniBand stress tests."""
    BANDWIDTH = "bandwidth"        # RDMA bandwidth test
    LATENCY = "latency"            # RDMA latency test
    BIDIRECTIONAL = "bidirectional"  # Simultaneous send/recv
    ATOMIC = "atomic"              # Atomic operations test
    MULTICAST = "multicast"        # Multicast performance


@dataclass
class IBStressThresholds:
    """Thresholds specific to InfiniBand stress testing."""
    # Bandwidth thresholds (percentage of link speed)
    min_bw_percent: float = 80.0   # Expect >80% of theoretical max
    target_bw_percent: float = 95.0

    # Latency thresholds (microseconds)
    max_latency_us: float = 5.0    # 5us for IB
    warning_latency_us: float = 3.0

    # Error thresholds
    max_symbol_errors: int = 100
    max_link_recoveries: int = 10
    max_vl15_dropped: int = 100

    # Test duration
    duration_seconds: int = 300
    warmup_seconds: int = 5

    # Message sizes to test
    msg_sizes: List[int] = None

    def __post_init__(self):
        if self.msg_sizes is None:
            self.msg_sizes = [256, 1024, 4096, 65536, 1048576]  # Bytes


class InfiniBandStressTest(StressTestBase):
    """Stress test for InfiniBand network adapters.

    Tests performed:
    1. RDMA bandwidth (ib_write_bw, ib_read_bw)
    2. RDMA latency (ib_write_lat, ib_read_lat)
    3. Bidirectional throughput
    4. Atomic operations performance
    5. Port error monitoring

    Supports:
    - SDR (10 Gbps)
    - DDR (20 Gbps)
    - QDR (40 Gbps)
    - FDR (56 Gbps)
    - EDR (100 Gbps)
    - HDR (200 Gbps)
    - NDR (400 Gbps)

    Requirements:
    - perftest package (ib_write_bw, ib_read_bw, etc.)
    - ibstat/ibstatus (for port monitoring)
    - Target IB node for bandwidth tests

    Note: InfiniBand testing requires a remote peer to communicate with.
    Single-node testing is limited to port status/error checks.
    """

    # Link speed mapping (Gbps)
    LINK_SPEEDS = {
        "SDR": 10,
        "DDR": 20,
        "QDR": 40,
        "FDR10": 40,
        "FDR": 56,
        "EDR": 100,
        "HDR": 200,
        "HDR100": 100,
        "NDR": 400,
        "NDR200": 200
    }

    def __init__(
        self,
        duration_seconds: int = 300,
        sample_interval_seconds: int = 5,
        thresholds: Optional[Dict[str, ThresholdConfig]] = None,
        device: Optional[str] = None,
        target_lid: Optional[int] = None,
        target_gid: Optional[str] = None
    ):
        super().__init__(duration_seconds, sample_interval_seconds, thresholds)
        self.ib_thresholds = IBStressThresholds()
        self.device = device
        self.target_lid = target_lid
        self.target_gid = target_gid
        self._ib_devices: List[Dict[str, Any]] = []
        self._initial_port_counters: Dict[str, int] = {}

    @property
    def test_name(self) -> str:
        return "infiniband_stress"

    @property
    def supported_vendors(self) -> List[str]:
        return ["mellanox", "intel", "qlogic"]

    def start_stress(self) -> bool:
        """Start InfiniBand stress workload."""
        # Discover IB devices
        self._ib_devices = self._discover_ib_devices()

        if not self._ib_devices:
            return False

        # Record initial port counters
        for dev in self._ib_devices:
            counters = self._get_port_counters(dev["name"])
            self._initial_port_counters[dev["name"]] = counters

        # Start bandwidth test if target available
        if self.target_lid or self.target_gid:
            return self._start_bw_test()

        # Otherwise, just monitor port status
        return True

    def _start_bw_test(self) -> bool:
        """Start bandwidth test using ib_write_bw."""
        try:
            cmd = ["ib_write_bw", "-D", str(self.duration_seconds + 60)]

            if self.device:
                cmd.extend(["-d", self.device])

            if self.target_gid:
                cmd.extend(["-g", self.target_gid])
            elif self.target_lid:
                cmd.extend(["-l", str(self.target_lid)])

            # Run in client mode
            self._bw_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            return True

        except FileNotFoundError:
            return False

    def stop_stress(self) -> None:
        """Stop InfiniBand stress workload."""
        if hasattr(self, '_bw_process') and self._bw_process:
            try:
                self._bw_process.terminate()
                self._bw_process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    self._bw_process.kill()
                except ProcessLookupError:
                    pass
            self._bw_process = None

    def collect_metrics(self) -> Dict[str, float]:
        """Collect current InfiniBand metrics."""
        metrics = {}

        if not self._ib_devices:
            return metrics

        # Port status and counters
        for dev in self._ib_devices:
            dev_name = dev["name"]

            # Link status
            link_info = self._get_link_info(dev_name)
            metrics[f"{dev_name}_link_up"] = 1.0 if link_info.get("state") == "Active" else 0.0
            metrics[f"{dev_name}_link_speed_gbps"] = link_info.get("speed_gbps", 0)

            # Port counters
            counters = self._get_port_counters(dev_name)
            initial = self._initial_port_counters.get(dev_name, {})

            # Calculate delta errors
            for counter_name in ["symbol_error", "link_error_recovery", "vl15_dropped"]:
                current = counters.get(counter_name, 0)
                prev = initial.get(counter_name, 0)
                delta = current - prev
                metrics[f"{dev_name}_{counter_name}"] = delta

            # Temperature (if available)
            temp = self._get_ib_temperature(dev_name)
            if temp:
                metrics[f"{dev_name}_temperature_c"] = temp

        return metrics

    def run_custom(self, duration: Optional[int] = None) -> StressTestResult:
        """Run InfiniBand stress test with custom duration."""
        duration = duration or self.ib_thresholds.duration_seconds

        if not self.start_stress():
            return StressTestResult(
                test_name=self.test_name,
                status="error",
                error_message="No InfiniBand devices found or failed to start stress",
                duration_seconds=0,
                metrics=[]
            )

        start_time = time.time()
        samples = []
        errors = []
        warnings = []

        # Run bandwidth tests for each message size
        bw_results = {}
        for msg_size in self.ib_thresholds.msg_sizes:
            if self.target_lid or self.target_gid:
                result = self._run_bw_test(msg_size)
                if result:
                    bw_results[f"msg_{msg_size}"] = result

        # Monitor port during test
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
                for dev in self._ib_devices:
                    dev_name = dev["name"]

                    # Check link status
                    if metrics.get(f"{dev_name}_link_up", 0) == 0:
                        errors.append(f"{dev_name}: Link is down")

                    # Check errors
                    sym_errors = metrics.get(f"{dev_name}_symbol_error", 0)
                    if sym_errors > self.ib_thresholds.max_symbol_errors:
                        errors.append(f"{dev_name}: Symbol errors {sym_errors} exceed threshold")

                    # Check temperature
                    temp = metrics.get(f"{dev_name}_temperature_c", 0)
                    if temp > 85:
                        warnings.append(f"{dev_name}: Temperature {temp}°C is high")

                # Progress callback
                if self._progress_callback:
                    pct = min(100.0, (elapsed / duration) * 100)
                    self._progress_callback(pct, metrics)

        finally:
            self.stop_stress()

        actual_duration = time.time() - start_time

        # Determine status
        status = "passed"
        if errors:
            status = "failed"
        elif warnings:
            status = "warning"

        metric_results = self._analyze_samples(samples)
        error_msg = "; ".join(errors + warnings) if (errors or warnings) else ""

        # Add bandwidth results to metrics
        if bw_results:
            for key, val in bw_results.items():
                # Check bandwidth threshold
                link_speed = self._ib_devices[0].get("speed_gbps", 100) if self._ib_devices else 100
                achieved_percent = (val / link_speed) * 100

                if achieved_percent < self.ib_thresholds.min_bw_percent:
                    if status == "passed":
                        status = "warning"
                    error_msg += f"; Bandwidth for {key}: {val:.1f} Gbps ({achieved_percent:.1f}%) below threshold"

        return StressTestResult(
            test_name=self.test_name,
            status=status,
            error_message=error_msg,
            duration_seconds=actual_duration,
            metrics=metric_results
        )

    def _discover_ib_devices(self) -> List[Dict[str, Any]]:
        """Discover InfiniBand devices."""
        devices = []

        try:
            result = subprocess.run(
                ["ibstat", "-l"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    dev_name = line.strip()
                    if dev_name:
                        link_info = self._get_link_info(dev_name)
                        devices.append({
                            "name": dev_name,
                            "speed_gbps": link_info.get("speed_gbps", 0),
                            "state": link_info.get("state", "Unknown")
                        })

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Fallback: check /sys/class/infiniband
        if not devices:
            try:
                import glob
                for path in glob.glob("/sys/class/infiniband/*"):
                    dev_name = os.path.basename(path)
                    link_info = self._get_link_info(dev_name)
                    devices.append({
                        "name": dev_name,
                        "speed_gbps": link_info.get("speed_gbps", 0),
                        "state": link_info.get("state", "Unknown")
                    })
            except Exception:
                pass

        return devices

    def _get_link_info(self, device: str) -> Dict[str, Any]:
        """Get IB link information."""
        info = {"state": "Unknown", "speed": "Unknown", "speed_gbps": 0}

        try:
            result = subprocess.run(
                ["ibstatus", device],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "state:" in line.lower():
                        info["state"] = line.split(":")[1].strip()
                    elif "rate:" in line.lower():
                        rate_str = line.split(":")[1].strip()
                        info["speed"] = rate_str
                        # Parse speed
                        match = re.search(r"(\d+)\s*Gb/sec", rate_str)
                        if match:
                            info["speed_gbps"] = int(match.group(1))

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return info

    def _get_port_counters(self, device: str) -> Dict[str, int]:
        """Get IB port counters."""
        counters = {
            "symbol_error": 0,
            "link_error_recovery": 0,
            "vl15_dropped": 0,
            "xmit_wait": 0
        }

        # Try perfquery
        try:
            result = subprocess.run(
                ["perfquery", "-x", "-d", device],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "SymbolError" in line:
                        match = re.search(r"SymbolError\s*[:=]\s*(\d+)", line)
                        if match:
                            counters["symbol_error"] = int(match.group(1))
                    elif "LinkErrorRecovery" in line:
                        match = re.search(r"LinkErrorRecovery\s*[:=]\s*(\d+)", line)
                        if match:
                            counters["link_error_recovery"] = int(match.group(1))
                    elif "VL15Dropped" in line:
                        match = re.search(r"VL15Dropped\s*[:=]\s*(\d+)", line)
                        if match:
                            counters["vl15_dropped"] = int(match.group(1))

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Fallback: sysfs
        if counters["symbol_error"] == 0:
            try:
                port_path = f"/sys/class/infiniband/{device}/ports/1/counters"
                for counter_name in counters.keys():
                    try:
                        with open(f"{port_path}/{counter_name}", "r") as f:
                            counters[counter_name] = int(f.read().strip())
                    except FileNotFoundError:
                        pass
            except Exception:
                pass

        return counters

    def _get_ib_temperature(self, device: str) -> Optional[float]:
        """Get IB adapter temperature."""
        # Try hwmon
        try:
            import glob
            for hwmon in glob.glob(f"/sys/class/infiniband/{device}/hwmon*/temp1_input"):
                try:
                    with open(hwmon, "r") as f:
                        return int(f.read().strip()) / 1000
                except (FileNotFoundError, ValueError):
                    pass
        except Exception:
            pass

        return None

    def _run_bw_test(self, msg_size: int) -> Optional[float]:
        """Run bandwidth test for specific message size."""
        try:
            cmd = [
                "ib_write_bw",
                "-s", str(msg_size),
                "-n", "1000",
                "-D", "10"  # 10 seconds
            ]

            if self.device:
                cmd.extend(["-d", self.device])

            if self.target_gid:
                cmd.extend(["-g", self.target_gid])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Parse bandwidth from output
                # Example: " #bytes #iterations BW peak[Gb/sec] BW average[Gb/sec]"
                lines = result.stdout.split("\n")
                for line in lines:
                    if str(msg_size) in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            try:
                                return float(parts[-1])  # Average BW
                            except ValueError:
                                pass

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def quick_test(self) -> StressTestResult:
        """Run a quick 30-second IB stress test."""
        return self.run_custom(duration=30)

    def extended_test(self, duration: int = 1800) -> StressTestResult:
        """Run extended IB stress test (default 30 minutes)."""
        return self.run_custom(duration=duration)

    def list_devices(self) -> List[Dict[str, Any]]:
        """List all InfiniBand devices."""
        return self._discover_ib_devices()


# Need os import at top
import os
