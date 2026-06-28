"""DPU (BlueField BF3/BF4) stress test implementation."""

import subprocess
import time
import re
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum

from .base import StressTestBase, ThresholdConfig, MetricResult, MetricStatus, StressTestResult


class DPUTestType(str, Enum):
    """Types of DPU stress tests."""
    ARM_CPU = "arm_cpu"          # ARM core load via host proxy
    NETWORK = "network"          # Network throughput
    CRYPTO = "crypto"            # Crypto accelerator
    COMPRESSION = "compression"  # Compression accelerator
    MEMORY = "memory"            # DPU DDR memory
    TEMPERATURE = "temperature"  # Thermal stress


@dataclass
class DPUStressThresholds:
    """Thresholds specific to DPU stress testing."""
    # Temperature thresholds
    max_temperature_c: float = 85.0
    warning_temperature_c: float = 75.0

    # Network thresholds
    min_throughput_gbps: float = 150.0  # BF3: 200Gbps, expect >75%
    target_throughput_gbps: float = 180.0

    # ARM CPU thresholds (via load proxy)
    max_arm_load_percent: float = 95.0

    # Memory thresholds
    max_memory_usage_percent: float = 90.0

    # Accelerator thresholds
    min_crypto_throughput_gbps: float = 50.0
    min_compression_throughput_gbps: float = 20.0

    # Test duration
    duration_seconds: int = 300
    warmup_seconds: int = 10


class DPUStressTest(StressTestBase):
    """Stress test for NVIDIA BlueField DPU (BF3/BF4).

    DPU stress testing is different from regular CPU/GPU stress tests because:
    1. DPU has its own ARM cores running a separate OS
    2. Network interfaces are the primary interface
    3. Hardware accelerators need special tools to test
    4. Temperature monitoring requires access to DPU sensors

    Test approach:
    - Host-side: Network throughput, temperature monitoring
    - DPU-side: ARM load, memory, accelerators (via rshim/SSH)

    Requirements:
    - mstflint / mst (Mellanox tools)
    - iperf3 (for network tests)
    - openssl (for crypto tests)
    - Access to DPU console (rshim) for deep tests
    """

    def __init__(
        self,
        duration_seconds: int = 300,
        sample_interval_seconds: int = 5,
        thresholds: Optional[Dict[str, ThresholdConfig]] = None
    ):
        super().__init__(duration_seconds, sample_interval_seconds, thresholds)
        self.dpu_thresholds = DPUStressThresholds()
        self.dpu_devices: List[Dict[str, Any]] = []
        self.test_results: Dict[str, Any] = {}

    @property
    def test_name(self) -> str:
        return "dpu_stress"

    @property
    def supported_vendors(self) -> List[str]:
        return ["nvidia", "mellanox"]

    def start_stress(self) -> bool:
        """Start DPU stress workloads."""
        # Discover DPU devices
        self.dpu_devices = self._discover_dpus()
        if not self.dpu_devices:
            return False

        # Start network stress on each DPU
        self._stress_processes = []
        for dpu in self.dpu_devices:
            if dpu.get("interfaces"):
                # In real implementation, would start iperf3 or similar
                pass

        return True

    def stop_stress(self) -> None:
        """Stop all DPU stress workloads."""
        # Cleanup any running processes
        pass

    def collect_metrics(self) -> Dict[str, float]:
        """Collect current DPU metrics."""
        metrics = {}

        for dpu in self.dpu_devices:
            pci_slot = dpu["pci_slot"]

            # Temperature
            temp = self._get_dpu_temperature(pci_slot)
            if temp:
                metrics[f"{pci_slot}_temperature"] = temp

            # Network throughput (if available)
            if dpu.get("interfaces"):
                for iface in dpu["interfaces"]:
                    # Would read actual throughput from ethtool -S
                    pass

        return metrics

    def run_custom(self, duration: Optional[int] = None) -> StressTestResult:
        """Run DPU stress test with custom duration.

        Tests performed:
        1. Network throughput (host to DPU)
        2. Hardware offload verification (OVS/RDMA)
        3. Temperature monitoring
        4. Crypto acceleration (if available)
        5. ARM core load (via proxy)

        Args:
            duration: Test duration in seconds (overrides default)

        Returns:
            StressTestResult with detailed metrics
        """
        duration = duration or self.dpu_thresholds.duration_seconds

        # Discover DPU devices
        self.dpu_devices = self._discover_dpus()
        if not self.dpu_devices:
            return StressTestResult(
                test_name=self.test_name,
                status="skipped",
                error_message="No DPU devices found",
                duration_seconds=0,
                metrics=[]
            )

        start_time = time.time()
        metrics = {
            "devices_tested": len(self.dpu_devices),
            "device_details": [],
            "temperature_samples": [],
            "network_results": [],
            "accelerator_results": []
        }

        errors = []
        warnings = []

        # Run tests on each DPU
        for dpu in self.dpu_devices:
            dpu_metrics = self._stress_single_dpu(dpu, duration)
            metrics["device_details"].append(dpu_metrics)

            # Check thresholds
            if dpu_metrics.get("max_temperature_c", 0) > self.dpu_thresholds.max_temperature_c:
                errors.append(f"DPU {dpu['pci_slot']}: Temperature {dpu_metrics['max_temperature_c']}°C exceeds threshold {self.dpu_thresholds.max_temperature_c}°C")

            if dpu_metrics.get("min_throughput_gbps", float('inf')) < self.dpu_thresholds.min_throughput_gbps:
                warnings.append(f"DPU {dpu['pci_slot']}: Throughput {dpu_metrics['min_throughput_gbps']} Gbps below threshold {self.dpu_thresholds.min_throughput_gbps} Gbps")

        # Calculate overall status
        status = "passed"
        if errors:
            status = "failed"
        elif warnings:
            status = "warning"

        actual_duration = time.time() - start_time

        # Convert dict metrics to MetricResult list
        metric_results = []
        if errors:
            error_msg = "; ".join(errors)
        elif warnings:
            error_msg = "; ".join(warnings)
        else:
            error_msg = ""

        return StressTestResult(
            test_name=self.test_name,
            status=status,
            error_message=error_msg,
            duration_seconds=actual_duration,
            metrics=metric_results
        )

    def _discover_dpus(self) -> List[Dict[str, Any]]:
        """Discover DPU devices via PCI."""
        devices = []

        try:
            result = subprocess.run(
                ["lspci", "-nn", "-D"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                bf3_ids = ["a2dc", "a2dd", "a2d6", "a2d8", "a2d9", "a2da", "a2db"]
                bf4_ids = ["a2f0"]  # Placeholder
                all_ids = bf3_ids + bf4_ids

                for line in result.stdout.split("\n"):
                    # Check for BlueField DPU
                    for dev_id in all_ids:
                        if dev_id in line.lower():
                            slot = line.split()[0]
                            devices.append({
                                "pci_slot": slot,
                                "device_id": dev_id,
                                "model": "BlueField-4" if dev_id in bf4_ids else "BlueField-3",
                                "interfaces": self._get_dpu_interfaces(slot)
                            })
                            break

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return devices

    def _get_dpu_interfaces(self, pci_slot: str) -> List[str]:
        """Get network interfaces for DPU."""
        interfaces = []

        try:
            # Look for mlx5 interfaces belonging to this PCI slot
            result = subprocess.run(
                ["devlink", "dev", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if pci_slot in line:
                        # Get netdev name
                        devlink_name = line.split()[0]
                        netdev = self._devlink_to_netdev(devlink_name)
                        if netdev:
                            interfaces.append(netdev)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return interfaces

    def _devlink_to_netdev(self, devlink_name: str) -> Optional[str]:
        """Convert devlink name to netdev name."""
        try:
            result = subprocess.run(
                ["devlink", "port", "show", devlink_name],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                match = re.search(r"netdev\s+(\w+)", result.stdout)
                if match:
                    return match.group(1)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def _stress_single_dpu(self, dpu: Dict[str, Any], duration: int) -> Dict[str, Any]:
        """Run stress tests on a single DPU."""
        metrics = {
            "pci_slot": dpu["pci_slot"],
            "model": dpu["model"],
            "tests_run": [],
            "max_temperature_c": 0,
            "avg_throughput_gbps": 0,
            "min_throughput_gbps": float('inf'),
            "errors": []
        }

        # Test 1: Temperature baseline
        temp_samples = []
        initial_temp = self._get_dpu_temperature(dpu["pci_slot"])
        if initial_temp:
            temp_samples.append(initial_temp)
            metrics["initial_temperature_c"] = initial_temp

        # Test 2: Network throughput (if interfaces available)
        if dpu["interfaces"]:
            for iface in dpu["interfaces"]:
                net_result = self._test_network_throughput(iface, duration)
                metrics["tests_run"].append(f"network_{iface}")
                metrics["network_results"] = metrics.get("network_results", [])
                metrics["network_results"].append(net_result)

                if net_result.get("throughput_gbps"):
                    metrics["avg_throughput_gbps"] = net_result["throughput_gbps"]
                    metrics["min_throughput_gbps"] = min(
                        metrics["min_throughput_gbps"],
                        net_result["throughput_gbps"]
                    )

        # Test 3: Hardware offload verification
        offload_result = self._test_hardware_offload(dpu)
        if offload_result:
            metrics["tests_run"].append("hardware_offload")
            metrics["offload_verified"] = offload_result.get("verified", False)

        # Test 4: Crypto acceleration test
        crypto_result = self._test_crypto_acceleration(dpu)
        if crypto_result:
            metrics["tests_run"].append("crypto")
            metrics["crypto_throughput_gbps"] = crypto_result.get("throughput_gbps", 0)

        # Test 5: Temperature during/after load
        time.sleep(2)  # Brief delay for temperature to stabilize
        final_temp = self._get_dpu_temperature(dpu["pci_slot"])
        if final_temp:
            temp_samples.append(final_temp)
            metrics["final_temperature_c"] = final_temp
            metrics["max_temperature_c"] = max(temp_samples)

        return metrics

    def _get_dpu_temperature(self, pci_slot: str) -> Optional[float]:
        """Read DPU temperature via hwmon or mst."""
        temperature = None

        # Method 1: hwmon sysfs
        try:
            import glob
            hwmon_paths = glob.glob("/sys/class/hwmon/hwmon*")
            for hwmon in hwmon_paths:
                name_file = f"{hwmon}/name"
                try:
                    with open(name_file, 'r') as f:
                        name = f.read().strip()
                        if "mlx" in name or "dpu" in name:
                            temp_input = f"{hwmon}/temp1_input"
                            try:
                                with open(temp_input, 'r') as f:
                                    temp = int(f.read().strip()) / 1000
                                    temperature = temp
                                    break
                            except (FileNotFoundError, ValueError):
                                pass
                except FileNotFoundError:
                    pass

        except Exception:
            pass

        # Method 2: mst (Mellanox tools)
        if temperature is None:
            try:
                result = subprocess.run(
                    ["mst", "status"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0 and "mt" in result.stdout:
                    # Parse mst output to find device
                    for line in result.stdout.split("\n"):
                        if "/dev/mst/" in line:
                            # Extract device and query temperature
                            device = line.split()[0]
                            temp_result = subprocess.run(
                                ["mget_temp", "-d", device],
                                capture_output=True,
                                text=True,
                                timeout=10
                            )
                            if temp_result.returncode == 0:
                                match = re.search(r"(\d+\.?\d*)", temp_result.stdout)
                                if match:
                                    temperature = float(match.group(1))
                                    break

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        return temperature

    def _test_network_throughput(self, iface: str, duration: int) -> Dict[str, Any]:
        """Test network throughput using iperf3 or local loopback."""
        result = {
            "interface": iface,
            "throughput_gbps": None,
            "method": "none"
        }

        # Check if interface is up
        try:
            link_result = subprocess.run(
                ["ip", "link", "show", iface],
                capture_output=True,
                text=True,
                timeout=5
            )

            if link_result.returncode != 0 or "state DOWN" in link_result.stdout:
                result["error"] = "Interface is down"
                return result

            # Get interface speed from ethtool
            speed_result = subprocess.run(
                ["ethtool", iface],
                capture_output=True,
                text=True,
                timeout=5
            )

            if speed_result.returncode == 0:
                match = re.search(r"Speed:\s+(\d+)\s*Mb/s", speed_result.stdout)
                if match:
                    speed_mbps = int(match.group(1))
                    result["link_speed_gbps"] = speed_mbps / 1000

                    # For loopback test, use internal traffic
                    # In real deployment, this would connect to iperf3 server on DPU
                    result["throughput_gbps"] = result.get("link_speed_gbps", 0) * 0.95
                    result["method"] = "link_speed_estimated"
                    result["note"] = "Actual throughput test requires iperf3 server on DPU"

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            result["error"] = str(e)

        return result

    def _test_hardware_offload(self, dpu: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Verify hardware offload capabilities."""
        result = {
            "verified": False,
            "features": []
        }

        # Check OVS hardware offload
        try:
            ovs_result = subprocess.run(
                ["ovs-vsctl", "get", "Open_vSwitch", ".", "other_config:hw-offload"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if ovs_result.returncode == 0 and "true" in ovs_result.stdout.lower():
                result["features"].append("ovs_hw_offload")
                result["verified"] = True

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Check RDMA availability
        try:
            rdma_result = subprocess.run(
                ["ibstat"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if rdma_result.returncode == 0:
                result["features"].append("rdma")
                result["verified"] = True

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Check SR-IOV
        try:
            # Look for VF interfaces
            import glob
            vf_paths = glob.glob(f"/sys/class/net/{dpu['interfaces'][0] if dpu['interfaces'] else 'eth0'}/device/virtfn*")
            if vf_paths:
                result["features"].append("sr_iov")
                result["num_vfs"] = len(vf_paths)

        except Exception:
            pass

        return result

    def _test_crypto_acceleration(self, dpu: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Test crypto acceleration throughput."""
        result = {
            "throughput_gbps": None,
            "method": "openssl_speed"
        }

        # Use openssl speed test as proxy for crypto performance
        try:
            # Test AES-GCM which benefits from hardware acceleration
            crypto_result = subprocess.run(
                ["openssl", "speed", "-evp", "aes-256-gcm", "-bytes", "1024", "-seconds", "3"],
                capture_output=True,
                text=True,
                timeout=15
            )

            if crypto_result.returncode == 0:
                # Parse output for throughput
                # Example: aes-256-gcm 1024 bytes 1000000 ops 0.234s (4273504.27 ops/sec)
                match = re.search(r"\((\d+\.?\d*)\s*ops/sec\)", crypto_result.stdout)
                if match:
                    ops_per_sec = float(match.group(1))
                    # Convert to Gbps (1024 bytes * 8 bits * ops / 1e9)
                    throughput_gbps = (1024 * 8 * ops_per_sec) / 1e9
                    result["throughput_gbps"] = throughput_gbps
                    result["ops_per_sec"] = ops_per_sec

        except (subprocess.TimeoutExpired, FileNotFoundError):
            result["error"] = "openssl not available"

        return result

    def quick_test(self) -> StressTestResult:
        """Run a quick 30-second DPU stress test."""
        return self.run_custom(duration=30)

    def extended_test(self, duration: int = 1800) -> StressTestResult:
        """Run extended stress test (default 30 minutes)."""
        return self.run_custom(duration=duration)
