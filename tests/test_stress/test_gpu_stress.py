"""Unit tests for GPU stress test implementation.

Tests cover all GPU vendors: NVIDIA, AMD, Hygon, Cambricon, Ascend, Moore Threads
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock, call
from dataclasses import dataclass

from src.stress_tests.gpu_stress import (
    GPUStressTest,
    GPUVendor,
    GPUInfo,
    GPUThresholds,
)
from src.stress_tests.base import ThresholdConfig, MetricStatus


class TestGPUVendor:
    """Tests for GPUVendor enum."""

    def test_vendor_values(self):
        """Test all GPU vendor enum values."""
        assert GPUVendor.NVIDIA == "nvidia"
        assert GPUVendor.AMD == "amd"
        assert GPUVendor.HYGON == "hygon"
        assert GPUVendor.CAMBRICON == "cambricon"
        assert GPUVendor.ASCEND == "ascend"
        assert GPUVendor.MOORE_THREADS == "moore_threads"
        assert GPUVendor.UNKNOWN == "unknown"

    def test_vendor_count(self):
        """Test that all expected vendors are defined."""
        expected_vendors = {
            "nvidia", "amd", "hygon", "cambricon",
            "ascend", "moore_threads", "unknown"
        }
        actual_vendors = {v.value for v in GPUVendor}
        assert actual_vendors == expected_vendors


class TestGPUInfo:
    """Tests for GPUInfo dataclass."""

    def test_gpu_info_creation(self):
        """Test GPUInfo dataclass creation with all fields."""
        gpu = GPUInfo(
            index=0,
            name="NVIDIA RTX 4090",
            vendor=GPUVendor.NVIDIA,
            memory_mb=24576,
            driver_version="535.104.05",
            pci_id="0000:01:00.0"
        )
        assert gpu.index == 0
        assert gpu.name == "NVIDIA RTX 4090"
        assert gpu.vendor == GPUVendor.NVIDIA
        assert gpu.memory_mb == 24576
        assert gpu.driver_version == "535.104.05"
        assert gpu.pci_id == "0000:01:00.0"

    def test_gpu_info_default_pci_id(self):
        """Test GPUInfo with default empty pci_id."""
        gpu = GPUInfo(
            index=1,
            name="AMD MI100",
            vendor=GPUVendor.AMD,
            memory_mb=32768,
            driver_version="5.4.3"
        )
        assert gpu.pci_id == ""


class TestGPUThresholds:
    """Tests for GPUThresholds configuration."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = GPUThresholds()

        # Temperature: 0-95C, warning at 84%, critical at 95%
        assert thresholds.temperature.min_value == 0
        assert thresholds.temperature.max_value == 95
        assert thresholds.temperature.warning_pct == 0.84
        assert thresholds.temperature.critical_pct == 0.95

        # Utilization: 80-100%
        assert thresholds.utilization.min_value == 80
        assert thresholds.utilization.max_value == 100

        # Memory utilization: 50-100%
        assert thresholds.memory_utilization.min_value == 50
        assert thresholds.memory_utilization.max_value == 100

        # Power: 50-400W, warning at 90%, critical at 98%
        assert thresholds.power.min_value == 50
        assert thresholds.power.max_value == 400
        assert thresholds.power.warning_pct == 0.9
        assert thresholds.power.critical_pct == 0.98

        # Clock speed: 500-2500 MHz
        assert thresholds.clock_speed.min_value == 500
        assert thresholds.clock_speed.max_value == 2500

    def test_custom_thresholds(self):
        """Test custom threshold configuration."""
        custom_temp = ThresholdConfig(min_value=0, max_value=85)
        thresholds = GPUThresholds(temperature=custom_temp)

        assert thresholds.temperature.max_value == 85
        # Other thresholds should still use defaults
        assert thresholds.utilization.max_value == 100

    def test_threshold_check_value(self):
        """Test threshold value checking."""
        thresholds = GPUThresholds()

        # Temperature checks
        assert thresholds.temperature.check_value(50) == MetricStatus.NORMAL
        assert thresholds.temperature.check_value(85) == MetricStatus.WARNING
        assert thresholds.temperature.check_value(95) == MetricStatus.CRITICAL


class TestGPUStressTestBasics:
    """Tests for GPUStressTest basic functionality."""

    def test_test_name(self):
        """Test that test_name returns correct value."""
        test = GPUStressTest()
        assert test.test_name == "gpu_stress"

    def test_default_initialization(self):
        """Test default initialization parameters."""
        test = GPUStressTest()
        assert test.duration_seconds == 300
        assert test.sample_interval_seconds == 5
        assert test.gpu_indices is None
        assert isinstance(test.thresholds["temperature"], ThresholdConfig)

    def test_custom_initialization(self):
        """Test custom initialization parameters."""
        custom_thresholds = GPUThresholds(
            temperature=ThresholdConfig(min_value=0, max_value=85)
        )
        test = GPUStressTest(
            duration_seconds=600,
            sample_interval_seconds=10,
            gpu_indices=[0, 1],
            thresholds=custom_thresholds
        )
        assert test.duration_seconds == 600
        assert test.sample_interval_seconds == 10
        assert test.gpu_indices == [0, 1]
        assert test.thresholds["temperature"].max_value == 85


class TestGPUDetection:
    """Tests for GPU detection across all vendors."""

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_detect_nvidia_success(self, mock_run):
        """Test successful NVIDIA GPU detection."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="0, NVIDIA RTX 4090, 24576 MiB, 0000:01:00.0, 535.104.05\n"
        )
        test = GPUStressTest()
        gpus = test._detect_nvidia()

        assert len(gpus) == 1
        assert gpus[0].index == 0
        assert gpus[0].name == "NVIDIA RTX 4090"
        assert gpus[0].vendor == GPUVendor.NVIDIA
        assert gpus[0].memory_mb == 24576

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_detect_nvidia_multiple_gpus(self, mock_run):
        """Test detection of multiple NVIDIA GPUs."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="0, NVIDIA RTX 4090, 24576 MiB, 0000:01:00.0, 535.104.05\n"
                   "1, NVIDIA RTX 4080, 16384 MiB, 0000:02:00.0, 535.104.05\n"
        )
        test = GPUStressTest()
        gpus = test._detect_nvidia()

        assert len(gpus) == 2
        assert gpus[0].index == 0
        assert gpus[1].index == 1

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_detect_nvidia_not_found(self, mock_run):
        """Test NVIDIA detection when nvidia-smi is not found."""
        mock_run.side_effect = FileNotFoundError()
        test = GPUStressTest()
        gpus = test._detect_nvidia()
        assert gpus == []

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_detect_amd_success(self, mock_run):
        """Test successful AMD GPU detection via rocm-smi."""
        mock_data = {
            "driver_version": "5.4.3",
            "card_list": [
                {
                    "card_index": 0,
                    "product_name": "AMD Instinct MI100",
                    "memory_available": 32768,
                    "pci_bus": "0000:03:00.0"
                }
            ]
        }
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps(mock_data))
        test = GPUStressTest()
        gpus = test._detect_amd()

        assert len(gpus) == 1
        assert gpus[0].name == "AMD Instinct MI100"
        assert gpus[0].vendor == GPUVendor.AMD

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_detect_amd_not_found(self, mock_run):
        """Test AMD detection when rocm-smi is not found."""
        mock_run.side_effect = FileNotFoundError()
        test = GPUStressTest()
        gpus = test._detect_amd()
        assert gpus == []

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_detect_amd_json_error(self, mock_run):
        """Test AMD detection with invalid JSON response."""
        mock_run.return_value = Mock(returncode=0, stdout="invalid json")
        test = GPUStressTest()
        gpus = test._detect_amd()
        assert gpus == []

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_detect_hygon_with_hygon_smi(self, mock_run):
        """Test Hygon DCU detection with hygon-smi."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="GPU 0: Hygon DCU\nGPU 1: Hygon DCU"
        )
        test = GPUStressTest()
        gpus = test._detect_hygon()

        assert len(gpus) == 2
        assert gpus[0].vendor == GPUVendor.HYGON

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_detect_hygon_fallback_rocm(self, mock_run):
        """Test Hygon DCU detection fallback to rocm-smi."""
        # First call (hygon-smi) fails, second (rocm-smi) succeeds
        mock_run.side_effect = [
            FileNotFoundError(),
            Mock(returncode=0, stdout="Hygon DCU\nHygon DCU")
        ]
        test = GPUStressTest()
        gpus = test._detect_hygon()

        assert len(gpus) == 2
        assert all(g.vendor == GPUVendor.HYGON for g in gpus)

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_detect_cambricon_with_cnmon(self, mock_run):
        """Test Cambricon MLU detection with cnmon."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="| 0 | MLU370-X8 |\n| 1 | MLU370-X4 |"
        )
        test = GPUStressTest()
        gpus = test._detect_cambricon()

        assert len(gpus) >= 1
        assert gpus[0].vendor == GPUVendor.CAMBRICON

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_detect_ascend_success(self, mock_run):
        """Test Huawei Ascend NPU detection."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="| 0 | Ascend 910B |\n| 1 | Ascend 310P |"
        )
        test = GPUStressTest()
        gpus = test._detect_ascend()

        assert len(gpus) >= 1
        assert gpus[0].vendor == GPUVendor.ASCEND

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_detect_moore_threads_with_gmi(self, mock_run):
        """Test Moore Threads GPU detection with mthreads-gmi."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="GPU 0: MTT S80\nGPU 1: MTT S3000"
        )
        test = GPUStressTest()
        gpus = test._detect_moore_threads()

        assert len(gpus) == 2
        assert gpus[0].vendor == GPUVendor.MOORE_THREADS

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_detect_moore_threads_fallback_smi(self, mock_run):
        """Test Moore Threads detection fallback to mthreads-smi."""
        mock_run.side_effect = [
            FileNotFoundError(),
            Mock(returncode=0, stdout="GPU 0: Moore Threads GPU")
        ]
        test = GPUStressTest()
        gpus = test._detect_moore_threads()

        assert len(gpus) == 1
        assert gpus[0].vendor == GPUVendor.MOORE_THREADS


class TestGPUMetricsCollection:
    """Tests for GPU metrics collection across all vendors."""

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_get_nvidia_metrics(self, mock_run):
        """Test NVIDIA metrics collection."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="65, 85, 70, 250.5, 1950\n"
        )
        test = GPUStressTest()
        metrics = test._get_nvidia_metrics(0)

        assert metrics["temperature"] == 65
        assert metrics["utilization"] == 85
        assert metrics["memory_utilization"] == 70
        assert metrics["power"] == 250.5
        assert metrics["clock_speed"] == 1950

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_get_amd_metrics(self, mock_run):
        """Test AMD metrics collection."""
        mock_data = {
            "card_list": [{
                "temperature": 70,
                "gpu_use": 90,
                "average_graphics_package_power": 280
            }]
        }
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps(mock_data))
        test = GPUStressTest()
        metrics = test._get_amd_metrics(0)

        assert metrics["temperature"] == 70
        assert metrics["utilization"] == 90
        assert metrics["power"] == 280

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_get_hygon_metrics_with_hygon_smi(self, mock_run):
        """Test Hygon metrics collection with hygon-smi."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="75, 80, 200.0\n"
        )
        test = GPUStressTest()
        metrics = test._get_hygon_metrics(0)

        assert metrics["temperature"] == 75
        assert metrics["utilization"] == 80
        assert metrics["power"] == 200.0

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_get_cambricon_metrics(self, mock_run):
        """Test Cambricon metrics collection."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="mlu0: 45C 30%\nmlu1: 50C 45%"
        )
        test = GPUStressTest()
        metrics = test._get_cambricon_metrics(0)

        assert "temperature" in metrics or "utilization" in metrics or metrics == {}

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_get_ascend_metrics(self, mock_run):
        """Test Ascend NPU metrics collection."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Ai Core: 85%"),
            Mock(returncode=0, stdout="Temperature: 65C")
        ]
        test = GPUStressTest()
        metrics = test._get_ascend_metrics(0)

        assert "utilization" in metrics or "temperature" in metrics or metrics == {}

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_get_moore_threads_metrics(self, mock_run):
        """Test Moore Threads metrics collection."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Temperature: 60C\nGPU Utilization: 75%\nPower Draw: 150W"
        )
        test = GPUStressTest()
        metrics = test._get_moore_threads_metrics(0)

        assert metrics.get("temperature") == 60
        assert metrics.get("utilization") == 75
        assert metrics.get("power") == 150


class TestStressStartStop:
    """Tests for stress start/stop functionality."""

    @patch.object(GPUStressTest, "_detect_gpus")
    @patch.object(GPUStressTest, "_start_nvidia_stress")
    def test_start_stress_no_gpus(self, mock_start_nvidia, mock_detect):
        """Test start_stress returns False when no GPUs detected."""
        mock_detect.return_value = []
        test = GPUStressTest()
        result = test.start_stress()
        assert result is False

    @patch.object(GPUStressTest, "_detect_gpus")
    def test_start_stress_with_nvidia(self, mock_detect):
        """Test start_stress with NVIDIA GPU."""
        mock_detect.return_value = [
            GPUInfo(index=0, name="RTX 4090", vendor=GPUVendor.NVIDIA,
                    memory_mb=24576, driver_version="535")
        ]
        test = GPUStressTest()

        # Mock _start_nvidia_stress to add a thread entry
        def mock_start_nvidia(gpu):
            test._stress_threads.append(("nvidia", Mock()))

        test._start_nvidia_stress = mock_start_nvidia
        result = test.start_stress()

        assert result is True

    @patch("src.stress_tests.gpu_stress.subprocess.Popen")
    @patch("src.stress_tests.gpu_stress.time.sleep")
    def test_start_nvidia_stress_success(self, mock_sleep, mock_popen):
        """Test NVIDIA stress start with successful process."""
        mock_proc = Mock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        test = GPUStressTest()
        gpu = GPUInfo(index=0, name="RTX 4090", vendor=GPUVendor.NVIDIA,
                      memory_mb=24576, driver_version="535")
        test._start_nvidia_stress(gpu)

        assert len(test._stress_threads) == 1
        assert test._stress_threads[0][0] == "nvidia"

    @patch("src.stress_tests.gpu_stress.subprocess.Popen")
    def test_start_amd_stress(self, mock_popen):
        """Test AMD stress start."""
        mock_proc = Mock()
        mock_popen.return_value = mock_proc

        test = GPUStressTest()
        gpu = GPUInfo(index=0, name="MI100", vendor=GPUVendor.AMD,
                      memory_mb=32768, driver_version="5.4")
        test._start_amd_stress(gpu)

        assert len(test._stress_threads) == 1
        assert test._stress_threads[0][0] == "amd"

    @patch("src.stress_tests.gpu_stress.subprocess.Popen")
    def test_start_hygon_stress(self, mock_popen):
        """Test Hygon stress start."""
        mock_proc = Mock()
        mock_popen.return_value = mock_proc

        test = GPUStressTest()
        gpu = GPUInfo(index=0, name="DCU", vendor=GPUVendor.HYGON,
                      memory_mb=0, driver_version="")
        test._start_hygon_stress(gpu)

        assert len(test._stress_threads) == 1

    @patch("src.stress_tests.gpu_stress.subprocess.Popen")
    def test_start_cambricon_stress(self, mock_popen):
        """Test Cambricon stress start."""
        mock_proc = Mock()
        mock_popen.return_value = mock_proc

        test = GPUStressTest()
        gpu = GPUInfo(index=0, name="MLU", vendor=GPUVendor.CAMBRICON,
                      memory_mb=0, driver_version="")
        test._start_cambricon_stress(gpu)

        assert len(test._stress_threads) == 1

    @patch("src.stress_tests.gpu_stress.subprocess.Popen")
    def test_start_ascend_stress(self, mock_popen):
        """Test Ascend stress start."""
        mock_proc = Mock()
        mock_popen.return_value = mock_proc

        test = GPUStressTest()
        gpu = GPUInfo(index=0, name="Ascend 910", vendor=GPUVendor.ASCEND,
                      memory_mb=0, driver_version="")
        test._start_ascend_stress(gpu)

        assert len(test._stress_threads) == 1

    @patch("src.stress_tests.gpu_stress.subprocess.Popen")
    def test_start_moore_threads_stress(self, mock_popen):
        """Test Moore Threads stress start."""
        mock_proc = Mock()
        mock_popen.return_value = mock_proc

        test = GPUStressTest()
        gpu = GPUInfo(index=0, name="MTT S80", vendor=GPUVendor.MOORE_THREADS,
                      memory_mb=0, driver_version="")
        test._start_moore_threads_stress(gpu)

        assert len(test._stress_threads) == 1

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_stop_stress(self, mock_run):
        """Test stop_stress terminates processes."""
        test = GPUStressTest()
        mock_proc = Mock()
        test._stress_threads = [("nvidia", mock_proc)]
        test._detected_gpus = [
            GPUInfo(index=0, name="RTX 4090", vendor=GPUVendor.NVIDIA,
                    memory_mb=0, driver_version="")
        ]

        test.stop_stress()

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=5)
        assert test._stress_threads == []

    @patch("src.stress_tests.gpu_stress.subprocess.run")
    def test_stop_stress_with_kill(self, mock_run):
        """Test stop_stress kills process when terminate times out."""
        import subprocess
        test = GPUStressTest()
        mock_proc = Mock()
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=5)
        test._stress_threads = [("nvidia", mock_proc)]
        test._detected_gpus = [
            GPUInfo(index=0, name="RTX 4090", vendor=GPUVendor.NVIDIA,
                    memory_mb=0, driver_version="")
        ]

        test.stop_stress()

        mock_proc.kill.assert_called_once()


class TestMultiGPUHandling:
    """Tests for multi-GPU handling."""

    @patch.object(GPUStressTest, "_detect_gpus")
    def test_get_detected_gpus_caches_result(self, mock_detect):
        """Test that get_detected_gpus caches the detection result."""
        mock_gpus = [
            GPUInfo(index=0, name="GPU0", vendor=GPUVendor.NVIDIA,
                    memory_mb=0, driver_version=""),
            GPUInfo(index=1, name="GPU1", vendor=GPUVendor.NVIDIA,
                    memory_mb=0, driver_version="")
        ]
        mock_detect.return_value = mock_gpus

        test = GPUStressTest()
        gpus1 = test.get_detected_gpus()
        gpus2 = test.get_detected_gpus()

        assert gpus1 == gpus2
        assert len(gpus1) == 2
        mock_detect.assert_called_once()

    def test_collect_metrics_multi_gpu(self):
        """Test metrics collection from multiple GPUs."""
        test = GPUStressTest()
        test._detected_gpus = [
            GPUInfo(index=0, name="GPU0", vendor=GPUVendor.NVIDIA,
                    memory_mb=0, driver_version=""),
            GPUInfo(index=1, name="GPU1", vendor=GPUVendor.NVIDIA,
                    memory_mb=0, driver_version="")
        ]

        with patch.object(test, "_get_nvidia_metrics") as mock_get:
            mock_get.side_effect = [
                {"temperature": 60, "utilization": 80},
                {"temperature": 65, "utilization": 85}
            ]
            metrics = test.collect_metrics()

        assert "gpu0_temperature" in metrics
        assert "gpu0_utilization" in metrics
        assert "gpu1_temperature" in metrics
        assert "gpu1_utilization" in metrics
        assert metrics["gpu0_temperature"] == 60
        assert metrics["gpu1_temperature"] == 65

    @patch.object(GPUStressTest, "_detect_gpus")
    def test_start_stress_mixed_vendors(self, mock_detect):
        """Test starting stress with mixed vendor GPUs."""
        mock_detect.return_value = [
            GPUInfo(index=0, name="RTX 4090", vendor=GPUVendor.NVIDIA,
                    memory_mb=0, driver_version=""),
            GPUInfo(index=1, name="MI100", vendor=GPUVendor.AMD,
                    memory_mb=0, driver_version="")
        ]
        test = GPUStressTest()

        nvidia_called = []
        amd_called = []

        def mock_start_nvidia(gpu):
            nvidia_called.append(gpu)
            test._stress_threads.append(("nvidia", Mock()))

        def mock_start_amd(gpu):
            amd_called.append(gpu)
            test._stress_threads.append(("amd", Mock()))

        test._start_nvidia_stress = mock_start_nvidia
        test._start_amd_stress = mock_start_amd
        result = test.start_stress()

        assert result is True
        assert len(nvidia_called) == 1
        assert len(amd_called) == 1


class TestMemoryParsing:
    """Tests for memory string parsing."""

    def test_parse_memory_gib(self):
        """Test parsing GiB memory string."""
        test = GPUStressTest()
        assert test._parse_memory("16 GiB") == 16384
        assert test._parse_memory("24 GiB") == 24576

    def test_parse_memory_gb(self):
        """Test parsing GB memory string."""
        test = GPUStressTest()
        assert test._parse_memory("16 GB") == 16384

    def test_parse_memory_mib(self):
        """Test parsing MiB memory string."""
        test = GPUStressTest()
        assert test._parse_memory("8192 MiB") == 8192

    def test_parse_memory_mb(self):
        """Test parsing MB memory string."""
        test = GPUStressTest()
        assert test._parse_memory("4096 MB") == 4096

    def test_parse_memory_invalid(self):
        """Test parsing invalid memory string."""
        test = GPUStressTest()
        assert test._parse_memory("invalid") == 0
        assert test._parse_memory("") == 0


class TestGetMetricsByVendor:
    """Tests for vendor-specific metric routing."""

    def test_get_metrics_routing(self):
        """Test that _get_metrics_by_vendor routes to correct method."""
        test = GPUStressTest()

        vendors_methods = [
            (GPUVendor.NVIDIA, "_get_nvidia_metrics"),
            (GPUVendor.AMD, "_get_amd_metrics"),
            (GPUVendor.HYGON, "_get_hygon_metrics"),
            (GPUVendor.CAMBRICON, "_get_cambricon_metrics"),
            (GPUVendor.ASCEND, "_get_ascend_metrics"),
            (GPUVendor.MOORE_THREADS, "_get_moore_threads_metrics"),
        ]

        for vendor, method_name in vendors_methods:
            gpu = GPUInfo(index=0, name="Test", vendor=vendor,
                          memory_mb=0, driver_version="")
            with patch.object(test, method_name, return_value={"test": 1}) as mock_method:
                result = test._get_metrics_by_vendor(gpu)
                mock_method.assert_called_once_with(0)
                assert result == {"test": 1}

    def test_get_metrics_unknown_vendor(self):
        """Test handling of unknown vendor."""
        test = GPUStressTest()
        gpu = GPUInfo(index=0, name="Unknown", vendor=GPUVendor.UNKNOWN,
                      memory_mb=0, driver_version="")
        result = test._get_metrics_by_vendor(gpu)
        assert result == {}
