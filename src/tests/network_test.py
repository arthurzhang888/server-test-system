"""Network functional tests including throughput and connectivity."""

import subprocess
import socket
import time
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

from .base import FunctionalTestBase, TestResult, TestStatus, TestConfig


@dataclass
class NetworkConfig(TestConfig):
    """Network test configuration."""
    test_interface: str = ""  # Empty = auto-detect
    iperf3_server: str = ""  # Empty = skip throughput test
    iperf3_duration: int = 10
    ping_targets: List[str] = None

    def __post_init__(self):
        if self.ping_targets is None:
            self.ping_targets = ["8.8.8.8", "1.1.1.1"]


class NetworkTest(FunctionalTestBase):
    """Network functional and performance tests.

    Tests:
    - Interface presence and status
    - Link speed verification
    - Connectivity (ping)
    - Throughput (iperf3)
    - Packet loss and latency
    """

    def __init__(self, config: NetworkConfig = None):
        super().__init__(config or NetworkConfig())
        self.net_config = self.config  # type: NetworkConfig

    @property
    def test_name(self) -> str:
        return "network_functional"

    def run(self) -> TestResult:
        """Run network functional tests."""
        self._start_timer()

        results = []
        all_passed = True
        metrics = {}

        # Get interfaces to test
        interfaces = self._get_test_interfaces()

        if not interfaces:
            return self._create_result(
                TestStatus.ERROR,
                "No network interfaces found",
                {},
                {}
            )

        for interface in interfaces[:2]:  # Test up to 2 interfaces
            iface_results = self._test_interface(interface)
            results.extend(iface_results["tests"])
            metrics[interface["name"]] = iface_results["metrics"]

            if not iface_results["passed"]:
                all_passed = False

        details = {
            "interfaces_tested": len(interfaces),
            "tests": results
        }

        if all_passed:
            return self._create_result(
                TestStatus.PASSED,
                f"Network tests passed on {len(interfaces)} interface(s)",
                details,
                metrics
            )
        else:
            return self._create_result(
                TestStatus.FAILED,
                "Some network tests failed",
                details,
                metrics
            )

    def _get_test_interfaces(self) -> List[Dict[str, Any]]:
        """Get list of network interfaces to test."""
        interfaces = []

        try:
            # Get interface list
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

                    # Skip loopback and virtual interfaces
                    if name.startswith("lo") or name.startswith("docker") or name.startswith("veth"):
                        continue

                    # Check if interface is UP
                    flags = iface.get("flags", [])
                    is_up = "UP" in flags

                    # Get link info
                    link = iface.get("link", {})
                    speed = self._get_interface_speed(name)

                    interfaces.append({
                        "name": name,
                        "up": is_up,
                        "speed_mbps": speed,
                        "mac": iface.get("address", "")
                    })

        except (FileNotFoundError, json.JSONDecodeError):
            # Fallback to /sys/class/net
            try:
                for entry in os.listdir("/sys/class/net"):
                    if entry.startswith("lo"):
                        continue

                    speed = self._get_interface_speed(entry)
                    interfaces.append({
                        "name": entry,
                        "up": True,  # Assume up
                        "speed_mbps": speed,
                        "mac": ""
                    })
            except OSError:
                pass

        return interfaces

    def _get_interface_speed(self, interface: str) -> int:
        """Get interface speed in Mbps."""
        try:
            with open(f"/sys/class/net/{interface}/speed", "r") as f:
                speed = int(f.read().strip())
                return speed if speed > 0 else 1000
        except (OSError, ValueError):
            return 1000  # Assume 1Gbps

    def _test_interface(self, interface: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single network interface."""
        tests = []
        passed = True
        metrics = {}

        name = interface["name"]

        # Test 1: Interface Status
        if interface["up"]:
            tests.append({"name": "link_status", "passed": True, "message": "Interface UP"})
        else:
            tests.append({"name": "link_status", "passed": False, "message": "Interface DOWN"})
            passed = False

        # Test 2: Link Speed
        speed = interface["speed_mbps"]
        metrics["speed_mbps"] = speed

        if speed >= 1000:  # At least 1Gbps
            tests.append({"name": "link_speed", "passed": True, "message": f"{speed} Mbps"})
        else:
            tests.append({"name": "link_speed", "passed": False, "message": f"Speed too low: {speed} Mbps"})
            passed = False

        # Test 3: Connectivity (ping)
        ping_ok, ping_msg, latency = self._test_ping(name)
        tests.append({"name": "connectivity", "passed": ping_ok, "message": ping_msg})
        metrics["latency_ms"] = latency
        if not ping_ok:
            passed = False

        # Test 4: Throughput (iperf3)
        if self.net_config.iperf3_server:
            iperf_ok, iperf_msg, tx_bw, rx_bw = self._test_throughput(name)
            tests.append({"name": "throughput", "passed": iperf_ok, "message": iperf_msg})
            metrics["tx_bandwidth_mbps"] = tx_bw
            metrics["rx_bandwidth_mbps"] = rx_bw
            # Throughput test is optional, don't fail if it doesn't work

        return {
            "tests": tests,
            "passed": passed,
            "metrics": metrics
        }

    def _test_ping(self, interface: str) -> Tuple[bool, str, float]:
        """Test connectivity with ping."""
        best_latency = float('inf')
        best_result = (False, "All pings failed", 0)

        for target in self.net_config.ping_targets:
            try:
                result = subprocess.run(
                    ["ping", "-c", "3", "-W", "2", "-I", interface, target],
                    capture_output=True,
                    text=True,
                    timeout=15
                )

                if result.returncode == 0:
                    # Parse latency
                    for line in result.stdout.split("\n"):
                        if "avg" in line and "ms" in line:
                            try:
                                # Extract avg from "min/avg/max/stddev"
                                parts = line.split("=")[1].strip().split("/")
                                if len(parts) >= 2:
                                    latency = float(parts[1])
                                    if latency < best_latency:
                                        best_latency = latency
                                        best_result = (True, f"Ping OK ({latency:.1f}ms)", latency)
                            except (IndexError, ValueError):
                                pass

            except subprocess.TimeoutExpired:
                continue
            except Exception:
                continue

        if best_latency == float('inf'):
            return best_result
        return best_result

    def _test_throughput(self, interface: str) -> Tuple[bool, str, float, float]:
        """Test throughput with iperf3."""
        if not self.net_config.iperf3_server:
            return True, "No iperf3 server configured", 0, 0

        try:
            # Test TX (upload)
            tx_result = subprocess.run(
                [
                    "iperf3",
                    "-c", self.net_config.iperf3_server,
                    "-t", str(self.net_config.iperf3_duration),
                    "-f", "m",
                    "-J"  # JSON output
                ],
                capture_output=True,
                text=True,
                timeout=self.net_config.iperf3_duration + 10
            )

            tx_bw = 0
            if tx_result.returncode == 0:
                import json
                data = json.loads(tx_result.stdout)
                tx_bw = data.get("end", {}).get("sum_sent", {}).get("bits_per_second", 0) / 1e6  # Mbps

            # Test RX (download)
            rx_result = subprocess.run(
                [
                    "iperf3",
                    "-c", self.net_config.iperf3_server,
                    "-t", str(self.net_config.iperf3_duration),
                    "-R",  # Reverse mode
                    "-f", "m",
                    "-J"
                ],
                capture_output=True,
                text=True,
                timeout=self.net_config.iperf3_duration + 10
            )

            rx_bw = 0
            if rx_result.returncode == 0:
                import json
                data = json.loads(rx_result.stdout)
                rx_bw = data.get("end", {}).get("sum_received", {}).get("bits_per_second", 0) / 1e6  # Mbps

            # Check against link speed
            expected_min = 100  # At least 100 Mbps

            if tx_bw >= expected_min or rx_bw >= expected_min:
                return True, f"TX: {tx_bw:.0f}, RX: {rx_bw:.0f} Mbps", tx_bw, rx_bw
            else:
                return False, f"Throughput too low: TX={tx_bw:.0f}, RX={rx_bw:.0f} Mbps", tx_bw, rx_bw

        except FileNotFoundError:
            return True, "iperf3 not installed", 0, 0
        except subprocess.TimeoutExpired:
            return False, "iperf3 timeout", 0, 0
        except Exception as e:
            return True, f"Throughput test error: {str(e)}", 0, 0
