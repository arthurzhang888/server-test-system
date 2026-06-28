"""NVMe SSD stress test implementation using fio or fallback methods."""

import subprocess
import os
import tempfile
import threading
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .base import StressTestBase, ThresholdConfig


@dataclass
class NVMeThresholds:
    """Predefined threshold configurations for NVMe stress test."""
    temperature: ThresholdConfig = None
    health_percent: ThresholdConfig = None
    spare_percent: ThresholdConfig = None
    media_errors: ThresholdConfig = None
    power_on_hours: ThresholdConfig = None

    def __post_init__(self):
        if self.temperature is None:
            # NVMe temp: warning at 70°C, critical > 85°C
            self.temperature = ThresholdConfig(min_value=0, max_value=85, warning_pct=0.82, critical_pct=0.95)
        if self.health_percent is None:
            # Health should not degrade during test
            self.health_percent = ThresholdConfig(min_value=90, max_value=100)
        if self.spare_percent is None:
            # Spare blocks should remain high
            self.spare_percent = ThresholdConfig(min_value=10, max_value=100)
        if self.media_errors is None:
            # No media errors allowed
            self.media_errors = ThresholdConfig(min_value=0, max_value=0)
        if self.power_on_hours is None:
            # Not a critical metric, just track
            self.power_on_hours = ThresholdConfig(min_value=0, max_value=100000)


class NVMeStressTest(StressTestBase):
    """NVMe SSD stress test using fio or dd fallback.

    Performs sustained read/write I/O to stress the drive while monitoring:
    - Temperature
    - SMART health metrics
    - Media errors
    - Wear leveling

    Warning: This test writes to the drive. Use with caution on production systems.
    """

    def __init__(
        self,
        duration_seconds: int = 300,
        sample_interval_seconds: int = 5,
        devices: Optional[List[str]] = None,
        test_file_size_gb: int = 10,
        write_ratio: float = 0.3,  # 30% writes, 70% reads (safer)
        thresholds: Optional[NVMeThresholds] = None
    ):
        thresholds = thresholds or NVMeThresholds()
        super().__init__(
            duration_seconds=duration_seconds,
            sample_interval_seconds=sample_interval_seconds,
            thresholds={
                "temperature": thresholds.temperature,
                "health_percent": thresholds.health_percent,
                "spare_percent": thresholds.spare_percent,
                "media_errors": thresholds.media_errors,
            }
        )
        self.devices = devices or []
        self.test_file_size_gb = test_file_size_gb
        self.write_ratio = write_ratio
        self._stress_threads: List[threading.Thread] = []
        self._stop_stress = threading.Event()
        self._temp_dir: Optional[str] = None

    @property
    def test_name(self) -> str:
        return "nvme_stress"

    def start_stress(self) -> bool:
        """Start NVMe stress workload."""
        if not self.devices:
            # Auto-detect NVMe devices
            self.devices = self._detect_nvme_devices()

        if not self.devices:
            return False

        self._stop_stress.clear()
        self._stress_threads = []

        for device in self.devices:
            # Create stress thread for each device
            t = threading.Thread(
                target=self._stress_device,
                args=(device,),
                daemon=True
            )
            t.start()
            self._stress_threads.append(t)

        return len(self._stress_threads) > 0

    def stop_stress(self) -> None:
        """Stop NVMe stress workload."""
        self._stop_stress.set()

        for t in self._stress_threads:
            t.join(timeout=5)
        self._stress_threads = []

        # Cleanup temp files
        if self._temp_dir and os.path.exists(self._temp_dir):
            import shutil
            try:
                shutil.rmtree(self._temp_dir)
            except OSError:
                pass
            self._temp_dir = None

    def collect_metrics(self) -> Dict[str, float]:
        """Collect NVMe metrics."""
        metrics = {}

        for device in self.devices:
            device_metrics = self._get_smart_metrics(device)

            # Aggregate (worst case across devices)
            for key, value in device_metrics.items():
                if key in metrics:
                    if key in ["temperature", "media_errors"]:
                        metrics[key] = max(metrics[key], value)
                    else:
                        metrics[key] = min(metrics[key], value)  # For health metrics, take min
                else:
                    metrics[key] = value

        return metrics

    def _detect_nvme_devices(self) -> List[str]:
        """Auto-detect NVMe devices."""
        devices = []

        try:
            # List NVMe devices
            result = subprocess.run(
                ["nvme", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n")[2:]:  # Skip header
                    parts = line.split()
                    if parts and parts[0].startswith("/dev/nvme"):
                        devices.append(parts[0])

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: check /dev for nvme devices
        if not devices:
            try:
                for entry in os.listdir("/dev"):
                    if entry.startswith("nvme") and "p" not in entry:  # nvme0, not nvme0n1p1
                        device_path = f"/dev/{entry}n1"  # namespace 1
                        if os.path.exists(device_path):
                            devices.append(device_path)
            except OSError:
                pass

        return devices

    def _stress_device(self, device: str) -> None:
        """Run stress workload on a single device."""
        # Try fio first
        if self._try_fio_stress(device):
            return

        # Fallback to simple dd-based stress
        self._dd_stress(device)

    def _try_fio_stress(self, device: str) -> bool:
        """Try to use fio for stress testing."""
        try:
            # Create a temp file for fio to work on (safer than raw device)
            mount_point = self._get_mount_point(device)
            if not mount_point:
                return False

            test_file = os.path.join(mount_point, ".stress_test_file")

            # fio command for mixed read/write
            cmd = [
                "fio",
                "--name=nvme_stress",
                f"--filename={test_file}",
                f"--size={self.test_file_size_gb}G",
                "--direct=1",
                "--ioengine=libaio",
                f"--rw=randrw",
                f"--rwmixread={int((1 - self.write_ratio) * 100)}",
                "--bs=4k",
                "--numjobs=4",
                "--iodepth=32",
                "--runtime=86400",  # Run until stopped
                "--time_based",
                "--group_reporting"
            ]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Wait while checking stop signal
            while not self._stop_stress.is_set():
                if process.poll() is not None:
                    break
                time.sleep(1)

            process.terminate()
            process.wait(timeout=10)

            # Cleanup test file
            try:
                os.remove(test_file)
            except OSError:
                pass

            return True

        except FileNotFoundError:
            return False
        except Exception:
            return False

    def _dd_stress(self, device: str) -> None:
        """Fallback stress using dd reads (safer, no writes)."""
        # For safety, only do reads unless explicitly configured
        if self.write_ratio > 0:
            # Would need a file on the filesystem
            mount_point = self._get_mount_point(device)
            if mount_point:
                test_file = os.path.join(mount_point, ".dd_test_file")
                # Create test file if not exists
                if not os.path.exists(test_file):
                    self._create_test_file(test_file)

                while not self._stop_stress.is_set():
                    try:
                        # Read the file repeatedly
                        subprocess.run(
                            ["dd", "if=" + test_file, "of=/dev/null", "bs=1M", "status=none"],
                            timeout=10,
                            capture_output=True
                        )
                    except subprocess.TimeoutExpired:
                        pass
                    except Exception:
                        break
        else:
            # Read-only stress from raw device (safer)
            while not self._stop_stress.is_set():
                try:
                    subprocess.run(
                        ["dd", f"if={device}", "of=/dev/null", "bs=1M", "count=1000", "status=none"],
                        timeout=30,
                        capture_output=True
                    )
                except subprocess.TimeoutExpired:
                    pass
                except Exception:
                    break

    def _create_test_file(self, filepath: str) -> None:
        """Create a test file for dd stress."""
        try:
            subprocess.run(
                ["dd", "if=/dev/zero", f"of={filepath}", "bs=1M",
                 f"count={self.test_file_size_gb * 1024}", "status=none"],
                timeout=300,
                capture_output=True
            )
        except Exception:
            pass

    def _get_mount_point(self, device: str) -> Optional[str]:
        """Get mount point for a device."""
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        # Check if device matches
                        if device in parts[0] or parts[0] in device:
                            return parts[1]
        except OSError:
            pass
        return None

    def _get_smart_metrics(self, device: str) -> Dict[str, float]:
        """Get SMART metrics for NVMe device."""
        metrics = {}

        # Try nvme-cli first
        try:
            result = subprocess.run(
                ["nvme", "smart-log", device],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    line = line.strip()

                    if "temperature" in line.lower() and ":" in line:
                        try:
                            # Temperature in Kelvin, convert to Celsius
                            val = int(line.split(":")[1].strip().split()[0])
                            metrics["temperature"] = val - 273 if val > 273 else val
                        except (ValueError, IndexError):
                            pass

                    elif "percentage_used" in line.lower():
                        try:
                            val = int(line.split(":")[1].strip().replace("%", ""))
                            metrics["health_percent"] = 100 - val
                        except (ValueError, IndexError):
                            pass

                    elif "available_spare" in line.lower():
                        try:
                            val = int(line.split(":")[1].strip().replace("%", ""))
                            metrics["spare_percent"] = val
                        except (ValueError, IndexError):
                            pass

                    elif "media_errors" in line.lower():
                        try:
                            val = int(line.split(":")[1].strip())
                            metrics["media_errors"] = val
                        except (ValueError, IndexError):
                            pass

                    elif "power_on_hours" in line.lower():
                        try:
                            val = int(line.split(":")[1].strip())
                            metrics["power_on_hours"] = val
                        except (ValueError, IndexError):
                            pass

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback to smartctl
        if not metrics:
            try:
                result = subprocess.run(
                    ["smartctl", "-a", device],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if "Temperature:" in line:
                            try:
                                parts = line.split()
                                for i, part in enumerate(parts):
                                    if part.isdigit() and i > 0:
                                        metrics["temperature"] = float(part)
                                        break
                            except (ValueError, IndexError):
                                pass

            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        return metrics
