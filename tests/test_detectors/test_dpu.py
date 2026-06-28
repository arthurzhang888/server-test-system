"""Tests for DPU detector (NVIDIA BlueField BF3/BF4)."""

import pytest
from unittest.mock import patch, MagicMock

from src.detectors.dpu import DPUDetector


class TestDPUDetectorMock:
    """Test DPU detector in mock mode."""

    def test_mock_returns_valid_structure(self):
        detector = DPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert isinstance(result, dict)
        assert "present" in result
        assert "device_count" in result
        assert "devices" in result

    def test_mock_has_dpu_devices(self):
        detector = DPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["present"] is True
        assert result["device_count"] == 2
        assert len(result["devices"]) == 2

    def test_mock_device_has_required_fields(self):
        detector = DPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        device = result["devices"][0]

        # Basic info
        assert "name" in device
        assert "pci_slot" in device
        assert "vendor" in device
        assert "model" in device
        assert device["vendor"] == "NVIDIA"
        assert device["model"] == "BlueField-3"

        # Firmware
        assert "firmware_version" in device
        assert "bmc_version" in device

        # DPU-specific
        assert "mode" in device
        assert device["mode"] in ["dpu", "nic", "unknown"]
        assert "arm_cores" in device
        assert "arm_memory_gb" in device
        assert "emmc_storage_gb" in device

        # Network
        assert "network_interfaces" in device
        assert isinstance(device["network_interfaces"], list)

        # Accelerators
        assert "accelerators" in device
        assert isinstance(device["accelerators"], dict)

        # Health
        assert "health" in device
        assert "temperature_c" in device["health"]
        assert "status" in device["health"]

        # Features
        assert "features" in device

    def test_mock_network_interface_structure(self):
        detector = DPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        device = result["devices"][0]
        interfaces = device["network_interfaces"]

        assert len(interfaces) > 0

        for iface in interfaces:
            assert "name" in iface
            assert "type" in iface
            assert iface["type"] in ["physical", "ovs_bridge", "bond"]
            assert "state" in iface

            # Physical interfaces should have MAC
            if iface["type"] == "physical":
                assert "mac" in iface
                assert "speed" in iface

    def test_mock_accelerator_flags(self):
        detector = DPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        device = result["devices"][0]
        acc = device["accelerators"]

        # BF3 has crypto, compression, regex
        assert "crypto" in acc
        assert "compression" in acc
        assert "regex" in acc

    def test_mock_dpu_mode_values(self):
        detector = DPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for device in result["devices"]:
            assert device["mode"] in ["dpu", "nic", "unknown"]
            # Mock data uses dpu mode
            assert device["mode"] == "dpu"


class TestDPUDetectorReal:
    """Test DPU detector in real mode."""

    def test_real_returns_dict(self):
        detector = DPUDetector(mode=DetectorMode.REAL)
        result = detector.detect()

        assert isinstance(result, dict)
        assert "present" in result
        assert "device_count" in result

    def test_real_has_required_keys(self):
        detector = DPUDetector(mode=DetectorMode.REAL)
        result = detector.detect()

        assert "present" in result
        assert "device_count" in result
        assert "devices" in result

    def test_pci_ids_parsing(self):
        """Test that BF3 PCI ID parsing works."""
        detector = DPUDetector(mode=DetectorMode.REAL)

        # Test the parsing logic directly
        test_line = "0000:03:00.0 Ethernet controller [0200]: Mellanox Technologies MT42822 BlueField-3 [15b3:a2dc]"

        # Check if line contains DPU ID (lspci format uses lowercase without 0x)
        found = False
        for dev_id in detector.DPU_PCI_IDS.keys():
            # Remove 0x prefix for comparison with lspci output
            dev_id_clean = dev_id.lower().replace("0x", "")
            if dev_id_clean in test_line.lower():
                found = True
                break

        assert found is True


class TestDPUDetectorBF3Specific:
    """Test BF3-specific detection."""

    def test_bf3_pci_ids_defined(self):
        """Test that BF3 PCI IDs are defined."""
        detector = DPUDetector()

        assert len(detector.DPU_PCI_IDS) > 0
        assert "0xa2dc" in detector.DPU_PCI_IDS
        assert detector.DPU_PCI_IDS["0xa2dc"] == "BlueField-3"

    def test_bf4_pci_ids_placeholder(self):
        """Test BF4 PCI IDs structure."""
        detector = DPUDetector()

        # BF4 IDs may be empty or have placeholders
        assert isinstance(detector.BF4_PCI_IDS, dict)


class TestDPUDetectorHealth:
    """Test DPU health monitoring."""

    def test_mock_health_structure(self):
        detector = DPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for device in result["devices"]:
            health = device["health"]

            assert "status" in health
            assert "temperature_c" in health

            if health["temperature_c"] is not None:
                assert isinstance(health["temperature_c"], (int, float))
                assert health["temperature_c"] > 0


class TestDPUDetectorFeatures:
    """Test DPU feature flags."""

    def test_mock_features_structure(self):
        detector = DPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for device in result["devices"]:
            features = device["features"]

            assert isinstance(features, dict)
            assert "sr_iov" in features
            assert "rdma" in features


# Need to import DetectorMode
from src.detectors.base import DetectorMode
