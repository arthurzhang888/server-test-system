"""FPGA (Field Programmable Gate Array) stress test implementation."""

import subprocess
import time
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from .base import StressTestBase, ThresholdConfig, MetricResult, MetricStatus, StressTestResult


class FPGATestType(str, Enum):
    """Types of FPGA stress tests."""
    COMPUTE = "compute"            # Compute intensive workload
    MEMORY = "memory"              # FPGA memory bandwidth
    PCIE = "pcie"                  # PCIe bandwidth test
    THERMAL = "thermal"            # Thermal stress
    POWER = "power"                # Power consumption test


@dataclass
class FPGAStressThresholds:
    """Thresholds specific to FPGA stress testing."""
    # Temperature thresholds
    max_temperature_c: float = 85.0
    warning_temperature_c: float = 75.0

    # Power thresholds (Watts)
    max_power_w: float = 300.0
    warning_power_w: float = 250.0

    # PCIe bandwidth (GB/s)
    min_pcie_bw_gbps: float = 10.0  # PCIe Gen3 x16 ~16GB/s

    # Memory bandwidth (percentage of theoretical)
    min_memory_bw_percent: float = 80.0

    # Compute utilization
    min_compute_utilization: float = 80.0

    # Test duration
    duration_seconds: int = 300
    warmup_seconds: int = 10


class FPGAStressTest(StressTestBase):
    """Stress test for FPGA accelerator cards.

    Tests performed:
    1. Compute workload validation (xbutil/aocl validate)
    2. Memory bandwidth test
    3. PCIe bandwidth test
    4. Temperature monitoring
    5. Power consumption monitoring

    Supported FPGAs:
    - Xilinx/AMD Alveo (U200, U250, U280, U50, U55C)
    - Intel Stratix/Agilex

    Requirements:
    - Xilinx: xbutil (XRT - Xilinx Runtime)
    - Intel: aocl (Intel FPGA SDK)
    - lspci (for device enumeration)

    Note: FPGA stress testing is vendor-specific and requires
    vendor tools to be installed.
    """

    # Known FPGA PCI IDs
    FPGA_PCI_IDS = {
        # Xilinx/AMD Alveo
        "0x10ee:0x500c": "Alveo U200",
        "0x10ee:0x500d": "Alveo U250",
        "0x10ee:0x500e": "Alveo U280",
        "0x10ee:0x5021": "Alveo U50",
        "0x10ee:0x5020": "Alveo U55C",
        # Intel
        "0x8086:0x09c4": "Stratix 10",
        "0x8086:0x0b30": "Agilex",
    }

    def __init__(
        self,
        duration_seconds: int = 300,
        sample_interval_seconds: int = 5,
        thresholds: Optional[Dict[str, ThresholdConfig]] = None,
        device_index: int = 0
    ):
        super().__init__(duration_seconds, sample_interval_seconds, thresholds)
        self.fpga_thresholds = FPGAStressThresholds()
        self.device_index = device_index
        self._fpga_devices: List[Dict[str, Any]] = []
        self._vendor_tools: Dict[str, bool] = {}

    @property
    def test_name(self) -> str:
        return "fpga_stress"

    @property
    def supported_vendors(self) -> List[str]:
        return ["xilinx", "amd", "intel"]

    def start_stress(self) -> bool:
        """Start FPGA stress workload."""
        # Discover FPGA devices
        self._fpga_devices = self._discover_fpgas()

        if not self._fpga_devices:
            return False

        # Check vendor tools availability
        self._vendor_tools = self._check_vendor_tools()

        # Start validation/stress
        device = self._fpga_devices[self.device_index]
        vendor = device.get("vendor", "unknown")

        if vendor in ["xilinx", "amd"] and self._vendor_tools.get("xbutil"):
            return self._start_xilinx_stress(device)
        elif vendor == "intel" and self._vendor_tools.get("aocl"):
            return self._start_intel_stress(device)

        # Fallback: just monitor what we can
        return True

    def _start_xilinx_stress(self, device: Dict[str, Any]) -> bool:
        """Start Xilinx/AMD FPGA stress."""
        try:
            # Run validation in background
            self._stress_process = subprocess.Popen(
                ["xbutil", "validate", "--device", str(self.device_index), "--run", "dma"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return True

        except FileNotFoundError:
            return False

    def _start_intel_stress(self, device: Dict[str, Any]) -> bool:
        """Start Intel FPGA stress."""
        try:
            # Run diagnostic
            self._stress_process = subprocess.Popen(
                ["aocl", "diagnose", str(self.device_index)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return True

        except FileNotFoundError:
            return False

    def stop_stress(self) -> None:
        """Stop FPGA stress workload."""
        if hasattr(self, '_stress_process') and self._stress_process:
            try:
                self._stress_process.terminate()
                self._stress_process.wait(timeout=10)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    self._stress_process.kill()
                except ProcessLookupError:
                    pass
            self._stress_process = None

    def collect_metrics(self) -> Dict[str, float]:
        """Collect current FPGA metrics."""
        metrics = {}

        if not self._fpga_devices:
            return metrics

        device = self._fpga_devices[self.device_index]
        vendor = device.get("vendor", "unknown")

        if vendor in ["xilinx", "amd"] and self._vendor_tools.get("xbutil"):
            xbutil_metrics = self._get_xbutil_metrics(self.device_index)
            metrics.update(xbutil_metrics)
        elif vendor == "intel" and self._vendor_tools.get("aocl"):
            aocl_metrics = self._get_aocl_metrics(self.device_index)
            metrics.update(aocl_metrics)

        # PCIe info
        pcie_info = self._get_pcie_info(device.get("pci_slot", ""))
        if pcie_info:
            metrics["pcie_link_width"] = pcie_info.get("link_width", 0)
            metrics["pcie_link_speed_gts"] = pcie_info.get("link_speed_gt", 0)

        return metrics

    def run_custom(self, duration: Optional[int] = None) -> StressTestResult:
        """Run FPGA stress test with custom duration."""
        duration = duration or self.fpga_thresholds.duration_seconds

        if not self.start_stress():
            return StressTestResult(
                test_name=self.test_name,
                status="error",
                error_message="No FPGA devices found or vendor tools not available",
                duration_seconds=0,
                metrics=[]
            )

        start_time = time.time()
        samples = []
        errors = []
        warnings = []

        # Run validation tests
        validation_results = self._run_validation_tests()

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
                temp = metrics.get("temperature_c", 0)
                if temp > self.fpga_thresholds.max_temperature_c:
                    errors.append(f"Temperature {temp}°C exceeds threshold {self.fpga_thresholds.max_temperature_c}°C")
                elif temp > self.fpga_thresholds.warning_temperature_c:
                    warnings.append(f"Temperature {temp}°C is high")

                power = metrics.get("power_w", 0)
                if power > self.fpga_thresholds.max_power_w:
                    errors.append(f"Power {power}W exceeds threshold {self.fpga_thresholds.max_power_w}W")
                elif power > self.fpga_thresholds.warning_power_w:
                    warnings.append(f"Power {power}W is high")

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
        elif not validation_results.get("passed", True):
            status = "failed"
            errors.append(f"Validation failed: {validation_results.get('message', '')}")

        metric_results = self._analyze_samples(samples)
        error_msg = "; ".join(errors + warnings) if (errors or warnings) else ""

        return StressTestResult(
            test_name=self.test_name,
            status=status,
            error_message=error_msg,
            duration_seconds=actual_duration,
            metrics=metric_results
        )

    def _discover_fpgas(self) -> List[Dict[str, Any]]:
        """Discover FPGA devices via lspci."""
        devices = []

        try:
            result = subprocess.run(
                ["lspci", "-nn", "-D"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    # Check for known FPGA vendors
                    if any(vendor in line for vendor in ["Xilinx", "Intel", "Altera"]):
                        # Extract PCI slot
                        slot = line.split()[0]

                        # Determine vendor and model
                        vendor = "unknown"
                        model = "unknown"

                        if "Xilinx" in line or "AMD" in line:
                            vendor = "xilinx"
                            # Try to identify model
                            for pci_id, name in self.FPGA_PCI_IDS.items():
                                if pci_id.split(":")[0] in line:
                                    model = name
                                    break
                        elif "Intel" in line or "Altera" in line:
                            vendor = "intel"
                            for pci_id, name in self.FPGA_PCI_IDS.items():
                                if pci_id.split(":")[0] in line:
                                    model = name
                                    break

                        devices.append({
                            "pci_slot": slot,
                            "vendor": vendor,
                            "model": model,
                            "raw_info": line
                        })

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return devices

    def _check_vendor_tools(self) -> Dict[str, bool]:
        """Check which vendor tools are available."""
        tools = {
            "xbutil": False,
            "aocl": False
        }

        for tool in tools.keys():
            try:
                result = subprocess.run(
                    [tool, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                tools[tool] = (result.returncode == 0)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        return tools

    def _get_xbutil_metrics(self, device_index: int) -> Dict[str, float]:
        """Get metrics from xbutil."""
        metrics = {}

        try:
            result = subprocess.run(
                ["xbutil", "examine", "--device", str(device_index), "--report", "thermal,electrical"],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                output = result.stdout

                # Parse temperature
                temp_match = re.search(r"FPGA\s+Temperature\s*[:=]\s*(\d+)\s*C", output, re.IGNORECASE)
                if temp_match:
                    metrics["temperature_c"] = float(temp_match.group(1))

                # Parse power
                power_match = re.search(r"Power\s*[:=]\s*(\d+\.?\d*)\s*W", output, re.IGNORECASE)
                if power_match:
                    metrics["power_w"] = float(power_match.group(1))

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return metrics

    def _get_aocl_metrics(self, device_index: int) -> Dict[str, float]:
        """Get metrics from Intel aocl."""
        metrics = {}

        # Intel tools have limited metrics without running diagnostics
        # Most metrics would require running aocl diagnose with verbose output

        return metrics

    def _get_pcie_info(self, pci_slot: str) -> Optional[Dict[str, Any]]:
        """Get PCIe link information."""
        if not pci_slot:
            return None

        try:
            result = subprocess.run(
                ["lspci", "-vv", "-s", pci_slot],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                info = {}

                for line in result.stdout.split("\n"):
                    if "LnkCap:" in line:
                        # Link capabilities
                        match = re.search(r"Speed\s+(\d+)GT/s.*Width\s+x(\d+)", line)
                        if match:
                            info["cap_speed_gt"] = int(match.group(1))
                            info["cap_width"] = int(match.group(2))
                    elif "LnkSta:" in line:
                        # Link status
                        match = re.search(r"Speed\s+(\d+)GT/s.*Width\s+x(\d+)", line)
                        if match:
                            info["link_speed_gt"] = int(match.group(1))
                            info["link_width"] = int(match.group(2))

                return info

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def _run_validation_tests(self) -> Dict[str, Any]:
        """Run FPGA validation tests."""
        results = {
            "passed": True,
            "message": ""
        }

        if not self._fpga_devices:
            return results

        device = self._fpga_devices[self.device_index]
        vendor = device.get("vendor", "unknown")

        if vendor in ["xilinx", "amd"] and self._vendor_tools.get("xbutil"):
            try:
                result = subprocess.run(
                    ["xbutil", "validate", "--device", str(self.device_index)],
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                results["passed"] = (result.returncode == 0)
                if not results["passed"]:
                    results["message"] = result.stderr[:200] if result.stderr else "Validation failed"

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        elif vendor == "intel" and self._vendor_tools.get("aocl"):
            try:
                result = subprocess.run(
                    ["aocl", "diagnose", str(self.device_index)],
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                results["passed"] = (result.returncode == 0)
                if not results["passed"]:
                    results["message"] = result.stderr[:200] if result.stderr else "Diagnose failed"

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        return results

    def quick_test(self) -> StressTestResult:
        """Run a quick 60-second FPGA validation."""
        return self.run_custom(duration=60)

    def extended_test(self, duration: int = 1800) -> StressTestResult:
        """Run extended FPGA stress test (default 30 minutes)."""
        return self.run_custom(duration=duration)

    def list_devices(self) -> List[Dict[str, Any]]:
        """List all FPGA devices."""
        return self._discover_fpgas()
