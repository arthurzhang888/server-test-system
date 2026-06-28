"""Unit tests for Network stress test implementation."""

import json
import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from stress_tests.network_stress import NetworkStressTest, NetworkStressThresholds, NetworkTestType
from stress_tests.base import StressTestResult


class TestNetworkTestType:
    """Tests for NetworkTestType enum."""

    def test_enum_values(self):
        assert NetworkTestType.THROUGHPUT == "throughput"
        assert NetworkTestType.LATENCY == "latency"
        assert NetworkTestType.PACKET_GEN == "packet_gen"
        assert NetworkTestType.STRESS == "stress"
        assert isinstance(NetworkTestType.THROUGHPUT, str)


class TestNetworkStressThresholds:
    """Tests for NetworkStressThresholds configuration."""

    def test_default_thresholds(self):
        t = NetworkStressThresholds()
        assert t.min_throughput_percent == 80.0
        assert t.target_throughput_percent == 95.0
        assert t.max_latency_us == 100.0
        assert t.warning_latency_us == 50.0
        assert t.max_packet_loss_percent == 0.1
        assert t.warning_packet_loss_percent == 0.01
        assert t.max_crc_errors == 10
        assert t.max_dropped_packets == 100
        assert t.duration_seconds == 300
        assert t.warmup_seconds == 5
        assert t.parallel_streams == 4
        assert t.buffer_size == 1024 * 1024

    def test_custom_thresholds(self):
        t = NetworkStressThresholds(min_throughput_percent=70.0, max_latency_us=200.0)
        assert t.min_throughput_percent == 70.0
        assert t.max_latency_us == 200.0


class TestNetworkStressTestBasics:
    """Tests for basic NetworkStressTest functionality."""

    def test_test_name_and_vendors(self):
        test = NetworkStressTest()
        assert test.test_name == "network_stress"
        assert all(v in test.supported_vendors for v in ["generic", "mellanox", "intel"])

    def test_default_initialization(self):
        test = NetworkStressTest()
        assert test.duration_seconds == 300
        assert test.sample_interval_seconds == 5
        assert test.interface is None
        assert test.target_host is None
        assert test.iperf3_port == 5201
        assert isinstance(test.net_thresholds, NetworkStressThresholds)

    def test_custom_initialization(self):
        test = NetworkStressTest(duration_seconds=600, interface="eth0",
                                  target_host="192.168.1.1", iperf3_port=5202)
        assert test.duration_seconds == 600
        assert test.interface == "eth0"
        assert test.target_host == "192.168.1.1"
        assert test.iperf3_port == 5202


class TestInterfaceSelection:
    """Tests for network interface selection."""

    @patch("subprocess.run")
    def test_select_best_interface(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps([
            {"ifname": "lo", "flags": ["UP", "LOOPBACK"]},
            {"ifname": "eth0", "flags": ["UP", "BROADCAST"]},
        ]))
        test = NetworkStressTest()
        with patch.object(test, "_get_interface_speed", return_value=1000):
            assert test._select_best_interface() == "eth0"

    @patch("subprocess.run")
    def test_select_best_interface_skips_invalid(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps([
            {"ifname": "lo", "flags": ["UP", "LOOPBACK"]},
            {"ifname": "virbr0", "flags": ["UP", "BROADCAST"]},
            {"ifname": "docker0", "flags": ["UP", "BROADCAST"]},
            {"ifname": "eth1", "flags": ["BROADCAST"]},
            {"ifname": "eth0", "flags": ["UP", "BROADCAST"]},
        ]))
        test = NetworkStressTest()
        with patch.object(test, "_get_interface_speed", return_value=1000):
            assert test._select_best_interface() == "eth0"

    @patch("subprocess.run")
    def test_select_best_interface_fallback(self, mock_run):
        mock_run.side_effect = FileNotFoundError("ip not found")
        test = NetworkStressTest()
        with patch("os.listdir", return_value=["lo", "eth0"]), \
             patch("os.path.islink", return_value=True):
            assert test._select_best_interface() == "eth0"


class TestThroughputMeasurement:
    """Tests for throughput measurement."""

    @patch("subprocess.Popen")
    def test_start_iperf3_stress_success(self, mock_popen):
        mock_popen.return_value = Mock()
        test = NetworkStressTest(target_host="192.168.1.1", iperf3_port=5202)
        test.net_thresholds.parallel_streams = 8
        assert test._start_iperf3_stress() is True
        args = mock_popen.call_args[0][0]
        assert "iperf3" in args and "-c" in args

    @patch("subprocess.Popen")
    def test_start_iperf3_stress_not_found(self, mock_popen):
        mock_popen.side_effect = FileNotFoundError()
        test = NetworkStressTest(target_host="192.168.1.1")
        assert test._start_iperf3_stress() is False

    def test_start_local_stress(self):
        test = NetworkStressTest()
        test.net_thresholds.parallel_streams = 2
        assert test._start_local_stress() is True
        assert len(test._stress_threads) == 2


class TestLatencyMeasurement:
    """Tests for latency measurement using ping."""

    @patch("subprocess.run")
    def test_measure_latency(self, mock_run):
        test = NetworkStressTest()
        # Success - regex captures min latency (0.5ms = 500us)
        mock_run.return_value = Mock(returncode=0,
            stdout="rtt min/avg/max/mdev = 0.5/1.2/2.0/0.3 ms")
        assert test._measure_latency("192.168.1.1") == 500.0
        # Ping fails
        mock_run.return_value = Mock(returncode=1, stdout="")
        assert test._measure_latency("192.168.1.1") is None
        # ping not found
        mock_run.side_effect = FileNotFoundError()
        assert test._measure_latency("192.168.1.1") is None


class TestInterfaceStatistics:
    """Tests for interface statistics collection."""

    def test_get_interface_stats(self):
        test = NetworkStressTest()
        mock_files = {
            "/sys/class/net/eth0/statistics/rx_bytes": "1000",
            "/sys/class/net/eth0/statistics/tx_bytes": "2000",
            "/sys/class/net/eth0/statistics/rx_dropped": "5",
            "/sys/class/net/eth0/statistics/tx_dropped": "3",
        }
        def mock_open(path, mode="r"):
            if path in mock_files:
                m = Mock(read=Mock(return_value=mock_files[path]))
                m.__enter__ = Mock(return_value=m)
                m.__exit__ = Mock(return_value=False)
                return m
            raise FileNotFoundError(path)
        with patch("builtins.open", mock_open):
            stats = test._get_interface_stats("eth0")
        assert stats["rx_bytes"] == 1000
        assert stats["tx_bytes"] == 2000
        assert stats["rx_dropped"] == 5
        # Handles missing files
        with patch("builtins.open", side_effect=FileNotFoundError):
            stats = test._get_interface_stats("eth0")
        assert stats["rx_bytes"] == 0


class TestCRCErrorDetection:
    """Tests for CRC error detection using ethtool."""

    @patch("subprocess.run")
    def test_get_crc_errors(self, mock_run):
        test = NetworkStressTest()
        # rx_crc_errors matches both patterns (5+5=10)
        mock_run.return_value = Mock(returncode=0, stdout="rx_crc_errors: 5")
        assert test._get_crc_errors("eth0") == 10
        # Multiple values: rx_crc_errors (3+3=6) + crc_errors (7) = 13
        mock_run.return_value = Mock(returncode=0, stdout="rx_crc_errors: 3\ncrc_errors: 7")
        assert test._get_crc_errors("eth0") == 13
        # Not found
        mock_run.return_value = Mock(returncode=0, stdout="rx_packets: 100")
        assert test._get_crc_errors("eth0") is None
        # ethtool fails
        mock_run.side_effect = FileNotFoundError()
        assert test._get_crc_errors("eth0") is None


class TestPacketLossDetection:
    """Tests for packet loss detection."""

    def test_collect_metrics(self):
        test = NetworkStressTest()
        test.interface = "eth0"
        with patch.object(test, "_get_interface_stats", return_value={
            "rx_bytes": 1000, "tx_bytes": 2000,
            "rx_dropped": 5, "tx_dropped": 3,
        }), patch.object(test, "_get_crc_errors", return_value=2), \
             patch.object(test, "_get_link_info", return_value={"speed_gbps": 1, "up": True}):
            metrics = test.collect_metrics()
        assert metrics["rx_dropped"] == 5
        assert metrics["tx_dropped"] == 3
        assert metrics["crc_errors"] == 2


class TestStartStopStress:
    """Tests for start/stop stress methods."""

    def test_start_stress(self):
        # No interface found
        test = NetworkStressTest()
        with patch.object(test, "_select_best_interface", return_value=None):
            assert test.start_stress() is False
        # With interface provided
        test = NetworkStressTest(interface="eth0")
        with patch.object(test, "_get_interface_info", return_value={}), \
             patch.object(test, "_get_interface_stats", return_value={}), \
             patch.object(test, "_start_local_stress", return_value=True):
            assert test.start_stress() is True
        # With target host
        test = NetworkStressTest(interface="eth0", target_host="192.168.1.1")
        with patch.object(test, "_get_interface_info", return_value={}), \
             patch.object(test, "_get_interface_stats", return_value={}), \
             patch.object(test, "_start_iperf3_stress", return_value=True):
            assert test.start_stress() is True

    def test_stop_stress(self):
        test = NetworkStressTest()
        assert not test._stop_event.is_set()
        test.stop_stress()
        assert test._stop_event.is_set()

    @patch("subprocess.Popen")
    def test_stop_stress_terminates_iperf3(self, mock_popen):
        mock_process = Mock()
        mock_popen.return_value = mock_process
        test = NetworkStressTest(target_host="192.168.1.1")
        test._start_iperf3_stress()
        test.stop_stress()
        mock_process.terminate.assert_called_once()


class TestTestModes:
    """Tests for quick and extended test modes."""

    def test_quick_test(self):
        test = NetworkStressTest()
        mock_result = StressTestResult(test_name="network_stress", status="passed",
                                       duration_seconds=30, metrics=[])
        with patch.object(test, "run_custom", return_value=mock_result) as mock_run:
            result = test.quick_test()
            mock_run.assert_called_once_with(duration=30)
            assert isinstance(result, StressTestResult)

    def test_extended_test(self):
        test = NetworkStressTest()
        mock_result = StressTestResult(test_name="network_stress", status="passed",
                                       duration_seconds=600, metrics=[])
        with patch.object(test, "run_custom", return_value=mock_result) as mock_run:
            result = test.extended_test(duration=600)
            mock_run.assert_called_once_with(duration=600)
            assert isinstance(result, StressTestResult)


class TestListInterfaces:
    """Tests for list_interfaces method."""

    @patch("subprocess.run")
    def test_list_interfaces(self, mock_run):
        test = NetworkStressTest()
        # Success
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps([
            {"ifname": "lo", "flags": ["UP", "LOOPBACK"], "address": "00:00:00:00:00:00"},
            {"ifname": "eth0", "flags": ["UP", "BROADCAST"], "address": "aa:bb:cc:dd:ee:ff"}
        ]))
        with patch.object(test, "_get_interface_speed", return_value=1000):
            interfaces = test.list_interfaces()
        assert len(interfaces) == 1
        assert interfaces[0]["name"] == "eth0"
        # Error handling
        mock_run.side_effect = FileNotFoundError()
        assert test.list_interfaces() == []
