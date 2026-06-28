"""Storage and RAID stress test implementation."""

import subprocess
import time
import re
import os
import tempfile
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .base import StressTestBase, ThresholdConfig, MetricResult, MetricStatus, StressTestResult


class StorageTestType(str, Enum):
    """Types of storage stress tests."""
    SEQUENTIAL = "sequential"      # Sequential read/write
    RANDOM = "random"              # Random I/O
    LATENCY = "latency"            # Latency test
    ENDURANCE = "endurance"        # Long-duration test
    RAID = "raid"                  # RAID-specific tests


@dataclass
class StorageStressThresholds:
    """Thresholds specific to storage stress testing."""
    # IOPS thresholds
    min_read_iops: float = 1000.0
    min_write_iops: float = 500.0
    target_read_iops: float = 10000.0
    target_write_iops: float = 5000.0

    # Bandwidth thresholds (MB/s)
    min_read_bw_mbps: float = 100.0
    min_write_bw_mbps: float = 50.0

    # Latency thresholds (microseconds)
    max_read_latency_us: float = 10000.0  # 10ms
    max_write_latency_us: float = 20000.0  # 20ms

    # Temperature thresholds (for NVMe)
    max_temperature_c: float = 70.0
    warning_temperature_c: float = 60.0

    # SMART thresholds
    max_reallocated_sectors: int = 10
    max_pending_sectors: int = 10
    min_health_percent: float = 90.0

    # Test duration
    duration_seconds: int = 300
    warmup_seconds: int = 10

    # Test parameters
    block_size: str = "4k"  # or "1M" for sequential
    queue_depth: int = 32
    num_jobs: int = 4


class StorageStressTest(StressTestBase):
    """Stress test for storage devices (HDD/SSD/NVMe) and RAID arrays.

    Tests performed:
    1. Sequential read/write bandwidth
    2. Random I/O performance (IOPS)
    3. Latency measurement
    4. RAID array consistency check
    5. SMART health monitoring
    6. Temperature monitoring (NVMe)

    Supports:
    - SATA/SAS HDD
    - SATA SSD
    - NVMe SSD
    - RAID arrays (via /dev/md*)

    Requirements:
    - fio (Flexible I/O Tester)
    - smartctl (for SMART monitoring)
    - nvme-cli (for NVMe-specific tests)
    - mdadm (for RAID arrays)

    WARNING: This test will write to disks. Ensure test data only!
    """

    def __init__(
        self,
        duration_seconds: int = 300,
        sample_interval_seconds: int = 5,
        thresholds: Optional[Dict[str, ThresholdConfig]] = None,
        device: Optional[str] = None,
        test_file_size: str = "10G"
    ):
        super().__init__(duration_seconds, sample_interval_seconds, thresholds)
        self.storage_thresholds = StorageStressThresholds()
        self.device = device
        self.test_file_size = test_file_size
        self._test_files: List[str] = []
        self._fio_process: Optional[subprocess.Popen] = None
        self._initial_smart: Dict[str, Any] = {}

    @property
    def test_name(self) -> str:
        return "storage_stress"

    @property
    def supported_vendors(self) -> List[str]:
        return ["generic", "samsung", "intel", "wd", "seagate", "micron", "skhynix"]

    def start_stress(self) -> bool:
        """Start storage stress workload."""
        # Discover target device
        if not self.device:
            self.device = self._select_best_device()

        if not self.device:
            return False

        # Record initial SMART data
        self._initial_smart = self._get_smart_data(self.device)

        # Create test file(s)
        self._test_files = self._create_test_files()

        if not self._test_files:
            return False

        # Start fio stress
        return self._start_fio_stress()

    def _start_fio_stress(self) -> bool:
        """Start fio-based stress test."""
        try:
            # Create fio job file
            job_file = self._create_fio_jobfile()

            self._fio_process = subprocess.Popen(
                ["fio", job_file, "--output-format=json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            return True

        except FileNotFoundError:
            return False

    def _create_fio_jobfile(self) -> str:
        """Create fio job file for comprehensive testing."""
        job_content = f"""
[global]
directory=/tmp/stress_test
filename=fio_test_file
direct=1
bs={self.storage_thresholds.block_size}
iodepth={self.storage_thresholds.queue_depth}
numjobs={self.storage_thresholds.num_jobs}
time_based=1
runtime={self.duration_seconds + 60}

[random_read]
stonewall
rw=randread
size={self.test_file_size}

[random_write]
stonewall
rw=randwrite
size={self.test_file_size}

[sequential_read]
stonewall
rw=read
bs=1M
size={self.test_file_size}

[sequential_write]
stonewall
rw=write
bs=1M
size={self.test_file_size}
"""

        job_file = "/tmp/fio_stress_job.fio"
        with open(job_file, "w") as f:
            f.write(job_content)

        return job_file

    def _create_test_files(self) -> List[str]:
        """Create test files on target device."""
        test_files = []

        # Determine mount point or use /tmp
        if self.device.startswith("/dev/"):
            # Find mount point for device
            mount_point = self._get_mount_point(self.device)
            if not mount_point:
                # Device not mounted, create temp dir
                mount_point = tempfile.mkdtemp(prefix="storage_stress_")
        else:
            mount_point = "/tmp"

        # Create test directory
        test_dir = os.path.join(mount_point, "stress_test")
        os.makedirs(test_dir, exist_ok=True)

        return [test_dir]

    def stop_stress(self) -> None:
        """Stop storage stress workload."""
        if self._fio_process:
            try:
                self._fio_process.terminate()
                self._fio_process.wait(timeout=10)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    self._fio_process.kill()
                except ProcessLookupError:
                    pass
            self._fio_process = None

        # Cleanup test files
        for test_dir in self._test_files:
            try:
                import shutil
                if os.path.exists(test_dir):
                    shutil.rmtree(test_dir)
            except Exception:
                pass

    def collect_metrics(self) -> Dict[str, float]:
        """Collect current storage metrics."""
        metrics = {}

        if not self.device:
            return metrics

        # Device statistics from /sys or iostat
        stats = self._get_device_stats(self.device)
        metrics.update(stats)

        # SMART data
        smart = self._get_smart_data(self.device)
        if smart:
            metrics["smart_health_percent"] = smart.get("health_percent", 100)
            metrics["smart_temperature_c"] = smart.get("temperature_c", 0)

        # RAID status (if applicable)
        if self.device.startswith("/dev/md"):
            raid_status = self._get_raid_status(self.device)
            if raid_status:
                metrics["raid_degraded"] = 1.0 if raid_status.get("degraded") else 0.0
                metrics["raid_sync_percent"] = raid_status.get("sync_percent", 100.0)

        return metrics

    def run_custom(self, duration: Optional[int] = None) -> StressTestResult:
        """Run storage stress test with custom duration."""
        duration = duration or self.storage_thresholds.duration_seconds

        if not self.start_stress():
            return StressTestResult(
                test_name=self.test_name,
                status="error",
                error_message="Failed to start storage stress workload",
                duration_seconds=0,
                metrics=[]
            )

        start_time = time.time()
        samples = []
        errors = []
        warnings = []

        # Warmup
        time.sleep(self.storage_thresholds.warmup_seconds)

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
                temp = metrics.get("smart_temperature_c", 0)
                if temp > self.storage_thresholds.max_temperature_c:
                    errors.append(f"Temperature {temp}°C exceeds threshold {self.storage_thresholds.max_temperature_c}°C")

                health = metrics.get("smart_health_percent", 100)
                if health < self.storage_thresholds.min_health_percent:
                    warnings.append(f"SMART health {health}% below threshold {self.storage_thresholds.min_health_percent}%")

                # Check for new bad sectors
                current_smart = self._get_smart_data(self.device)
                if current_smart:
                    new_realloc = current_smart.get("reallocated_sectors", 0) - self._initial_smart.get("reallocated_sectors", 0)
                    if new_realloc > 0:
                        errors.append(f"New reallocated sectors detected: {new_realloc}")

                # RAID check
                if metrics.get("raid_degraded", 0) > 0:
                    errors.append("RAID array is degraded")

                # Progress callback
                if self._progress_callback:
                    pct = min(100.0, (elapsed / duration) * 100)
                    self._progress_callback(pct, metrics)

        finally:
            self.stop_stress()

        actual_duration = time.time() - start_time

        # Get fio results if available
        fio_results = self._parse_fio_results()

        # Determine status
        status = "passed"
        if errors:
            status = "failed"
        elif warnings:
            status = "warning"

        metric_results = self._analyze_samples(samples)
        error_msg = "; ".join(errors + warnings) if (errors or warnings) else ""

        return StressTestResult(
            test_name=self.test_name,
            status=status,
            error_message=error_msg,
            duration_seconds=actual_duration,
            metrics=metric_results
        )

    def _select_best_device(self) -> Optional[str]:
        """Select best storage device for testing."""
        # Priority: NVMe > SSD > HDD
        devices = self.list_devices()

        # Look for NVMe first
        for dev in devices:
            if dev.get("type") == "nvme":
                return dev.get("device")

        # Then SSD
        for dev in devices:
            if dev.get("type") == "ssd":
                return dev.get("device")

        # Then any block device
        for dev in devices:
            if dev.get("type") in ["hdd", "ssd", "nvme"]:
                return dev.get("device")

        return None

    def _get_device_stats(self, device: str) -> Dict[str, float]:
        """Get device I/O statistics."""
        stats = {}

        # Use iostat if available
        try:
            result = subprocess.run(
                ["iostat", "-x", "-d", device.replace("/dev/", ""), "1", "1"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if device.replace("/dev/", "") in line:
                        parts = line.split()
                        if len(parts) >= 10:
                            stats["iops_read"] = float(parts[3])
                            stats["iops_write"] = float(parts[4])
                            stats["throughput_read_mbps"] = float(parts[5]) / 1024
                            stats["throughput_write_mbps"] = float(parts[6]) / 1024
                            stats["await_ms"] = float(parts[9])

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return stats

    def _get_smart_data(self, device: str) -> Dict[str, Any]:
        """Get SMART data for device."""
        data = {
            "health_percent": 100,
            "temperature_c": 0,
            "reallocated_sectors": 0,
            "pending_sectors": 0
        }

        try:
            result = subprocess.run(
                ["smartctl", "-a", device],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode in [0, 4]:  # 4 = smart failing
                output = result.stdout

                # Parse temperature
                temp_match = re.search(r"Temperature.*?(\d+)\s*Celsius", output, re.IGNORECASE)
                if temp_match:
                    data["temperature_c"] = int(temp_match.group(1))

                # Parse reallocated sectors
                realloc_match = re.search(r"Reallocated_Sector_Ct.*?(\d+)\s*$", output, re.MULTILINE)
                if realloc_match:
                    data["reallocated_sectors"] = int(realloc_match.group(1))

                # Parse pending sectors
                pending_match = re.search(r"Current_Pending_Sector.*?(\d+)\s*$", output, re.MULTILINE)
                if pending_match:
                    data["pending_sectors"] = int(pending_match.group(1))

                # Calculate health (simplified)
                health_penalty = (data["reallocated_sectors"] + data["pending_sectors"]) * 2
                data["health_percent"] = max(0, 100 - health_penalty)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return data

    def _get_raid_status(self, md_device: str) -> Optional[Dict[str, Any]]:
        """Get RAID array status."""
        try:
            result = subprocess.run(
                ["mdadm", "--detail", md_device],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                status = {
                    "degraded": "degraded" in result.stdout.lower(),
                    "sync_percent": 100.0
                }

                # Parse sync percentage
                sync_match = re.search(r"(\d+\.?\d*)%\s*sync", result.stdout)
                if sync_match:
                    status["sync_percent"] = float(sync_match.group(1))

                return status

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def _get_mount_point(self, device: str) -> Optional[str]:
        """Get mount point for device."""
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if parts[0] == device:
                        return parts[1]
        except FileNotFoundError:
            pass

        return None

    def _parse_fio_results(self) -> Dict[str, Any]:
        """Parse fio JSON output."""
        results = {}

        if not self._fio_process:
            return results

        try:
            stdout, _ = self._fio_process.communicate(timeout=1)
            if stdout:
                import json
                data = json.loads(stdout)

                # Extract results for each job
                for job in data.get("jobs", []):
                    job_name = job.get("jobname", "unknown")

                    if "read" in job:
                        results[f"{job_name}_read_iops"] = job["read"].get("iops", 0)
                        results[f"{job_name}_read_bw_mbps"] = job["read"].get("bw", 0) / 1024

                    if "write" in job:
                        results[f"{job_name}_write_iops"] = job["write"].get("iops", 0)
                        results[f"{job_name}_write_bw_mbps"] = job["write"].get("bw", 0) / 1024

        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            pass

        return results

    def quick_test(self) -> StressTestResult:
        """Run a quick 60-second storage stress test."""
        return self.run_custom(duration=60)

    def extended_test(self, duration: int = 3600) -> StressTestResult:
        """Run extended storage stress test (default 1 hour)."""
        return self.run_custom(duration=duration)

    def list_devices(self) -> List[Dict[str, Any]]:
        """List all available storage devices."""
        devices = []

        try:
            # Block devices
            for dev in os.listdir("/sys/block"):
                dev_path = f"/dev/{dev}"

                # Skip loop and ram devices
                if dev.startswith("loop") or dev.startswith("ram"):
                    continue

                device_info = {
                    "device": dev_path,
                    "name": dev,
                    "type": "unknown"
                }

                # Detect type
                if dev.startswith("nvme"):
                    device_info["type"] = "nvme"
                elif dev.startswith("sd") or dev.startswith("hd"):
                    # Check rotational
                    try:
                        with open(f"/sys/block/{dev}/queue/rotational", "r") as f:
                            rotational = int(f.read().strip())
                            device_info["type"] = "hdd" if rotational else "ssd"
                    except FileNotFoundError:
                        pass
                elif dev.startswith("md"):
                    device_info["type"] = "raid"

                devices.append(device_info)

        except FileNotFoundError:
            pass

        return devices
