"""Tests for CPU stress test."""

import subprocess
import pytest
from unittest.mock import patch, MagicMock, mock_open

from src.stress_tests.cpu_stress import CPUStressTest, CPUThresholds
from src.stress_tests.base import ThresholdConfig, MetricStatus


class TestCPUStressTestBasic:
    """Test CPU stress test basic functionality."""

    def test_test_name(self):
        test = CPUStressTest()
        assert test.test_name == "cpu_stress"

    def test_default_threads(self):
        test = CPUStressTest()
        # Should default to cpu_count or 4
        assert test.threads >= 1

    def test_custom_threads(self):
        test = CPUStressTest(threads=8)
        assert test.threads == 8

    def test_default_duration(self):
        test = CPUStressTest()
        assert test.duration_seconds == 300

    def test_custom_duration(self):
        test = CPUStressTest(duration_seconds=600)
        assert test.duration_seconds == 600

    def test_default_sample_interval(self):
        test = CPUStressTest()
        assert test.sample_interval_seconds == 5


class TestCPUStressThresholds:
    """Test CPU stress threshold configurations."""

    def test_default_thresholds(self):
        test = CPUStressTest()
        assert "temperature" in test.thresholds
        assert "utilization" in test.thresholds
        assert "frequency" in test.thresholds

    def test_default_temperature_threshold(self):
        thresholds = CPUThresholds()
        assert thresholds.temperature.max_value == 95
        assert thresholds.temperature.min_value == 0
        assert thresholds.temperature.warning_pct == 0.89
        assert thresholds.temperature.critical_pct == 0.95

    def test_default_utilization_threshold(self):
        thresholds = CPUThresholds()
        assert thresholds.utilization.min_value == 80
        assert thresholds.utilization.max_value == 100

    def test_default_frequency_threshold(self):
        thresholds = CPUThresholds()
        assert thresholds.frequency.min_value == 1000
        assert thresholds.frequency.max_value == 5000

    def test_custom_thresholds(self):
        custom_thresholds = CPUThresholds(
            temperature=ThresholdConfig(min_value=0, max_value=85, warning_pct=0.8, critical_pct=0.95),
            utilization=ThresholdConfig(min_value=70, max_value=100),
            frequency=ThresholdConfig(min_value=800, max_value=4000)
        )
        test = CPUStressTest(thresholds=custom_thresholds)

        assert test.thresholds["temperature"].max_value == 85
        assert test.thresholds["utilization"].min_value == 70
        assert test.thresholds["frequency"].min_value == 800


class TestCPUStressTestMock:
    """Test CPU stress test with mocked subprocess and system calls."""

    @patch("src.stress_tests.cpu_stress.subprocess.Popen")
    @patch("src.stress_tests.cpu_stress.time.sleep")
    def test_start_stress_with_stress_ng(self, mock_sleep, mock_popen):
        """Test starting stress with stress-ng available."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        test = CPUStressTest()
        result = test.start_stress()

        assert result is True
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "stress-ng"
        assert "--cpu" in args

    @patch("src.stress_tests.cpu_stress.subprocess.Popen")
    def test_start_stress_stress_ng_not_found(self, mock_popen):
        """Test fallback to Python CPU burn when stress-ng not found."""
        mock_popen.side_effect = FileNotFoundError("stress-ng not found")

        test = CPUStressTest(threads=2)
        result = test.start_stress()

        assert result is True
        assert len(test._cpu_burn_threads) == 2

    @patch("src.stress_tests.cpu_stress.subprocess.Popen")
    @patch("src.stress_tests.cpu_stress.time.sleep")
    def test_start_stress_process_exits_immediately(self, mock_sleep, mock_popen):
        """Test when stress-ng process exits immediately after starting."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process already exited
        mock_popen.return_value = mock_process

        test = CPUStressTest()
        result = test.start_stress()

        # Returns False when process fails to stay running
        assert result is False

    @patch("src.stress_tests.cpu_stress.subprocess.Popen")
    def test_stop_stress_process(self, mock_popen):
        """Test stopping stress-ng process."""
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        test = CPUStressTest()
        test.start_stress()
        test.stop_stress()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)

    @patch("src.stress_tests.cpu_stress.subprocess.Popen")
    def test_stop_stress_process_timeout(self, mock_popen):
        """Test killing stress process when terminate times out."""
        mock_process = MagicMock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)
        mock_popen.return_value = mock_process

        test = CPUStressTest()
        test.start_stress()
        test.stop_stress()

        mock_process.kill.assert_called_once()

    def test_stop_stress_python_threads(self):
        """Test stopping Python CPU burn threads."""
        import threading
        test = CPUStressTest(threads=2)

        # Manually set up threads
        test._stop_cpu_burn.clear()
        test._cpu_burn_threads = []

        def dummy_burn():
            test._stop_cpu_burn.wait(timeout=0.1)

        for _ in range(2):
            t = threading.Thread(target=dummy_burn)
            t.start()
            test._cpu_burn_threads.append(t)

        test.stop_stress()

        assert len(test._cpu_burn_threads) == 0


class TestCPUTemperatureReading:
    """Test CPU temperature reading from various sources."""

    @patch("src.stress_tests.cpu_stress.subprocess.run")
    def test_get_temperature_from_sensors(self, mock_run):
        """Test reading temperature from sensors command."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="temp1_input: 65.500\ntemp1_max: 100.000\n"
        )

        test = CPUStressTest()
        temp = test._get_cpu_temperature()

        assert temp == 65.5

    @patch("src.stress_tests.cpu_stress.subprocess.run")
    def test_get_temperature_from_sensors_no_match(self, mock_run):
        """Test when sensors output has no temperature."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Some other output\n"
        )

        test = CPUStressTest()
        temp = test._get_cpu_temperature()

        assert temp == 0.0

    @patch("src.stress_tests.cpu_stress.subprocess.run")
    def test_get_temperature_sensors_not_found(self, mock_run):
        """Test fallback when sensors command not found."""
        mock_run.side_effect = FileNotFoundError("sensors not found")

        test = CPUStressTest()
        temp = test._get_cpu_temperature()

        assert temp == 0.0

    @patch("builtins.open", mock_open(read_data="65000"))
    @patch("os.path.exists")
    def test_get_temperature_from_thermal_zone(self, mock_exists):
        """Test reading temperature from thermal zone sysfs."""
        mock_exists.return_value = True

        test = CPUStressTest()
        temp = test._get_cpu_temperature()

        assert temp == 65.0

    @patch("os.path.exists")
    def test_get_temperature_thermal_zone_not_found(self, mock_exists):
        """Test when no thermal zone available."""
        mock_exists.return_value = False

        test = CPUStressTest()
        temp = test._get_cpu_temperature()

        assert temp == 0.0


class TestCPUFrequencyReading:
    """Test CPU frequency reading from various sources."""

    @patch("builtins.open", mock_open(read_data="cpu MHz\t\t: 2400.500\n"))
    def test_get_frequency_from_cpuinfo(self):
        """Test reading frequency from /proc/cpuinfo."""
        test = CPUStressTest()
        freq = test._get_cpu_frequency()

        assert freq == 2400.5

    @patch("builtins.open", mock_open(read_data="no match here\n"))
    def test_get_frequency_cpuinfo_no_match(self):
        """Test when cpuinfo has no frequency line."""
        test = CPUStressTest()
        freq = test._get_cpu_frequency()

        assert freq == 0.0

    @patch("builtins.open", mock_open(read_data="2400000"))
    @patch("os.path.exists")
    def test_get_frequency_from_cpufreq(self, mock_exists):
        """Test reading frequency from cpufreq sysfs."""
        mock_exists.return_value = True

        test = CPUStressTest()
        freq = test._get_cpu_frequency()

        assert freq == 2400.0

    @patch("os.path.exists")
    def test_get_frequency_cpufreq_not_found(self, mock_exists):
        """Test when cpufreq sysfs not available."""
        mock_exists.return_value = False

        test = CPUStressTest()
        freq = test._get_cpu_frequency()

        assert freq == 0.0


class TestCPUCollectMetrics:
    """Test CPU metrics collection."""

    def test_collect_metrics_with_psutil(self):
        """Test collecting metrics with psutil available."""
        # Create mock psutil module with cpu_percent function
        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = 85.5

        test = CPUStressTest()

        # Mock temperature and frequency
        test._get_cpu_temperature = MagicMock(return_value=60.0)
        test._get_cpu_frequency = MagicMock(return_value=2500.0)

        # Inject mock psutil into sys.modules
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            metrics = test.collect_metrics()

        assert metrics["utilization"] == 85.5
        assert metrics["temperature"] == 60.0
        assert metrics["frequency"] == 2500.0
        assert "load_average" in metrics

    def test_collect_metrics_without_psutil(self):
        """Test collecting metrics when psutil not available."""
        test = CPUStressTest()

        # Mock temperature and frequency
        test._get_cpu_temperature = MagicMock(return_value=55.0)
        test._get_cpu_frequency = MagicMock(return_value=2400.0)

        # Simulate psutil not available by patching import
        with patch.dict("sys.modules", {"psutil": None}):
            metrics = test.collect_metrics()

        assert metrics["utilization"] == 0.0  # Fallback when psutil not available
        assert metrics["temperature"] == 55.0
        assert metrics["frequency"] == 2400.0

    @patch("os.getloadavg")
    def test_collect_metrics_load_average(self, mock_getloadavg):
        """Test collecting load average."""
        mock_getloadavg.return_value = (2.5, 2.0, 1.5)

        test = CPUStressTest()
        test._get_cpu_temperature = MagicMock(return_value=50.0)
        test._get_cpu_frequency = MagicMock(return_value=2400.0)

        metrics = test.collect_metrics()

        assert metrics["load_average"] == 2.5

    @patch("os.getloadavg")
    def test_collect_metrics_load_average_unavailable(self, mock_getloadavg):
        """Test when load average is not available."""
        mock_getloadavg.side_effect = OSError("Not available")

        test = CPUStressTest()
        test._get_cpu_temperature = MagicMock(return_value=50.0)
        test._get_cpu_frequency = MagicMock(return_value=2400.0)

        metrics = test.collect_metrics()

        assert metrics["load_average"] == 0.0


class TestCPUQuickAndExtended:
    """Test quick and extended test modes."""

    @patch.object(CPUStressTest, "run")
    def test_quick_test(self, mock_run):
        """Test quick 30-second test mode."""
        mock_run.return_value = MagicMock(
            test_name="cpu_stress",
            status="passed",
            duration_seconds=30
        )

        test = CPUStressTest(duration_seconds=300)
        result = test.quick_test()

        assert test.duration_seconds == 300  # Original restored
        mock_run.assert_called_once()

    @patch.object(CPUStressTest, "run")
    def test_extended_test(self, mock_run):
        """Test extended test mode with custom duration."""
        mock_run.return_value = MagicMock(
            test_name="cpu_stress",
            status="passed",
            duration_seconds=1800
        )

        test = CPUStressTest(duration_seconds=300)
        result = test.extended_test(duration=1800)

        assert test.duration_seconds == 300  # Original restored
        mock_run.assert_called_once()

    @patch.object(CPUStressTest, "run")
    def test_extended_test_default_duration(self, mock_run):
        """Test extended test mode with default 30-minute duration."""
        mock_run.return_value = MagicMock(
            test_name="cpu_stress",
            status="passed",
            duration_seconds=1800
        )

        test = CPUStressTest(duration_seconds=300)
        result = test.extended_test()

        # Verify that run was called with duration=1800 set temporarily
        mock_run.assert_called_once()


class TestCPUStressIntegration:
    """Integration-style tests for CPU stress test."""

    @patch("src.stress_tests.cpu_stress.subprocess.Popen")
    @patch("src.stress_tests.cpu_stress.time.sleep")
    def test_full_run_with_mock_stress(self, mock_sleep, mock_popen):
        """Test a full run with mocked stress process."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        test = CPUStressTest(duration_seconds=2, sample_interval_seconds=1)

        # Mock metrics collection
        test.collect_metrics = MagicMock(return_value={
            "utilization": 95.0,
            "temperature": 70.0,
            "frequency": 2500.0,
            "load_average": 8.0
        })

        result = test.run()

        assert result.test_name == "cpu_stress"
        assert result.status in ["passed", "failed", "error"]
        mock_process.terminate.assert_called_once()

    def test_full_run_start_failure(self):
        """Test handling when stress fails to start."""
        test = CPUStressTest(duration_seconds=1)
        test.start_stress = MagicMock(return_value=False)

        result = test.run()

        assert result.test_name == "cpu_stress"
        assert result.status == "error"
        assert "Failed to start" in result.error_message
