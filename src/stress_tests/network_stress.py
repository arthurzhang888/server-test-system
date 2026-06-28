"""Network interface stress test implementation."""

import subprocess
import time
import re
import socket
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from .base import StressTestBase, ThresholdConfig, MetricResult, MetricStatus, StressTestResult


class NetworkTestType(str, Enum):
    """Types of network stress tests."""
    THROUGHPUT = "throughput"      # Bandwidth test
    LATENCY = "latency"            # Latency/packet loss
    PACKET_GEN = "packet_gen"      # Packet generation
    STRESS = "stress"              # Sustained load


@dataclass
class NetworkStressThresholds:
    """Thresholds specific to network stress testing."""
    # Throughput thresholds (percentage of link speed)
    min_throughput_percent: float = 80.0
    target_throughput_percent: float = 95.0

    # Latency thresholds (microseconds)
    max_latency_us: float = 100.0
    warning_latency_us: float = 50.0

    # Packet loss thresholds (percentage)
    max_packet_loss_percent: float = 0.1
    warning_packet_loss_percent: float = 0.01

    # Error thresholds
    max_crc_errors: int = 10
    max_dropped_packets: int = 100

    # Test duration
    duration_seconds: int = 300
    warmup_seconds: int = 5

    # Test parameters
    parallel_streams: int = 4
    buffer_size: int = 1024 * 1024  # 1MB


class NetworkStressTest(StressTestBase):
    """Stress test for network interfaces.

    Tests performed:
    1. Throughput test (iperf3 or similar)
    2. Latency measurement (ping)
    3. Packet loss detection
    4. Interface error monitoring
    5. Sustained load test

    Supports:
    - Ethernet (1G/10G/25G/40G/100G/200G/400G)
    - InfiniBand (if configured as IPoIB)
    - Bonded interfaces

    Requirements:
    - iperf3 (for throughput testing)
    - ethtool (for interface statistics)
    - ping (for latency)
    - netperf (optional, alternative to iperf3)

    Note: For full throughput testing, a remote iperf3 server is required.
    Without a remote server, only local interface statistics can be monitored.
    """

    def __init__(
        self,
        duration_seconds: int = 300,
        sample_interval_seconds: int = 5,
        thresholds: Optional[Dict[str, ThresholdConfig]] = None,
        interface: Optional[str] = None,
        target_host: Optional[str] = None,
        iperf3_port: int = 5201
    ):
        super().__init__(duration_seconds, sample_interval_seconds, thresholds)
        self.net_thresholds = NetworkStressThresholds()
        self.interface = interface
        self.target_host = target_host
        self.iperf3_port = iperf3_port
        self._stress_threads: List[threading.Thread] = []
        self._stop_event = threading.Event()

    @property
    def test_name(self) -> str:
        return "network_stress"

    @property
    def supported_vendors(self) -> List[str]:
        return ["generic", "mellanox", "intel", "broadcom", "realtek"]

    def start_stress(self) -> bool:
        """Start network stress workload."""
        # Discover target interface
        if not self.interface:
            self.interface = self._select_best_interface()

        if not self.interface:
            return False

        # Get interface info
        self._interface_info = self._get_interface_info(self.interface)

        # Record initial statistics
        self._initial_stats = self._get_interface_stats(self.interface)

        # Start iperf3 client if target host is available
        if self.target_host:
            return self._start_iperf3_stress()

        # Otherwise, use packet generation or loopback test
        return self._start_local_stress()

    def _start_iperf3_stress(self) -> bool:
        """Start iperf3-based stress test."""
        try:
            self._iperf3_process = subprocess.Popen(
                [
                    "iperf3",
                    "-c", self.target_host,
                    "-p", str(self.iperf3_port),
                    "-t", str(self.duration_seconds + 60),  # Longer than test
                    "-P", str(self.net_thresholds.parallel_streams),
                    "-l", str(self.net_thresholds.buffer_size),
                    "-f", "g",  # Gigabits
                    "-i", "1",   # 1 second intervals
                    "--json"     # JSON output
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return True

        except FileNotFoundError:
            return False

    def _start_local_stress(self) -> bool:
        """Start local stress without remote target."""
        # Start packet generation threads
        for i in range(self.net_thresholds.parallel_streams):
            thread = threading.Thread(target=self._packet_generation_worker)
            thread.daemon = True
            thread.start()
            self._stress_threads.append(thread)

        return True

    def _packet_generation_worker(self) -> None:
        """Worker thread for local packet generation."""
        # Create UDP socket for stress generation
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            packet = b'X' * 1400  # Typical MTU-sized packet

            while not self._stop_event.is_set():
                # Send to localhost (will be dropped, generates load)
                try:
                    sock.sendto(packet, ("127.0.0.1", 9))  # Discard port
                except:
                    pass
                time.sleep(0.001)  # Rate limit

            sock.close()

        except Exception:
            pass

    def stop_stress(self) -> None:
        """Stop network stress workload."""
        self._stop_event.set()

        # Stop iperf3
        if hasattr(self, '_iperf3_process') and self._iperf3_process:
            try:
                self._iperf3_process.terminate()
                self._iperf3_process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    self._iperf3_process.kill()
                except ProcessLookupError:
                    pass

        # Wait for threads
        for thread in self._stress_threads:
            thread.join(timeout=2)

        self._stress_threads.clear()

    def collect_metrics(self) -> Dict[str, float]:
        """Collect current network metrics."""
        metrics = {}

        if not self.interface:
            return metrics

        # Interface statistics
        stats = self._get_interface_stats(self.interface)

        # Calculate rates
        if hasattr(self, '_last_stats') and self._last_stats:
            time_delta = time.time() - self._last_time
            if time_delta > 0:
                rx_bytes_delta = stats.get("rx_bytes", 0) - self._last_stats.get("rx_bytes", 0)
                tx_bytes_delta = stats.get("tx_bytes", 0) - self._last_stats.get("tx_bytes", 0)

                rx_gbps = (rx_bytes_delta * 8) / (time_delta * 1e9)
                tx_gbps = (tx_bytes_delta * 8) / (time_delta * 1e9)

                metrics["rx_throughput_gbps"] = max(0, rx_gbps)
                metrics["tx_throughput_gbps"] = max(0, tx_gbps)

        self._last_stats = stats.copy()
        self._last_time = time.time()

        # Error counts
        metrics["rx_errors"] = stats.get("rx_errors", 0)
        metrics["tx_errors"] = stats.get("tx_errors", 0)
        metrics["rx_dropped"] = stats.get("rx_dropped", 0)
        metrics["tx_dropped"] = stats.get("tx_dropped", 0)

        # CRC errors (from ethtool -S)
        crc_errors = self._get_crc_errors(self.interface)
        if crc_errors is not None:
            metrics["crc_errors"] = crc_errors

        # Latency (if target host available)
        if self.target_host:
            latency = self._measure_latency(self.target_host)
            if latency is not None:
                metrics["latency_us"] = latency

        # Link status
        link_info = self._get_link_info(self.interface)
        metrics["link_speed_gbps"] = link_info.get("speed_gbps", 0)
        metrics["link_up"] = 1.0 if link_info.get("up", False) else 0.0

        return metrics

    def run_custom(self, duration: Optional[int] = None) -> StressTestResult:
        """Run network stress test with custom duration."""
        duration = duration or self.net_thresholds.duration_seconds

        if not self.start_stress():
            return StressTestResult(
                test_name=self.test_name,
                status="error",
                error_message="Failed to start network stress workload",
                duration_seconds=0,
                metrics=[]
            )

        start_time = time.time()
        samples = []
        errors = []
        warnings = []

        # Warmup period
        time.sleep(self.net_thresholds.warmup_seconds)

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
                link_speed = metrics.get("link_speed_gbps", 0)
                tx_speed = metrics.get("tx_throughput_gbps", 0)

                if link_speed > 0:
                    utilization = (tx_speed / link_speed) * 100

                    if utilization < self.net_thresholds.min_throughput_percent:
                        warnings.append(f"Throughput {utilization:.1f}% below threshold {self.net_thresholds.min_throughput_percent}%")

                # Check latency
                latency = metrics.get("latency_us")
                if latency and latency > self.net_thresholds.max_latency_us:
                    errors.append(f"Latency {latency:.1f}us exceeds threshold {self.net_thresholds.max_latency_us}us")

                # Check errors
                if metrics.get("crc_errors", 0) > self.net_thresholds.max_crc_errors:
                    errors.append(f"CRC errors {metrics['crc_errors']} exceed threshold")

                # Report progress
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

        # Convert samples to metric results
        metric_results = self._analyze_samples(samples)

        error_msg = "; ".join(errors + warnings) if (errors or warnings) else ""

        return StressTestResult(
            test_name=self.test_name,
            status=status,
            error_message=error_msg,
            duration_seconds=actual_duration,
            metrics=metric_results
        )

    def _select_best_interface(self) -> Optional[str]:
        """Select best network interface for testing."""
        # Prioritize: high-speed interfaces > up interfaces
        try:
            result = subprocess.run(
                ["ip", "-j", "link", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                import json
                interfaces = json.loads(result.stdout)

                best_iface = None
                best_speed = 0

                for iface in interfaces:
                    name = iface.get("ifname", "")

                    # Skip loopback and virtual
                    if name == "lo" or "virbr" in name or "docker" in name:
                        continue

                    # Check if up
                    if "UP" not in iface.get("flags", []):
                        continue

                    # Get speed
                    speed = self._get_interface_speed(name)
                    if speed > best_speed:
                        best_speed = speed
                        best_iface = name

                return best_iface

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

        # Fallback: try to find any ethernet interface
        try:
            for iface in os.listdir("/sys/class/net/"):
                if iface != "lo" and os.path.islink(f"/sys/class/net/{iface}/device"):
                    return iface
        except FileNotFoundError:
            pass

        return None

    def _get_interface_info(self, interface: str) -> Dict[str, Any]:
        """Get interface information."""
        info = {
            "name": interface,
            "speed_gbps": 0,
            "duplex": "unknown",
            "mtu": 1500
        }

        try:
            # Get MTU
            with open(f"/sys/class/net/{interface}/mtu", "r") as f:
                info["mtu"] = int(f.read().strip())

            # Get speed and duplex from ethtool
            result = subprocess.run(
                ["ethtool", interface],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Speed:" in line:
                        match = re.search(r"Speed:\s+(\d+)\s*Mb/s", line)
                        if match:
                            info["speed_gbps"] = int(match.group(1)) / 1000
                    elif "Duplex:" in line:
                        info["duplex"] = line.split(":")[1].strip().lower()

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return info

    def _get_interface_stats(self, interface: str) -> Dict[str, int]:
        """Get interface statistics from sysfs."""
        stats = {
            "rx_bytes": 0,
            "tx_bytes": 0,
            "rx_packets": 0,
            "tx_packets": 0,
            "rx_errors": 0,
            "tx_errors": 0,
            "rx_dropped": 0,
            "tx_dropped": 0
        }

        stat_files = {
            "rx_bytes": "statistics/rx_bytes",
            "tx_bytes": "statistics/tx_bytes",
            "rx_packets": "statistics/rx_packets",
            "tx_packets": "statistics/tx_packets",
            "rx_errors": "statistics/rx_errors",
            "tx_errors": "statistics/tx_errors",
            "rx_dropped": "statistics/rx_dropped",
            "tx_dropped": "statistics/tx_dropped"
        }

        for key, filename in stat_files.items():
            try:
                with open(f"/sys/class/net/{interface}/{filename}", "r") as f:
                    stats[key] = int(f.read().strip())
            except (FileNotFoundError, ValueError):
                pass

        return stats

    def _get_crc_errors(self, interface: str) -> Optional[int]:
        """Get CRC errors from ethtool -S."""
        crc_errors = 0
        found = False

        try:
            result = subprocess.run(
                ["ethtool", "-S", interface],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                crc_patterns = [
                    r"rx_crc_errors:\s+(\d+)",
                    r"crc_errors:\s+(\d+)",
                    r"rx_crc:\s+(\d+)",
                    r"crc:\s+(\d+)"
                ]

                for line in result.stdout.split("\n"):
                    for pattern in crc_patterns:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            crc_errors += int(match.group(1))
                            found = True

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return crc_errors if found else None

    def _get_interface_speed(self, interface: str) -> int:
        """Get interface speed in Mbps."""
        try:
            result = subprocess.run(
                ["ethtool", interface],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    match = re.search(r"Speed:\s+(\d+)\s*Mb/s", line)
                    if match:
                        return int(match.group(1))

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return 0

    def _get_link_info(self, interface: str) -> Dict[str, Any]:
        """Get link status information."""
        info = {"up": False, "speed_gbps": 0}

        try:
            result = subprocess.run(
                ["ip", "link", "show", interface],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                info["up"] = "state UP" in result.stdout

                # Get speed
                info["speed_gbps"] = self._get_interface_speed(interface) / 1000

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return info

    def _measure_latency(self, target: str, count: int = 10) -> Optional[float]:
        """Measure latency to target using ping."""
        try:
            result = subprocess.run(
                ["ping", "-c", str(count), "-i", "0.2", target],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Parse average latency
                match = re.search(r"(\d+\.?\d*)/\d+\.?\d*/\d+\.?\d*/\d+\.?\d*", result.stdout)
                if match:
                    return float(match.group(1)) * 1000  # Convert to microseconds

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def quick_test(self) -> StressTestResult:
        """Run a quick 30-second network stress test."""
        return self.run_custom(duration=30)

    def extended_test(self, duration: int = 1800) -> StressTestResult:
        """Run extended network stress test (default 30 minutes)."""
        return self.run_custom(duration=duration)

    def list_interfaces(self) -> List[Dict[str, Any]]:
        """List all available network interfaces with info."""
        interfaces = []

        try:
            result = subprocess.run(
                ["ip", "-j", "link", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)

                for iface in data:
                    name = iface.get("ifname", "")

                    # Skip loopback
                    if name == "lo":
                        continue

                    info = {
                        "name": name,
                        "up": "UP" in iface.get("flags", []),
                        "mac": iface.get("address", ""),
                        "speed_gbps": self._get_interface_speed(name) / 1000
                    }

                    interfaces.append(info)

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

        return interfaces
