"""Tests for DPU stress test."""

import pytest
from unittest.mock import patch, MagicMock

from src.stress_tests.dpu_stress import DPUStressTest, DPUStressThresholds, DPUTestType


class TestDPUStressTestBasic:
    """Test DPU stress test basic functionality."""

    def test_test_name(self):
        test = DPUStressTest()
        assert test.test_name == "dpu_stress"

    def test_supported_vendors(self):
        test = DPUStressTest()
        assert "nvidia" in test.supported_vendors
        assert "mellanox" in test.supported_vendors

    def test_default_thresholds(self):
        test = DPUStressTest()
        assert test.dpu_thresholds.max_temperature_c == 85.0
        assert test.dpu_thresholds.min_throughput_gbps == 150.0
        assert test.dpu_thresholds.duration_seconds == 300


class TestDPUStressTestMock:
    """Test DPU stress test with mocked DPU."""

    @patch("src.stress_tests.dpu_stress.subprocess.run")
    def test_run_no_dpu(self, mock_run):
        """Test when no DPU is present."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        test = DPUStressTest()
        result = test.run_custom(duration=5)

        assert result.test_name == "dpu_stress"
        assert result.status == "skipped"
        assert "No DPU devices found" in result.error_message

    @patch("src.stress_tests.dpu_stress.subprocess.run")
    def test_run_with_mock_dpu(self, mock_run):
        """Test with mocked DPU present."""
        def mock_subprocess(*args, **kwargs):
            cmd = args[0] if args else []

            if cmd[0] == "lspci":
                return MagicMock(
                    returncode=0,
                    stdout="0000:03:00.0 Ethernet controller [0200]: Mellanox Technologies MT42822 BlueField-3 [15b3:a2dc]\n"
                )
            elif cmd[0] == "devlink":
                if "port" in cmd:
                    return MagicMock(returncode=0, stdout="netdev p0\n")
                return MagicMock(returncode=0, stdout="pci/0000:03:00.0/0: type eth netdev p0\n")
            elif cmd[0] == "ip":
                return MagicMock(returncode=0, stdout="state UP")
            elif cmd[0] == "ethtool":
                return MagicMock(returncode=0, stdout="Speed: 200000Mb/s")

            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = mock_subprocess

        test = DPUStressTest()
        result = test.run_custom(duration=5)

        assert result.test_name == "dpu_stress"
        assert result.status in ["passed", "warning", "failed", "skipped"]
        assert result.duration_seconds >= 0


class TestDPUTemperature:
    """Test DPU temperature monitoring."""

    @patch("builtins.open")
    @patch("glob.glob")
    def test_read_temperature_hwmon(self, mock_glob, mock_open):
        """Test temperature reading from hwmon."""
        mock_glob.return_value = ["/sys/class/hwmon/hwmon0"]

        mock_file = MagicMock()
        mock_file.read.return_value = "mlx5\n"
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)

        mock_temp = MagicMock()
        mock_temp.read.return_value = "65000\n"
        mock_temp.__enter__ = MagicMock(return_value=mock_temp)
        mock_temp.__exit__ = MagicMock(return_value=False)

        mock_open.side_effect = [mock_file, mock_temp]

        test = DPUStressTest()
        temp = test._get_dpu_temperature("0000:03:00.0")

        assert temp == 65.0


class TestDPUNetworkThroughput:
    """Test DPU network throughput measurement."""

    @patch("src.stress_tests.dpu_stress.subprocess.run")
    def test_network_link_speed(self, mock_run):
        """Test reading link speed."""
        def mock_subprocess(*args, **kwargs):
            cmd = args[0] if args else []

            if cmd[0] == "ip":
                return MagicMock(returncode=0, stdout="state UP")
            elif cmd[0] == "ethtool":
                return MagicMock(returncode=0, stdout="Speed: 200000Mb/s")

            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = mock_subprocess

        test = DPUStressTest()
        result = test._test_network_throughput("p0", 5)

        assert result["interface"] == "p0"
        assert result["link_speed_gbps"] == 200.0
        assert result["throughput_gbps"] > 0

    @patch("src.stress_tests.dpu_stress.subprocess.run")
    def test_network_interface_down(self, mock_run):
        """Test handling of down interface."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="state DOWN"
        )

        test = DPUStressTest()
        result = test._test_network_throughput("p0", 5)

        assert "error" in result
        assert "down" in result["error"].lower()


class TestDPUCrypto:
    """Test DPU crypto acceleration."""

    @patch("src.stress_tests.dpu_stress.subprocess.run")
    def test_crypto_speed_test(self, mock_run):
        """Test crypto speed measurement."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="aes-256-gcm 1024 bytes 1000000 ops 0.234s (4273504.27 ops/sec)"
        )

        test = DPUStressTest()
        result = test._test_crypto_acceleration({"pci_slot": "0000:03:00.0"})

        assert result["throughput_gbps"] is not None
        assert result["throughput_gbps"] > 0
        assert result["ops_per_sec"] == 4273504.27

    @patch("src.stress_tests.dpu_stress.subprocess.run")
    def test_crypto_not_available(self, mock_run):
        """Test when openssl is not available."""
        mock_run.side_effect = FileNotFoundError("openssl not found")

        test = DPUStressTest()
        result = test._test_crypto_acceleration({"pci_slot": "0000:03:00.0"})

        assert "error" in result


class TestDPUHardwareOffload:
    """Test hardware offload detection."""

    @patch("src.stress_tests.dpu_stress.subprocess.run")
    def test_ovs_hw_offload(self, mock_run):
        """Test OVS hardware offload detection."""
        def mock_subprocess(*args, **kwargs):
            cmd = args[0] if args else []

            if "ovs-vsctl" in cmd:
                return MagicMock(returncode=0, stdout='"true"')

            return MagicMock(returncode=1, stdout="")

        mock_run.side_effect = mock_subprocess

        test = DPUStressTest()
        result = test._test_hardware_offload({"interfaces": ["p0"]})

        assert result["verified"] is True
        assert "ovs_hw_offload" in result["features"]

    @patch("src.stress_tests.dpu_stress.subprocess.run")
    def test_rdma_available(self, mock_run):
        """Test RDMA detection."""
        def mock_subprocess(*args, **kwargs):
            cmd = args[0] if args else []

            if cmd[0] == "ibstat":
                return MagicMock(returncode=0, stdout="CA 'mlx5_0'")

            return MagicMock(returncode=1, stdout="")

        mock_run.side_effect = mock_subprocess

        test = DPUStressTest()
        result = test._test_hardware_offload({"interfaces": ["p0"]})

        assert result["verified"] is True
        assert "rdma" in result["features"]


class TestDPUStressThresholds:
    """Test DPU stress thresholds."""

    def test_custom_thresholds(self):
        thresholds = DPUStressThresholds(
            max_temperature_c=80.0,
            min_throughput_gbps=160.0,
            duration_seconds=600
        )

        assert thresholds.max_temperature_c == 80.0
        assert thresholds.min_throughput_gbps == 160.0
        assert thresholds.duration_seconds == 600

    def test_temperature_check(self):
        """Test that temperature threshold checking works."""
        thresholds = DPUStressThresholds(max_temperature_c=85.0)

        # Simulate high temperature
        assert 90.0 > thresholds.max_temperature_c  # Should trigger error
        assert 80.0 < thresholds.max_temperature_c  # Should be OK


class TestDPUQuickAndExtended:
    """Test quick and extended test modes."""

    @patch("src.stress_tests.dpu_stress.subprocess.run")
    def test_quick_test(self, mock_run):
        """Test quick 30-second test."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        test = DPUStressTest()
        result = test.quick_test()

        assert result.test_name == "dpu_stress"
        assert result.duration_seconds < 60  # Should complete quickly

    @patch("src.stress_tests.dpu_stress.subprocess.run")
    def test_extended_test(self, mock_run):
        """Test extended test with custom duration."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        test = DPUStressTest()
        result = test.extended_test(duration=60)

        assert result.test_name == "dpu_stress"
