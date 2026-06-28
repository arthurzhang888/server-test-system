"""Unit tests for Memory stress test implementation."""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from src.stress_tests.memory_stress import (
    MemoryStressTest,
    MemoryStressThresholds,
    MemoryTestType
)
from src.stress_tests.base import MetricStatus, StressTestResult


class TestMemoryTestType:
    """Tests for MemoryTestType enum."""

    def test_allocation_value(self):
        assert MemoryTestType.ALLOCATION == "allocation"

    def test_read_write_value(self):
        assert MemoryTestType.READ_WRITE == "read_write"

    def test_random_access_value(self):
        assert MemoryTestType.RANDOM_ACCESS == "random"

    def test_ecc_value(self):
        assert MemoryTestType.ECC == "ecc"

    def test_bandwidth_value(self):
        assert MemoryTestType.BANDWIDTH == "bandwidth"

    def test_enum_membership(self):
        assert MemoryTestType("allocation") == MemoryTestType.ALLOCATION
        assert MemoryTestType("read_write") == MemoryTestType.READ_WRITE
        assert MemoryTestType("random") == MemoryTestType.RANDOM_ACCESS


class TestMemoryStressThresholds:
    """Tests for MemoryStressThresholds configuration."""

    def test_default_values(self):
        thresholds = MemoryStressThresholds()
        assert thresholds.max_temperature_c == 85.0
        assert thresholds.warning_temperature_c == 75.0
        assert thresholds.max_memory_usage_percent == 95.0
        assert thresholds.target_memory_usage_percent == 90.0
        assert thresholds.max_ecc_errors == 10
        assert thresholds.max_ce_errors == 100
        assert thresholds.min_bandwidth_percent == 80.0
        assert thresholds.max_latency_ns == 100.0
        assert thresholds.duration_seconds == 300
        assert thresholds.warmup_seconds == 10

    def test_custom_values(self):
        thresholds = MemoryStressThresholds(
            max_temperature_c=80.0,
            warning_temperature_c=70.0,
            max_memory_usage_percent=90.0,
            duration_seconds=600
        )
        assert thresholds.max_temperature_c == 80.0
        assert thresholds.warning_temperature_c == 70.0
        assert thresholds.max_memory_usage_percent == 90.0
        assert thresholds.duration_seconds == 600

    def test_partial_custom_values(self):
        thresholds = MemoryStressThresholds(max_ecc_errors=5)
        assert thresholds.max_ecc_errors == 5
        assert thresholds.max_temperature_c == 85.0  # Default unchanged


class TestMemoryStressTestBasic:
    """Tests for basic MemoryStressTest functionality."""

    def test_test_name_property(self):
        test = MemoryStressTest()
        assert test.test_name == "memory_stress"

    def test_supported_vendors(self):
        test = MemoryStressTest()
        vendors = test.supported_vendors
        assert "generic" in vendors
        assert "samsung" in vendors
        assert "micron" in vendors
        assert "hynix" in vendors
        assert "kingston" in vendors

    def test_default_initialization(self):
        test = MemoryStressTest()
        assert test.duration_seconds == 300
        assert test.sample_interval_seconds == 5
        assert test.memory_percent == 80.0
        assert test.mem_thresholds is not None

    def test_custom_initialization(self):
        test = MemoryStressTest(
            duration_seconds=600,
            sample_interval_seconds=10,
            memory_percent=90.0
        )
        assert test.duration_seconds == 600
        assert test.sample_interval_seconds == 10
        assert test.memory_percent == 90.0

    def test_mem_thresholds_is_instance(self):
        test = MemoryStressTest()
        assert isinstance(test.mem_thresholds, MemoryStressThresholds)


class TestMemoryInfo:
    """Tests for memory information gathering."""

    @patch("builtins.open", mock_open(read_data="""MemTotal:       16000000 kB
MemFree:         4000000 kB
MemAvailable:    8000000 kB
"""))
    def test_get_memory_info(self):
        test = MemoryStressTest()
        info = test._get_memory_info()
        assert info["total_gb"] > 0
        assert info["free_gb"] > 0
        assert info["available_gb"] > 0
        assert info["used_gb"] >= 0

    @patch("builtins.open", mock_open(read_data="""MemTotal:       32000000 kB
MemFree:         8000000 kB
MemAvailable:   16000000 kB
"""))
    def test_get_memory_info_usage_calculation(self):
        test = MemoryStressTest()
        info = test._get_memory_info()
        # used_gb = total - available = 32GB - 16GB = 16GB
        expected_usage = (info["used_gb"] / info["total_gb"]) * 100
        assert info["usage_percent"] == pytest.approx(expected_usage, 0.1)

    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_get_memory_info_file_not_found(self, mock_file):
        test = MemoryStressTest()
        info = test._get_memory_info()
        assert info["total_gb"] == 0
        assert info["free_gb"] == 0


class TestECCErrorDetection:
    """Tests for ECC error detection functionality."""

    @patch("glob.glob")
    @patch("builtins.open", mock_open(read_data="5"))
    def test_get_ecc_error_count_from_edac(self, mock_glob):
        mock_glob.side_effect = [
            ["/sys/devices/system/edac/mc/mc0/ce_count"],
            []  # No UE errors
        ]
        test = MemoryStressTest()
        errors = test._get_ecc_error_count()
        assert errors == 5

    @patch("glob.glob")
    @patch("builtins.open", mock_open(read_data="3"))
    def test_get_ecc_error_count_multiple_controllers(self, mock_glob):
        mock_glob.side_effect = [
            ["/sys/devices/system/edac/mc/mc0/ce_count",
             "/sys/devices/system/edac/mc/mc1/ce_count"],
            []
        ]
        test = MemoryStressTest()
        errors = test._get_ecc_error_count()
        assert errors == 6  # 3 + 3 from two controllers

    @patch("glob.glob")
    @patch("builtins.open", mock_open(read_data="1"))
    def test_get_ecc_error_count_with_ue_errors(self, mock_glob):
        mock_glob.side_effect = [
            [],
            ["/sys/devices/system/edac/mc/mc0/ue_count"]
        ]
        test = MemoryStressTest()
        errors = test._get_ecc_error_count()
        assert errors == 1

    @patch("subprocess.run")
    def test_get_ecc_error_count_from_mcelog(self, mock_run):
        mock_run.return_value = Mock(
            returncode=0,
            stdout="memory error detected\nanother memory error"
        )
        test = MemoryStressTest()
        errors = test._get_ecc_error_count()
        assert errors == 2

    @patch("subprocess.run")
    def test_get_ecc_error_count_from_ras_mc_ctl(self, mock_run):
        def side_effect(*args, **kwargs):
            if args[0][0] == "mcelog":
                return Mock(returncode=1, stdout="")
            if args[0][0] == "ras-mc-ctl":
                return Mock(returncode=0, stdout="10 total errors found")
            return Mock(returncode=1, stdout="")
        mock_run.side_effect = side_effect
        test = MemoryStressTest()
        errors = test._get_ecc_error_count()
        assert errors == 10

    @patch("glob.glob")
    @patch("subprocess.run")
    def test_get_ecc_error_count_no_source_available(self, mock_run, mock_glob):
        mock_glob.return_value = []
        mock_run.side_effect = FileNotFoundError()
        test = MemoryStressTest()
        errors = test._get_ecc_error_count()
        assert errors is None


class TestDIMMTemperatures:
    """Tests for DIMM temperature monitoring."""

    @patch("subprocess.run")
    def test_get_dimm_temperatures_ipmi_sensors(self, mock_run):
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Memory Temp 1 | 45.50 degrees C\nMemory Temp 2 | 48.00 degrees C"
        )
        test = MemoryStressTest()
        temps = test._get_dimm_temperatures()
        assert len(temps) == 2
        assert 45.5 in temps
        assert 48.0 in temps

    @patch("subprocess.run")
    def test_get_dimm_temperatures_ipmitool_fallback(self, mock_run):
        def side_effect(*args, **kwargs):
            if args[0][0] == "ipmi-sensors":
                return Mock(returncode=1, stdout="")
            if args[0][0] == "ipmitool":
                return Mock(returncode=0, stdout="DIMM1 | 50 degrees C\nDIMM2 | 55 degrees C")
            return Mock(returncode=1, stdout="")
        mock_run.side_effect = side_effect
        test = MemoryStressTest()
        temps = test._get_dimm_temperatures()
        assert len(temps) == 2
        assert 50.0 in temps

    @patch("subprocess.run")
    def test_get_dimm_temperatures_no_source(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        test = MemoryStressTest()
        temps = test._get_dimm_temperatures()
        assert temps == []


class TestBandwidthMeasurement:
    """Tests for memory bandwidth measurement."""

    def test_get_memory_bandwidth_returns_none(self):
        """Bandwidth measurement is not yet implemented."""
        test = MemoryStressTest()
        bandwidth = test._get_memory_bandwidth()
        assert bandwidth is None

    @patch("subprocess.run")
    def test_run_bandwidth_test_stream(self, mock_run):
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""Copy:         15000.5
Scale:        14500.2
Add:          14000.8
Triad:        14200.1
"""
        )
        test = MemoryStressTest()
        result = test.run_bandwidth_test()
        assert result["copy_gbps"] == 15000.5
        assert result["scale_gbps"] == 14500.2
        assert result["add_gbps"] == 14000.8
        assert result["triad_gbps"] == 14200.1

    @patch("subprocess.run", side_effect=FileNotFoundError())
    def test_run_bandwidth_test_no_stream(self, mock_run):
        test = MemoryStressTest()
        result = test.run_bandwidth_test()
        assert result["copy_gbps"] is None
        assert result["scale_gbps"] is None
        assert result["add_gbps"] is None
        assert result["triad_gbps"] is None


class TestStressStartStop:
    """Tests for stress workload start/stop with mocked tools."""

    @patch("subprocess.Popen")
    @patch.object(MemoryStressTest, "_get_memory_info")
    def test_start_stress_with_stress_ng(self, mock_meminfo, mock_popen):
        mock_meminfo.return_value = {"total_gb": 16, "free_gb": 8}
        mock_popen.return_value = Mock(pid=1234)
        test = MemoryStressTest()
        result = test.start_stress()
        assert result is True
        assert test._stress_process is not None
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "stress-ng"

    @patch("subprocess.Popen")
    @patch.object(MemoryStressTest, "_get_memory_info")
    def test_start_stress_fallback_to_memtester(self, mock_meminfo, mock_popen):
        mock_meminfo.return_value = {"total_gb": 16, "free_gb": 8}

        def side_effect(*args, **kwargs):
            if args[0][0] == "stress-ng":
                raise FileNotFoundError()
            if args[0][0] == "memtester":
                return Mock(pid=1234)
            return Mock()
        mock_popen.side_effect = side_effect

        test = MemoryStressTest()
        result = test.start_stress()
        assert result is True
        mock_popen.assert_called()

    @patch("subprocess.Popen")
    @patch.object(MemoryStressTest, "_get_memory_info")
    def test_start_stress_fallback_to_python(self, mock_meminfo, mock_popen):
        mock_meminfo.return_value = {"total_gb": 16, "free_gb": 8}
        mock_popen.side_effect = FileNotFoundError()
        test = MemoryStressTest()
        result = test.start_stress()
        assert result is True
        assert hasattr(test, "_memory_blocks")

    def test_stop_stress_process(self):
        test = MemoryStressTest()
        mock_process = Mock()
        test._stress_process = mock_process
        test.stop_stress()
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()

    def test_stop_stress_kill_on_timeout(self):
        test = MemoryStressTest()
        mock_process = Mock()
        mock_process.wait = Mock(side_effect=subprocess.TimeoutExpired("cmd", 5))
        test._stress_process = mock_process
        test.stop_stress()
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_stop_stress_clears_memory_blocks(self):
        test = MemoryStressTest()
        test._memory_blocks = [bytearray(1024), bytearray(1024)]
        test.stop_stress()
        assert len(test._memory_blocks) == 0


class TestCollectMetrics:
    """Tests for metric collection."""

    @patch.object(MemoryStressTest, "_get_memory_info")
    @patch.object(MemoryStressTest, "_get_dimm_temperatures")
    @patch.object(MemoryStressTest, "_get_ecc_error_count")
    @patch.object(MemoryStressTest, "_get_memory_bandwidth")
    def test_collect_metrics_all_available(self, mock_bw, mock_ecc, mock_temps, mock_meminfo):
        mock_meminfo.return_value = {
            "usage_percent": 75.0,
            "used_gb": 12.0,
            "available_gb": 4.0
        }
        mock_temps.return_value = [45.0, 48.0]
        mock_ecc.return_value = 0
        mock_bw.return_value = 25.5

        test = MemoryStressTest()
        metrics = test.collect_metrics()

        assert metrics["memory_usage_percent"] == 75.0
        assert metrics["memory_used_gb"] == 12.0
        assert metrics["memory_available_gb"] == 4.0
        assert metrics["dimm_max_temperature_c"] == 48.0
        assert metrics["dimm_avg_temperature_c"] == 46.5
        assert metrics["ecc_errors"] == 0
        assert metrics["memory_bandwidth_gbps"] == 25.5

    @patch.object(MemoryStressTest, "_get_memory_info")
    @patch.object(MemoryStressTest, "_get_dimm_temperatures")
    def test_collect_metrics_no_optional_data(self, mock_temps, mock_meminfo):
        mock_meminfo.return_value = {"usage_percent": 50.0, "used_gb": 8.0, "available_gb": 8.0}
        mock_temps.return_value = []

        test = MemoryStressTest()
        metrics = test.collect_metrics()

        assert "memory_usage_percent" in metrics
        assert "dimm_max_temperature_c" not in metrics
        assert "ecc_errors" not in metrics
        assert "memory_bandwidth_gbps" not in metrics


class TestMultiSocketNUMA:
    """Tests for multi-socket/NUMA handling via EDAC."""

    @patch("glob.glob")
    @patch("builtins.open")
    def test_multiple_mc_controllers(self, mock_open_file, mock_glob):
        mock_glob.side_effect = [
            [
                "/sys/devices/system/edac/mc/mc0/ce_count",
                "/sys/devices/system/edac/mc/mc1/ce_count",
                "/sys/devices/system/edac/mc/mc2/ce_count",
                "/sys/devices/system/edac/mc/mc3/ce_count"
            ],
            []
        ]
        mock_file = Mock()
        mock_file.read.side_effect = ["5", "3", "2", "1"]
        mock_open_file.return_value.__enter__ = Mock(return_value=mock_file)
        mock_open_file.return_value.__exit__ = Mock(return_value=False)

        test = MemoryStressTest()
        errors = test._get_ecc_error_count()
        assert errors == 11  # 5 + 3 + 2 + 1


class TestTestModes:
    """Tests for quick and extended test modes."""

    @patch.object(MemoryStressTest, "run_custom")
    def test_quick_test(self, mock_run_custom):
        mock_run_custom.return_value = StressTestResult(
            test_name="memory_stress",
            duration_seconds=60,
            status="passed"
        )
        test = MemoryStressTest()
        result = test.quick_test()
        mock_run_custom.assert_called_once_with(duration=60)
        assert result.status == "passed"

    @patch.object(MemoryStressTest, "run_custom")
    def test_extended_test_default(self, mock_run_custom):
        mock_run_custom.return_value = StressTestResult(
            test_name="memory_stress",
            duration_seconds=1800,
            status="passed"
        )
        test = MemoryStressTest()
        result = test.extended_test()
        mock_run_custom.assert_called_once_with(duration=1800)

    @patch.object(MemoryStressTest, "run_custom")
    def test_extended_test_custom_duration(self, mock_run_custom):
        test = MemoryStressTest()
        test.extended_test(duration=3600)
        mock_run_custom.assert_called_once_with(duration=3600)


class TestDIMMInfo:
    """Tests for DIMM information gathering."""

    @patch("subprocess.run")
    def test_get_dimm_info_success(self, mock_run):
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""Memory Device
    Array Handle: 0x1000
    Error Information Handle: Not Provided
    Total Width: 72 bits
    Data Width: 64 bits
    Size: 32 GB
    Form Factor: DIMM

Memory Device
    Array Handle: 0x1001
    Size: 32 GB
    Speed: 3200 MT/s
"""
        )
        test = MemoryStressTest()
        dimms = test.get_dimm_info()
        assert len(dimms) == 2
        assert dimms[0].get("size") == "32 GB"

    @patch("subprocess.run", side_effect=FileNotFoundError())
    def test_get_dimm_info_dmidecode_not_found(self, mock_run):
        test = MemoryStressTest()
        dimms = test.get_dimm_info()
        assert dimms == []

    @patch("subprocess.run")
    def test_get_dimm_info_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("dmidecode", 30)
        test = MemoryStressTest()
        dimms = test.get_dimm_info()
        assert dimms == []


class TestRunCustom:
    """Tests for the run_custom method."""

    @patch.object(MemoryStressTest, "start_stress")
    @patch.object(MemoryStressTest, "stop_stress")
    @patch.object(MemoryStressTest, "collect_metrics")
    @patch.object(MemoryStressTest, "_get_ecc_error_count")
    def test_run_custom_success(self, mock_ecc, mock_collect, mock_stop, mock_start):
        mock_start.return_value = True
        mock_ecc.return_value = 0
        mock_collect.return_value = {
            "memory_usage_percent": 50.0,
            "dimm_max_temperature_c": 60.0
        }
        test = MemoryStressTest()
        test.sample_interval_seconds = 0.01
        result = test.run_custom(duration=0.05)
        assert result.test_name == "memory_stress"
        assert result.status in ["passed", "warning"]
        mock_stop.assert_called_once()

    @patch.object(MemoryStressTest, "start_stress")
    def test_run_custom_start_failure(self, mock_start):
        mock_start.return_value = False
        test = MemoryStressTest()
        result = test.run_custom(duration=10)
        assert result.status == "error"
        assert "Failed to start" in result.error_message

    @patch.object(MemoryStressTest, "start_stress")
    @patch.object(MemoryStressTest, "stop_stress")
    @patch.object(MemoryStressTest, "collect_metrics")
    @patch.object(MemoryStressTest, "_get_ecc_error_count")
    def test_run_custom_temperature_threshold(self, mock_ecc, mock_collect, mock_stop, mock_start):
        mock_start.return_value = True
        mock_ecc.return_value = 0
        mock_collect.return_value = {
            "memory_usage_percent": 50.0,
            "dimm_max_temperature_c": 90.0  # Exceeds 85C threshold
        }
        test = MemoryStressTest()
        test.sample_interval_seconds = 0.01
        result = test.run_custom(duration=0.05)
        assert result.status == "failed"
        assert "temperature" in result.error_message.lower()

    @patch.object(MemoryStressTest, "start_stress")
    @patch.object(MemoryStressTest, "stop_stress")
    @patch.object(MemoryStressTest, "collect_metrics")
    @patch.object(MemoryStressTest, "_get_ecc_error_count")
    def test_run_custom_memory_usage_threshold(self, mock_ecc, mock_collect, mock_stop, mock_start):
        mock_start.return_value = True
        mock_ecc.return_value = 0
        mock_collect.return_value = {
            "memory_usage_percent": 98.0,  # Exceeds 95% threshold
            "dimm_max_temperature_c": 60.0
        }
        test = MemoryStressTest()
        test.sample_interval_seconds = 0.01
        result = test.run_custom(duration=0.05)
        assert result.status == "failed"
        assert "memory usage" in result.error_message.lower()

    @patch.object(MemoryStressTest, "start_stress")
    @patch.object(MemoryStressTest, "stop_stress")
    @patch.object(MemoryStressTest, "collect_metrics")
    @patch.object(MemoryStressTest, "_get_ecc_error_count")
    def test_run_custom_ecc_errors(self, mock_ecc, mock_collect, mock_stop, mock_start):
        mock_start.return_value = True
        mock_ecc.side_effect = [0, 15]  # Initial 0, then 15 errors
        mock_collect.return_value = {
            "memory_usage_percent": 50.0,
            "dimm_max_temperature_c": 60.0,
            "ecc_errors": 15
        }
        test = MemoryStressTest()
        test.sample_interval_seconds = 0.01
        result = test.run_custom(duration=0.05)
        assert result.status == "failed"
        assert "ecc" in result.error_message.lower()


import subprocess  # noqa: E402
