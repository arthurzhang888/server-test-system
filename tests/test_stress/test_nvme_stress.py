"""Unit tests for NVMe stress test implementation."""

import subprocess
import threading
from unittest.mock import Mock, patch, MagicMock

from src.stress_tests.nvme_stress import NVMeStressTest, NVMeThresholds
from src.stress_tests.base import ThresholdConfig


class TestNVMeThresholds:
    """Tests for NVMeThresholds configuration class."""

    def test_default_thresholds(self):
        """Test that default thresholds are set correctly."""
        t = NVMeThresholds()
        assert t.temperature.min_value == 0 and t.temperature.max_value == 85
        assert t.temperature.warning_pct == 0.82 and t.temperature.critical_pct == 0.95
        assert t.health_percent.min_value == 90 and t.health_percent.max_value == 100
        assert t.spare_percent.min_value == 10 and t.spare_percent.max_value == 100
        assert t.media_errors.min_value == 0 and t.media_errors.max_value == 0
        assert t.power_on_hours.min_value == 0 and t.power_on_hours.max_value == 100000

    def test_custom_thresholds(self):
        """Test that custom thresholds can be provided."""
        t = NVMeThresholds(
            temperature=ThresholdConfig(min_value=0, max_value=90),
            health_percent=ThresholdConfig(min_value=80, max_value=100)
        )
        assert t.temperature.max_value == 90
        assert t.health_percent.min_value == 80
        assert t.spare_percent.min_value == 10  # default


class TestNVMeStressTestBasic:
    """Tests for basic NVMeStressTest functionality."""

    def test_test_name(self):
        """Test that test_name property returns correct value."""
        assert NVMeStressTest().test_name == "nvme_stress"

    def test_default_initialization(self):
        """Test default initialization values."""
        t = NVMeStressTest()
        assert t.duration_seconds == 300 and t.sample_interval_seconds == 5
        assert t.devices == [] and t.test_file_size_gb == 10 and t.write_ratio == 0.3

    def test_custom_initialization(self):
        """Test custom initialization values."""
        t = NVMeStressTest(
            duration_seconds=600, sample_interval_seconds=10,
            devices=["/dev/nvme0n1"], test_file_size_gb=20, write_ratio=0.5
        )
        assert t.duration_seconds == 600 and t.sample_interval_seconds == 10
        assert t.devices == ["/dev/nvme0n1"] and t.test_file_size_gb == 20 and t.write_ratio == 0.5

    def test_thresholds_passed_to_base(self):
        """Test that thresholds are correctly passed to base class."""
        t = NVMeStressTest(thresholds=NVMeThresholds())
        assert all(k in t.thresholds for k in ["temperature", "health_percent", "spare_percent", "media_errors"])


class TestNVMeDeviceDetection:
    """Tests for NVMe device detection functionality."""

    @patch("subprocess.run")
    def test_detect_nvme_devices_with_nvme_cli(self, mock_run):
        """Test device detection using nvme list command."""
        mock_run.return_value = Mock(returncode=0, stdout="Node\n----------------\n/dev/nvme0n1\n/dev/nvme1n1\n")
        devices = NVMeStressTest()._detect_nvme_devices()
        assert "/dev/nvme0n1" in devices and "/dev/nvme1n1" in devices

    @patch("subprocess.run")
    @patch("os.listdir")
    @patch("os.path.exists")
    def test_detect_nvme_devices_fallback(self, mock_exists, mock_listdir, mock_run):
        """Test device detection fallback to /dev directory."""
        mock_run.side_effect = FileNotFoundError("nvme not found")
        mock_listdir.return_value = ["nvme0", "nvme0n1", "nvme1", "nvme1n1", "sda"]
        mock_exists.return_value = True
        devices = NVMeStressTest()._detect_nvme_devices()
        assert "/dev/nvme0n1" in devices and "/dev/nvme1n1" in devices and "/dev/sda" not in devices

    @patch("subprocess.run")
    def test_detect_nvme_devices_no_devices(self, mock_run):
        """Test device detection when no devices found."""
        mock_run.return_value = Mock(returncode=0, stdout="Node\n")
        assert NVMeStressTest()._detect_nvme_devices() == []

    @patch("subprocess.run")
    def test_detect_nvme_devices_timeout(self, mock_run):
        """Test device detection handles timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("nvme list", 10)
        assert NVMeStressTest()._detect_nvme_devices() == []


class TestSMARTMetricsCollection:
    """Tests for SMART metrics collection."""

    @patch("subprocess.run")
    def test_get_smart_metrics_nvme_cli(self, mock_run):
        """Test SMART metrics collection via nvme-cli with Kelvin conversion."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="temperature: 318\navailable_spare: 100%\npercentage_used: 5%\nmedia_errors: 0\npower_on_hours: 1234"
        )
        m = NVMeStressTest(devices=["/dev/nvme0n1"])._get_smart_metrics("/dev/nvme0n1")
        assert m["temperature"] == 45 and m["health_percent"] == 95 and m["spare_percent"] == 100
        assert m["media_errors"] == 0 and m["power_on_hours"] == 1234

    @patch("subprocess.run")
    def test_temperature_already_celsius(self, mock_run):
        """Test temperature parsing when already in Celsius (no conversion needed)."""
        mock_run.return_value = Mock(returncode=0, stdout="temperature: 45")
        assert NVMeStressTest(devices=["/dev/nvme0n1"])._get_smart_metrics("/dev/nvme0n1")["temperature"] == 45

    @patch("subprocess.run")
    def test_smart_metrics_smartctl_fallback(self, mock_run):
        """Test SMART metrics fallback to smartctl when nvme-cli unavailable."""
        mock_run.side_effect = [FileNotFoundError("nvme not found"), Mock(returncode=0, stdout="Temperature: 45 Celsius")]
        assert NVMeStressTest(devices=["/dev/nvme0n1"])._get_smart_metrics("/dev/nvme0n1")["temperature"] == 45

    @patch("subprocess.run")
    def test_smart_metrics_no_tools(self, mock_run):
        """Test SMART metrics returns empty dict when no tools available."""
        mock_run.side_effect = FileNotFoundError("nvme not found")
        assert NVMeStressTest(devices=["/dev/nvme0n1"])._get_smart_metrics("/dev/nvme0n1") == {}

    @patch("subprocess.run")
    def test_health_and_media_errors(self, mock_run):
        """Test health percentage, spare blocks, and media errors parsing."""
        mock_run.return_value = Mock(returncode=0, stdout="percentage_used: 15%\navailable_spare: 75%\nmedia_errors: 5")
        m = NVMeStressTest(devices=["/dev/nvme0n1"])._get_smart_metrics("/dev/nvme0n1")
        assert m["health_percent"] == 85 and m["spare_percent"] == 75 and m["media_errors"] == 5


class TestStressStartStop:
    """Tests for stress test start/stop functionality."""

    @patch.object(NVMeStressTest, "_detect_nvme_devices")
    def test_start_stress_no_devices(self, mock_detect):
        """Test start_stress returns False when no devices."""
        mock_detect.return_value = []
        assert NVMeStressTest().start_stress() is False

    @patch.object(NVMeStressTest, "_stress_device")
    @patch.object(NVMeStressTest, "_detect_nvme_devices")
    def test_start_stress_with_devices(self, mock_detect, mock_stress):
        """Test start_stress creates threads for each device."""
        mock_detect.return_value = ["/dev/nvme0n1", "/dev/nvme1n1"]
        mock_stress.side_effect = lambda d: threading.Event().wait(timeout=0.1)
        t = NVMeStressTest()
        assert t.start_stress() is True and len(t._stress_threads) == 2
        assert all(th.daemon for th in t._stress_threads)
        t.stop_stress()

    def test_stop_stress_clears_threads(self):
        """Test stop_stress clears thread list and joins threads."""
        t = NVMeStressTest(devices=["/dev/nvme0n1"])
        t._stop_stress = threading.Event()
        mock_thread = MagicMock()
        t._stress_threads = [mock_thread]
        t.stop_stress()
        mock_thread.join.assert_called_once_with(timeout=5)
        assert t._stress_threads == []

    @patch("shutil.rmtree")
    @patch("os.path.exists")
    def test_stop_stress_cleanup_temp(self, mock_exists, mock_rmtree):
        """Test stop_stress cleans up temp directory."""
        mock_exists.return_value = True
        t = NVMeStressTest(devices=["/dev/nvme0n1"])
        t._stop_stress, t._stress_threads, t._temp_dir = threading.Event(), [], "/tmp/nvme_stress_test"
        t.stop_stress()
        mock_rmtree.assert_called_once_with("/tmp/nvme_stress_test")
        assert t._temp_dir is None


class TestStressWorkload:
    """Tests for stress workload methods with mocked fio and dd."""

    @patch.object(NVMeStressTest, "_try_fio_stress")
    @patch.object(NVMeStressTest, "_dd_stress")
    def test_stress_device_tries_fio_first(self, mock_dd, mock_fio):
        """Test that fio is tried before dd fallback."""
        mock_fio.return_value = True
        t = NVMeStressTest(devices=["/dev/nvme0n1"])
        t._stop_stress = threading.Event()
        t._stress_device("/dev/nvme0n1")
        mock_fio.assert_called_once_with("/dev/nvme0n1")
        mock_dd.assert_not_called()

    @patch.object(NVMeStressTest, "_try_fio_stress")
    @patch.object(NVMeStressTest, "_dd_stress")
    def test_stress_device_fallback_to_dd(self, mock_dd, mock_fio):
        """Test that dd is used when fio fails."""
        mock_fio.return_value = False
        t = NVMeStressTest(devices=["/dev/nvme0n1"])
        t._stop_stress = threading.Event()
        t._stress_device("/dev/nvme0n1")
        mock_fio.assert_called_once_with("/dev/nvme0n1")
        mock_dd.assert_called_once_with("/dev/nvme0n1")

    @patch("subprocess.Popen")
    @patch.object(NVMeStressTest, "_get_mount_point")
    def test_fio_stress_success(self, mock_get_mount, mock_popen):
        """Test successful fio stress execution with correct parameters."""
        mock_get_mount.return_value = "/mnt"
        mock_process = MagicMock()
        mock_process.poll.side_effect = [None, 0]
        mock_popen.return_value = mock_process
        t = NVMeStressTest(devices=["/dev/nvme0n1"], write_ratio=0.3)
        t._stop_stress = threading.Event()
        t._stop_stress.set()
        assert t._try_fio_stress("/dev/nvme0n1") is True
        call_args = mock_popen.call_args[0][0]
        assert "fio" in call_args[0] and "--rwmixread=70" in call_args  # 70% reads with write_ratio=0.3

    @patch("subprocess.run")
    def test_dd_stress_read_only(self, mock_run):
        """Test dd stress with read-only mode uses raw device reads."""
        t = NVMeStressTest(devices=["/dev/nvme0n1"], write_ratio=0.0)
        t._stop_stress = threading.Event()
        mock_run.side_effect = lambda *a, **k: t._stop_stress.set() or Mock(returncode=0)
        t._dd_stress("/dev/nvme0n1")
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "dd" in call_args[0] and "/dev/nvme0n1" in call_args[1]  # if=device


class TestCollectMetrics:
    """Tests for metrics collection aggregation across devices."""

    @patch.object(NVMeStressTest, "_get_smart_metrics")
    def test_collect_metrics_aggregation(self, mock_get_smart):
        """Test metrics aggregation: max for temp/media_errors, min for health."""
        mock_get_smart.side_effect = [
            {"temperature": 45, "health_percent": 95, "media_errors": 0},
            {"temperature": 55, "health_percent": 90, "media_errors": 5}
        ]
        m = NVMeStressTest(devices=["/dev/nvme0n1", "/dev/nvme1n1"]).collect_metrics()
        assert m["temperature"] == 55 and m["health_percent"] == 90 and m["media_errors"] == 5

    def test_collect_metrics_empty_devices(self):
        """Test collect_metrics returns empty dict with no devices."""
        assert NVMeStressTest(devices=[]).collect_metrics() == {}


class TestMountPoint:
    """Tests for mount point detection from /proc/mounts."""

    @patch("builtins.open")
    def test_get_mount_point_found(self, mock_open):
        """Test getting mount point for a mounted device."""
        mock_open.return_value.__enter__.return_value = ["/dev/nvme0n1 / ext4 rw 0 0\n", "/dev/nvme0n1p1 /boot ext4 rw 0 0\n"]
        assert NVMeStressTest()._get_mount_point("/dev/nvme0n1") == "/"

    @patch("builtins.open")
    def test_get_mount_point_not_found(self, mock_open):
        """Test getting mount point returns None when not mounted."""
        mock_open.return_value.__enter__.return_value = ["/dev/sda1 / ext4 rw 0 0\n"]
        assert NVMeStressTest()._get_mount_point("/dev/nvme0n1") is None
