"""CPU stress test implementation using stress-ng or fallback to Python CPU load."""

import subprocess
import threading
import time
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .base import StressTestBase, ThresholdConfig


@dataclass
class CPUThresholds:
    """Predefined threshold configurations for CPU stress test."""
    temperature: ThresholdConfig = None
    utilization: ThresholdConfig = None
    frequency: ThresholdConfig = None

    def __post_init__(self):
        if self.temperature is None:
            # CPU temp: normal < 80°C, warning at 85°C, critical > 95°C
            self.temperature = ThresholdConfig(min_value=0, max_value=95, warning_pct=0.89, critical_pct=0.95)
        if self.utilization is None:
            # Utilization should stay high during stress
            self.utilization = ThresholdConfig(min_value=80, max_value=100)
        if self.frequency is None:
            # Frequency should not throttle below 50% of base
            self.frequency = ThresholdConfig(min_value=1000, max_value=5000)  # MHz


class CPUStressTest(StressTestBase):
    """CPU stress test using stress-ng or Python fallback.

    Monitors:
    - CPU temperature (if available via sensors)
    - CPU utilization
    - CPU frequency (to detect thermal throttling)
    - System load average
    """

    def __init__(
        self,
        duration_seconds: int = 300,
        sample_interval_seconds: int = 5,
        threads: Optional[int] = None,
        thresholds: Optional[CPUThresholds] = None
    ):
        thresholds = thresholds or CPUThresholds()
        super().__init__(
            duration_seconds=duration_seconds,
            sample_interval_seconds=sample_interval_seconds,
            thresholds={
                "temperature": thresholds.temperature,
                "utilization": thresholds.utilization,
                "frequency": thresholds.frequency,
            }
        )
        self.threads = threads or os.cpu_count() or 4
        self._stress_process: Optional[subprocess.Popen] = None
        self._stop_cpu_burn = threading.Event()
        self._cpu_burn_threads: list[threading.Thread] = []

    @property
    def test_name(self) -> str:
        return "cpu_stress"

    def start_stress(self) -> bool:
        """Start CPU stress workload."""
        # Try stress-ng first (more reliable)
        try:
            cmd = [
                "stress-ng",
                "--cpu", str(self.threads),
                "--cpu-method", "all",
                "--timeout", "0",  # Run until killed
                "--quiet"
            ]
            self._stress_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(0.5)  # Let it start
            return self._stress_process.poll() is None
        except FileNotFoundError:
            pass

        # Fallback to Python CPU burn
        self._stop_cpu_burn.clear()
        self._cpu_burn_threads = []

        def cpu_burn():
            while not self._stop_cpu_burn.is_set():
                # Busy loop to consume CPU
                for _ in range(1000000):
                    _ = _ * _

        for _ in range(self.threads):
            t = threading.Thread(target=cpu_burn, daemon=True)
            t.start()
            self._cpu_burn_threads.append(t)

        return True

    def stop_stress(self) -> None:
        """Stop CPU stress workload."""
        if self._stress_process:
            try:
                self._stress_process.terminate()
                self._stress_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._stress_process.kill()
            self._stress_process = None

        self._stop_cpu_burn.set()
        for t in self._cpu_burn_threads:
            t.join(timeout=1)
        self._cpu_burn_threads = []

    def collect_metrics(self) -> Dict[str, float]:
        """Collect CPU metrics."""
        metrics = {}

        # CPU utilization (using psutil if available)
        try:
            import psutil
            metrics["utilization"] = psutil.cpu_percent(interval=1)
        except ImportError:
            metrics["utilization"] = 0.0

        # CPU temperature (from sensors)
        metrics["temperature"] = self._get_cpu_temperature()

        # CPU frequency
        metrics["frequency"] = self._get_cpu_frequency()

        # Load average
        try:
            load1, _, _ = os.getloadavg()
            metrics["load_average"] = load1
        except OSError:
            metrics["load_average"] = 0.0

        return metrics

    def _get_cpu_temperature(self) -> float:
        """Get CPU temperature from various sources."""
        # Try sensors command
        try:
            result = subprocess.run(
                ["sensors", "-u"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse sensors output for CPU temp
                for line in result.stdout.split("\n"):
                    if "temp" in line.lower() and "input" in line.lower():
                        try:
                            parts = line.split(":")
                            if len(parts) >= 2:
                                return float(parts[1].strip())
                        except (ValueError, IndexError):
                            continue
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try thermal zone
        try:
            for zone in range(10):
                path = f"/sys/class/thermal/thermal_zone{zone}/temp"
                if os.path.exists(path):
                    with open(path, "r") as f:
                        temp_millidegrees = int(f.read().strip())
                        return temp_millidegrees / 1000.0
        except (OSError, ValueError):
            pass

        return 0.0

    def _get_cpu_frequency(self) -> float:
        """Get current CPU frequency in MHz."""
        try:
            # Try cpuinfo
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "cpu MHz" in line:
                        try:
                            return float(line.split(":")[1].strip())
                        except (ValueError, IndexError):
                            continue
        except OSError:
            pass

        # Try cpufreq
        try:
            path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"
            if os.path.exists(path):
                with open(path, "r") as f:
                    khz = int(f.read().strip())
                    return khz / 1000.0
        except (OSError, ValueError):
            pass

        return 0.0
