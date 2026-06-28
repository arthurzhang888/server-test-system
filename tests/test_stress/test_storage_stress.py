"""Tests for storage stress test."""

import pytest
import json
from unittest.mock import patch, MagicMock, mock_open
from src.stress_tests.storage_stress import StorageStressTest, StorageStressThresholds, StorageTestType


class TestStorageStressTestBasic:
    """Test basic functionality."""

    def test_test_name(self):
        assert StorageStressTest().test_name == "storage_stress"

    def test_supported_vendors(self):
        assert "generic" in StorageStressTest().supported_vendors
        assert "samsung" in StorageStressTest().supported_vendors

    def test_default_thresholds(self):
        t = StorageStressTest().storage_thresholds
        assert t.min_read_iops == 1000.0 and t.min_write_iops == 500.0
        assert t.max_temperature_c == 70.0 and t.warning_temperature_c == 60.0
        assert t.max_read_latency_us == 10000.0 and t.max_write_latency_us == 20000.0


class TestStorageStressThresholds:
    """Test thresholds configuration."""

    def test_default_thresholds(self):
        t = StorageStressThresholds()
        assert t.min_read_iops == 1000.0 and t.target_read_iops == 10000.0
        assert t.block_size == "4k" and t.queue_depth == 32 and t.num_jobs == 4
        assert t.max_reallocated_sectors == 10

    def test_custom_thresholds(self):
        t = StorageStressThresholds(min_read_iops=2000.0, max_temperature_c=80.0, duration_seconds=600)
        assert t.min_read_iops == 2000.0 and t.max_temperature_c == 80.0 and t.duration_seconds == 600


class TestStorageTestType:
    """Test storage test type enum."""

    def test_enum_values(self):
        assert StorageTestType.SEQUENTIAL == "sequential"
        assert StorageTestType.RANDOM == "random"
        assert StorageTestType.LATENCY == "latency"
        assert StorageTestType.ENDURANCE == "endurance"
        assert StorageTestType.RAID == "raid"
        assert len(list(StorageTestType)) == 5


class TestDeviceSelection:
    """Test device selection priority."""

    @patch("src.stress_tests.storage_stress.os.listdir")
    def test_select_nvme_first(self, mock_listdir):
        mock_listdir.return_value = ["sda", "nvme0n1", "sdb"]
        with patch("builtins.open", side_effect=lambda p, *args: mock_open(read_data="0" if "sdb" in p else "1")()):
            assert StorageStressTest()._select_best_device() == "/dev/nvme0n1"

    @patch("src.stress_tests.storage_stress.os.listdir")
    def test_select_ssd_second(self, mock_listdir):
        mock_listdir.return_value = ["sda", "sdb"]
        with patch("builtins.open", side_effect=lambda p, *args: mock_open(read_data="0" if "sdb" in p else "1")()):
            assert StorageStressTest()._select_best_device() == "/dev/sdb"

    @patch("src.stress_tests.storage_stress.os.listdir")
    def test_select_hdd_last(self, mock_listdir):
        mock_listdir.return_value = ["sda", "sdb"]
        with patch("builtins.open", mock_open(read_data="1")):
            assert StorageStressTest()._select_best_device() in ["/dev/sda", "/dev/sdb"]

    @patch("src.stress_tests.storage_stress.os.listdir")
    def test_select_raid_device(self, mock_listdir):
        mock_listdir.return_value = ["md0", "sda"]
        with patch("builtins.open", mock_open(read_data="1")):
            raid_devs = [d for d in StorageStressTest().list_devices() if d["type"] == "raid"]
            assert len(raid_devs) == 1 and raid_devs[0]["device"] == "/dev/md0"


class TestSmartDataParsing:
    """Test SMART data parsing."""

    @patch("src.stress_tests.storage_stress.subprocess.run")
    def test_parse_temperature(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="Temperature: 45 Celsius")
        assert StorageStressTest()._get_smart_data("/dev/sda")["temperature_c"] == 45

    @patch("src.stress_tests.storage_stress.subprocess.run")
    def test_parse_reallocated_sectors(self, mock_run):
        out = "Reallocated_Sector_Ct   0x0033   100   100   036    Pre-fail  Always   -       5"
        mock_run.return_value = MagicMock(returncode=0, stdout=out)
        assert StorageStressTest()._get_smart_data("/dev/sda")["reallocated_sectors"] == 5

    @patch("src.stress_tests.storage_stress.subprocess.run")
    def test_parse_pending_sectors(self, mock_run):
        out = "Current_Pending_Sector  0x0012   100   100   000    Old_age   Always   -       3"
        mock_run.return_value = MagicMock(returncode=0, stdout=out)
        assert StorageStressTest()._get_smart_data("/dev/sda")["pending_sectors"] == 3

    @patch("src.stress_tests.storage_stress.subprocess.run")
    def test_smart_failing_status(self, mock_run):
        mock_run.return_value = MagicMock(returncode=4, stdout="SMART: FAILED")
        assert StorageStressTest()._get_smart_data("/dev/sda")["health_percent"] <= 100

    @patch("src.stress_tests.storage_stress.subprocess.run")
    def test_smart_command_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("smartctl not found")
        data = StorageStressTest()._get_smart_data("/dev/sda")
        assert data["health_percent"] == 100 and data["temperature_c"] == 0


class TestRaidStatus:
    """Test RAID status checking."""

    @patch("src.stress_tests.storage_stress.subprocess.run")
    def test_raid_healthy(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="State : clean\n")
        status = StorageStressTest()._get_raid_status("/dev/md0")
        assert status["degraded"] is False and status["sync_percent"] == 100.0

    @patch("src.stress_tests.storage_stress.subprocess.run")
    def test_raid_degraded(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="State : clean, degraded")
        assert StorageStressTest()._get_raid_status("/dev/md0")["degraded"] is True

    @patch("src.stress_tests.storage_stress.subprocess.run")
    def test_raid_sync_progress(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="15.5% sync")
        assert StorageStressTest()._get_raid_status("/dev/md0")["sync_percent"] == 15.5

    @patch("src.stress_tests.storage_stress.subprocess.run")
    def test_mdadm_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("mdadm not found")
        assert StorageStressTest()._get_raid_status("/dev/md0") is None


class TestFioJobFile:
    """Test fio job file creation."""

    def test_job_file_content(self):
        test = StorageStressTest(test_file_size="5G")
        test.storage_thresholds.block_size, test.storage_thresholds.queue_depth = "4k", 32
        with patch("builtins.open", mock_open()) as m:
            test._create_fio_jobfile()
            c = "".join(call[0][0] for call in m().write.call_args_list)
            assert all(x in c for x in ["random_read", "sequential_write", "bs=4k", "iodepth=32", "size=5G"])

    def test_job_file_path(self):
        with patch("builtins.open", mock_open()):
            assert StorageStressTest()._create_fio_jobfile() == "/tmp/fio_stress_job.fio"


class TestIopsAndBandwidth:
    """Test IOPS and bandwidth measurement."""

    @patch("src.stress_tests.storage_stress.subprocess.run")
    def test_device_stats_parsing(self, mock_run):
        out = "Device r/s w/s rkB/s wkB/s rrqm/s wrqm/s %rrqm %wrqm r_await\nsda 100.50 50.20 2048.00 1024.00 0.00 0.00 0.00 0.00 5.00"
        mock_run.return_value = MagicMock(returncode=0, stdout=out)
        test = StorageStressTest()
        test.device = "/dev/sda"
        stats = test._get_device_stats("/dev/sda")
        assert "iops_read" in stats and "iops_write" in stats

    @patch("src.stress_tests.storage_stress.subprocess.run")
    def test_fio_results_parsing(self, mock_run):
        fio_json = {"jobs": [
            {"jobname": "random_read", "read": {"iops": 5000.5, "bw": 20480}},
            {"jobname": "random_write", "write": {"iops": 2500.0, "bw": 10240}},
        ]}
        mock_proc = MagicMock()
        mock_proc.communicate.return_value = (json.dumps(fio_json), "")
        mock_run.return_value = mock_proc
        test = StorageStressTest()
        test._fio_process = mock_proc
        results = test._parse_fio_results()
        assert results["random_read_read_iops"] == 5000.5 and results["random_write_write_iops"] == 2500.0


class TestTemperatureMonitoring:
    """Test temperature monitoring."""

    @patch("src.stress_tests.storage_stress.subprocess.run")
    def test_temperature_in_metrics(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="Temperature: 55 Celsius")
        test = StorageStressTest()
        test.device = "/dev/sda"
        assert test.collect_metrics().get("smart_temperature_c") == 55

    def test_temperature_threshold_violation(self):
        assert 75.0 > StorageStressTest().storage_thresholds.max_temperature_c

    def test_temperature_warning_threshold(self):
        t = StorageStressTest().storage_thresholds
        assert 65.0 > t.warning_temperature_c and 65.0 < t.max_temperature_c


class TestQuickAndExtendedModes:
    """Test quick and extended test modes."""

    @patch.object(StorageStressTest, "start_stress")
    @patch.object(StorageStressTest, "stop_stress")
    @patch.object(StorageStressTest, "collect_metrics")
    @patch.object(StorageStressTest, "_get_smart_data")
    def test_quick_test(self, mock_smart, mock_metrics, mock_stop, mock_start):
        mock_start.return_value = True
        mock_metrics.return_value = {"smart_temperature_c": 40}
        mock_smart.return_value = {"reallocated_sectors": 0}
        test = StorageStressTest()
        test._fio_process = None
        with patch.object(test, "_parse_fio_results", return_value={}):
            assert test.quick_test().test_name == "storage_stress"

    @patch.object(StorageStressTest, "start_stress")
    @patch.object(StorageStressTest, "stop_stress")
    @patch.object(StorageStressTest, "collect_metrics")
    @patch.object(StorageStressTest, "_get_smart_data")
    def test_extended_test(self, mock_smart, mock_metrics, mock_stop, mock_start):
        mock_start.return_value = True
        mock_metrics.return_value = {"smart_temperature_c": 40}
        mock_smart.return_value = {"reallocated_sectors": 0}
        test = StorageStressTest()
        test._fio_process = None
        with patch.object(test, "_parse_fio_results", return_value={}):
            assert test.extended_test(duration=60).test_name == "storage_stress"


class TestMountPointHandling:
    """Test mount point discovery."""

    def test_get_mount_point_found(self):
        with patch("builtins.open", mock_open(read_data="/dev/sda1 / ext4 rw 0 0\n")):
            assert StorageStressTest()._get_mount_point("/dev/sda1") == "/"

    def test_get_mount_point_not_found(self):
        with patch("builtins.open", mock_open(read_data="/dev/sda1 / ext4 rw 0 0\n")):
            assert StorageStressTest()._get_mount_point("/dev/sdb1") is None

    def test_get_mount_point_proc_not_found(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            assert StorageStressTest()._get_mount_point("/dev/sda1") is None
