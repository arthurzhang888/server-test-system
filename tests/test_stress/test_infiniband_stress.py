"""Tests for InfiniBand stress test."""

import subprocess
import pytest
from unittest.mock import patch, MagicMock, mock_open

from src.stress_tests.infiniband_stress import InfiniBandStressTest, IBStressThresholds, IBTestType


class TestIBStressTestBasic:
    """Test InfiniBand stress test basic functionality."""

    def test_test_name(self):
        test = InfiniBandStressTest()
        assert test.test_name == "infiniband_stress"

    def test_supported_vendors(self):
        test = InfiniBandStressTest()
        assert all(v in test.supported_vendors for v in ["mellanox", "intel", "qlogic"])

    def test_default_thresholds(self):
        test = InfiniBandStressTest()
        assert test.ib_thresholds.min_bw_percent == 80.0
        assert test.ib_thresholds.target_bw_percent == 95.0
        assert test.ib_thresholds.max_latency_us == 5.0
        assert test.ib_thresholds.warning_latency_us == 3.0
        assert test.ib_thresholds.max_symbol_errors == 100
        assert test.ib_thresholds.max_link_recoveries == 10
        assert test.ib_thresholds.max_vl15_dropped == 100
        assert test.ib_thresholds.duration_seconds == 300


class TestIBStressThresholds:
    """Test IB stress thresholds configuration."""

    def test_default_msg_sizes(self):
        thresholds = IBStressThresholds()
        assert thresholds.msg_sizes == [256, 1024, 4096, 65536, 1048576]

    def test_custom_thresholds(self):
        thresholds = IBStressThresholds(
            min_bw_percent=70.0, target_bw_percent=90.0, max_latency_us=10.0,
            max_symbol_errors=200, duration_seconds=600
        )
        assert thresholds.min_bw_percent == 70.0
        assert thresholds.target_bw_percent == 90.0
        assert thresholds.max_latency_us == 10.0
        assert thresholds.max_symbol_errors == 200
        assert thresholds.duration_seconds == 600

    def test_custom_msg_sizes(self):
        custom_sizes = [512, 2048, 8192]
        thresholds = IBStressThresholds(msg_sizes=custom_sizes)
        assert thresholds.msg_sizes == custom_sizes


class TestIBTestType:
    """Test IBTestType enum."""

    def test_test_types(self):
        assert IBTestType.BANDWIDTH == "bandwidth"
        assert IBTestType.LATENCY == "latency"
        assert IBTestType.BIDIRECTIONAL == "bidirectional"
        assert IBTestType.ATOMIC == "atomic"
        assert IBTestType.MULTICAST == "multicast"

    def test_all_test_types(self):
        types = list(IBTestType)
        assert len(types) == 5
        assert all(t in types for t in [IBTestType.BANDWIDTH, IBTestType.LATENCY,
                                        IBTestType.BIDIRECTIONAL, IBTestType.ATOMIC, IBTestType.MULTICAST])


class TestIBDeviceDetection:
    """Test IB device detection."""

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_discover_ib_devices_ibstat(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="mlx5_0\nmlx5_1\n")
        test = InfiniBandStressTest()
        devices = test._discover_ib_devices()
        assert len(devices) == 2
        assert devices[0]["name"] == "mlx5_0"
        assert devices[1]["name"] == "mlx5_1"

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_discover_no_ibstat(self, mock_run):
        mock_run.side_effect = FileNotFoundError("ibstat not found")
        test = InfiniBandStressTest()
        devices = test._discover_ib_devices()
        assert devices == []

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_discover_ibstat_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ibstat"], timeout=10)
        test = InfiniBandStressTest()
        devices = test._discover_ib_devices()
        assert devices == []


class TestLinkSpeedDetection:
    """Test IB link speed detection for all speed grades."""

    @pytest.mark.parametrize("speed_str,expected_gbps", [
        ("10 Gb/sec", 10), ("20 Gb/sec", 20), ("40 Gb/sec", 40), ("56 Gb/sec", 56),
        ("100 Gb/sec", 100), ("200 Gb/sec", 200), ("400 Gb/sec", 400),
    ])
    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_link_speeds(self, mock_run, speed_str, expected_gbps):
        mock_run.return_value = MagicMock(returncode=0, stdout=f"state: Active\nrate: {speed_str}")
        test = InfiniBandStressTest()
        info = test._get_link_info("mlx5_0")
        assert info["state"] == "Active"
        assert info["speed_gbps"] == expected_gbps

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_link_down_state(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="state: Down\nrate: 0 Gb/sec")
        test = InfiniBandStressTest()
        info = test._get_link_info("mlx5_0")
        assert info["state"] == "Down"

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_link_speed_ibstatus_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("ibstatus not found")
        test = InfiniBandStressTest()
        info = test._get_link_info("mlx5_0")
        assert info["state"] == "Unknown"
        assert info["speed_gbps"] == 0


class TestPortCounters:
    """Test IB port counter reading."""

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_port_counters_perfquery(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="SymbolError: 5\nLinkErrorRecovery: 2\nVL15Dropped: 0\n")
        test = InfiniBandStressTest()
        counters = test._get_port_counters("mlx5_0")
        assert counters["symbol_error"] == 5
        assert counters["link_error_recovery"] == 2
        assert counters["vl15_dropped"] == 0

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_port_counters_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        test = InfiniBandStressTest()
        counters = test._get_port_counters("mlx5_0")
        assert counters["symbol_error"] == 0
        assert counters["link_error_recovery"] == 0
        assert counters["vl15_dropped"] == 0


class TestRDMABandwidth:
    """Test RDMA bandwidth tests."""

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_run_bw_test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="#bytes #iterations BW peak[Gb/sec] BW average[Gb/sec]\n65536 1000 95.2 94.8")
        test = InfiniBandStressTest()
        result = test._run_bw_test(65536)
        assert result == 94.8

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_run_bw_test_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("ib_write_bw not found")
        test = InfiniBandStressTest()
        result = test._run_bw_test(65536)
        assert result is None

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_run_bw_test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ib_write_bw"], timeout=30)
        test = InfiniBandStressTest()
        result = test._run_bw_test(65536)
        assert result is None


class TestTemperatureReading:
    """Test IB adapter temperature reading."""

    @patch("builtins.open", mock_open(read_data="65000"))
    @patch("glob.glob")
    def test_get_temperature_hwmon(self, mock_glob):
        mock_glob.return_value = ["/sys/class/infiniband/mlx5_0/hwmon0/temp1_input"]
        test = InfiniBandStressTest()
        temp = test._get_ib_temperature("mlx5_0")
        assert temp == 65.0

    @patch("glob.glob")
    def test_get_temperature_no_hwmon(self, mock_glob):
        mock_glob.return_value = []
        test = InfiniBandStressTest()
        temp = test._get_ib_temperature("mlx5_0")
        assert temp is None

    @patch("builtins.open")
    @patch("glob.glob")
    def test_get_temperature_read_error(self, mock_glob, mock_file):
        mock_glob.return_value = ["/sys/class/infiniband/mlx5_0/hwmon0/temp1_input"]
        mock_file.side_effect = IOError("Permission denied")
        test = InfiniBandStressTest()
        temp = test._get_ib_temperature("mlx5_0")
        assert temp is None


class TestQuickAndExtendedModes:
    """Test quick and extended test modes."""

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_quick_test(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        test = InfiniBandStressTest()
        result = test.quick_test()
        assert result.test_name == "infiniband_stress"

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_extended_test(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        test = InfiniBandStressTest()
        result = test.extended_test(duration=60)
        assert result.test_name == "infiniband_stress"

    def test_list_devices(self):
        test = InfiniBandStressTest()
        devices = test.list_devices()
        assert isinstance(devices, list)


class TestStartStopStress:
    """Test stress start and stop operations."""

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_start_stress_no_devices(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        test = InfiniBandStressTest()
        result = test.start_stress()
        assert result is False

    @patch("src.stress_tests.infiniband_stress.subprocess.Popen")
    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_start_stress_with_target(self, mock_run, mock_popen):
        mock_run.return_value = MagicMock(returncode=0, stdout="mlx5_0\n")
        mock_popen.return_value = MagicMock()
        test = InfiniBandStressTest(target_lid=1)
        result = test.start_stress()
        assert result is True

    def test_stop_stress(self):
        test = InfiniBandStressTest()
        test.stop_stress()


class TestCollectMetrics:
    """Test metrics collection."""

    def test_collect_metrics_no_devices(self):
        test = InfiniBandStressTest()
        test._ib_devices = []
        metrics = test.collect_metrics()
        assert metrics == {}

    @patch("src.stress_tests.infiniband_stress.subprocess.run")
    def test_collect_metrics_with_device(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="state: Active\nrate: 100 Gb/sec")
        test = InfiniBandStressTest()
        test._ib_devices = [{"name": "mlx5_0", "speed_gbps": 100, "state": "Active"}]
        test._initial_port_counters["mlx5_0"] = {"symbol_error": 0, "link_error_recovery": 0, "vl15_dropped": 0, "xmit_wait": 0}
        metrics = test.collect_metrics()
        assert "mlx5_0_link_up" in metrics
        assert "mlx5_0_link_speed_gbps" in metrics
