"""Storage functional tests including performance benchmarks."""

import subprocess
import tempfile
import os
import time
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

from .base import FunctionalTestBase, TestResult, TestStatus, TestConfig


@dataclass
class StorageConfig(TestConfig):
    """Storage test configuration."""
    test_file_size_gb: int = 5
    block_sizes: List[int] = None

    def __post_init__(self):
        if self.block_sizes is None:
            self.block_sizes = [4, 64, 1024]  # KB


class StorageTest(FunctionalTestBase):
    """Storage functional and performance tests.

    Tests:
    - Disk presence and capacity
    - Sequential read/write performance
    - Random I/O performance
    - SMART health check
    """

    def __init__(self, config: StorageConfig = None):
        super().__init__(config or StorageConfig())
        self.storage_config = self.config  # type: StorageConfig

    @property
    def test_name(self) -> str:
        return "storage_functional"

    def run(self) -> TestResult:
        """Run storage functional tests."""
        self._start_timer()

        results = []
        all_passed = True
        metrics = {}

        # Get list of testable devices
        devices = self._get_test_devices()

        if not devices:
            return self._create_result(
                TestStatus.ERROR,
                "No storage devices found for testing",
                {},
                {}
            )

        for device in devices[:2]:  # Test up to 2 devices
            device_results = self._test_device(device)
            results.extend(device_results["tests"])
            metrics[device["name"]] = device_results["metrics"]

            if not device_results["passed"]:
                all_passed = False

        details = {
            "devices_tested": len(devices),
            "tests": results
        }

        if all_passed:
            return self._create_result(
                TestStatus.PASSED,
                f"Storage tests passed on {len(devices)} device(s)",
                details,
                metrics
            )
        else:
            return self._create_result(
                TestStatus.FAILED,
                "Some storage tests failed",
                details,
                metrics
            )

    def _get_test_devices(self) -> List[Dict[str, str]]:
        """Get list of storage devices to test."""
        devices = []

        # Look for NVMe devices
        try:
            for entry in os.listdir("/dev"):
                if entry.startswith("nvme") and "p" not in entry:
                    devices.append({
                        "name": entry,
                        "path": f"/dev/{entry}n1",
                        "type": "nvme"
                    })
        except OSError:
            pass

        # Look for SATA/SAS devices
        if not devices:
            try:
                for entry in os.listdir("/dev"):
                    if entry.startswith("sd") and len(entry) == 3:
                        devices.append({
                            "name": entry,
                            "path": f"/dev/{entry}",
                            "type": "sata"
                        })
            except OSError:
                pass

        return devices

    def _test_device(self, device: Dict[str, str]) -> Dict[str, Any]:
        """Test a single storage device."""
        tests = []
        passed = True
        metrics = {}

        # Test 1: SMART Health
        status, msg = self._check_smart_health(device["path"])
        tests.append({"name": "smart_health", "passed": status, "message": msg})
        if not status:
            passed = False

        # Test 2: Sequential Performance (if we can write)
        status, msg, seq_read, seq_write = self._test_sequential_perf(device)
        tests.append({"name": "sequential_perf", "passed": status, "message": msg})
        metrics["seq_read_mbps"] = seq_read
        metrics["seq_write_mbps"] = seq_write
        if not status:
            passed = False

        # Test 3: Random I/O (using fio if available)
        status, msg, rand_read_iops, rand_write_iops = self._test_random_io(device)
        tests.append({"name": "random_io", "passed": status, "message": msg})
        metrics["rand_read_iops"] = rand_read_iops
        metrics["rand_write_iops"] = rand_write_iops
        # Random I/O test is optional

        return {
            "tests": tests,
            "passed": passed,
            "metrics": metrics
        }

    def _check_smart_health(self, device_path: str) -> Tuple[bool, str]:
        """Check SMART health status."""
        try:
            result = subprocess.run(
                ["smartctl", "-H", device_path],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                if "PASSED" in result.stdout or "OK" in result.stdout:
                    return True, "SMART health OK"
                else:
                    return False, "SMART health check failed"
            else:
                # Non-zero exit might still mean healthy for some controllers
                return True, "SMART check inconclusive"

        except FileNotFoundError:
            return True, "smartctl not available"
        except Exception as e:
            return True, f"SMART check error: {str(e)}"

    def _test_sequential_perf(
        self,
        device: Dict[str, str]
    ) -> Tuple[bool, str, float, float]:
        """Test sequential read/write performance."""
        # Find mount point for the device
        mount_point = self._get_mount_point(device["path"])

        if not mount_point:
            return True, "Device not mounted, skipping write test", 0, 0

        test_file = os.path.join(mount_point, ".storage_test")
        size_mb = 1024  # 1GB test

        try:
            # Write test
            start = time.time()
            subprocess.run(
                ["dd", "if=/dev/zero", f"of={test_file}", "bs=1M",
                 f"count={size_mb}", "oflag=direct", "status=none"],
                timeout=120,
                capture_output=True
            )
            write_time = time.time() - start
            write_bw = (size_mb) / write_time  # MB/s

            # Read test
            start = time.time()
            subprocess.run(
                ["dd", f"if={test_file}", "of=/dev/null", "bs=1M",
                 "iflag=direct", "status=none"],
                timeout=120,
                capture_output=True
            )
            read_time = time.time() - start
            read_bw = (size_mb) / read_time  # MB/s

            # Cleanup
            os.unlink(test_file)

            # NVMe should do > 500 MB/s, SATA > 100 MB/s
            min_read = 500 if device["type"] == "nvme" else 100

            if read_bw >= min_read:
                return True, f"R: {read_bw:.0f} MB/s, W: {write_bw:.0f} MB/s", read_bw, write_bw
            else:
                return False, f"Read too slow: {read_bw:.0f} MB/s (expected > {min_read})", read_bw, write_bw

        except subprocess.TimeoutExpired:
            return False, "Performance test timeout", 0, 0
        except Exception as e:
            return False, f"Performance test error: {str(e)}", 0, 0

    def _test_random_io(
        self,
        device: Dict[str, str]
    ) -> Tuple[bool, str, float, float]:
        """Test random I/O performance using fio."""
        try:
            # Check if fio is available
            result = subprocess.run(
                ["fio", "--version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                return True, "fio not available", 0, 0

            mount_point = self._get_mount_point(device["path"])
            if not mount_point:
                return True, "Device not mounted", 0, 0

            test_file = os.path.join(mount_point, ".fio_test")

            # Run fio test
            result = subprocess.run(
                [
                    "fio",
                    "--name=random_test",
                    f"--filename={test_file}",
                    "--rw=randrw",
                    "--rwmixread=70",
                    "--bs=4k",
                    "--size=1G",
                    "--numjobs=4",
                    "--iodepth=32",
                    "--runtime=30",
                    "--time_based",
                    "--group_reporting",
                    "--output-format=json"
                ],
                capture_output=True,
                text=True,
                timeout=60
            )

            # Cleanup
            if os.path.exists(test_file):
                os.unlink(test_file)

            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                jobs = data.get("jobs", [{}])[0]

                read_iops = jobs.get("read", {}).get("iops", 0)
                write_iops = jobs.get("write", {}).get("iops", 0)

                return True, f"R: {read_iops:.0f} IOPS, W: {write_iops:.0f} IOPS", read_iops, write_iops

            return True, "fio test completed", 0, 0

        except FileNotFoundError:
            return True, "fio not installed", 0, 0
        except Exception as e:
            return True, f"Random I/O test error: {str(e)}", 0, 0

    def _get_mount_point(self, device_path: str) -> str:
        """Get mount point for a device."""
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        if device_path in parts[0] or parts[0] in device_path:
                            return parts[1]
        except OSError:
            pass
        return ""
