import pytest
from src.detectors.pcie import PCIeDetector
from src.detectors.base import DetectorMode


class TestPCIeDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = PCIeDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "devices" in result
        assert "device_count" in result
        assert isinstance(result["devices"], list)
        assert isinstance(result["device_count"], int)

    def test_mock_device_has_required_fields(self):
        detector = PCIeDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for device in result["devices"]:
            assert "slot" in device
            assert "type" in device
            assert "vendor" in device

    def test_mock_device_count_matches_devices(self):
        detector = PCIeDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["device_count"] == len(result["devices"])
        assert result["device_count"] > 0

    def test_mock_returns_sample_devices(self):
        detector = PCIeDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        # Should have at least the sample devices
        vendors = [d["vendor"] for d in result["devices"]]
        assert "Intel" in vendors


class TestPCIeDetectorReal:
    def test_real_returns_dict(self):
        detector = PCIeDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)

    def test_real_returns_devices_list(self):
        detector = PCIeDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert "devices" in result
        assert isinstance(result["devices"], list)

    def test_real_returns_device_count(self):
        detector = PCIeDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert "device_count" in result
        assert isinstance(result["device_count"], int)
