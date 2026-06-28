import pytest
from src.detectors.bios import BIOSDetector
from src.detectors.base import DetectorMode


class TestBIOSDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = BIOSDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "type" in result
        assert "vendor" in result
        assert "version" in result
        assert "date" in result

    def test_mock_type_is_valid(self):
        detector = BIOSDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert result["type"] in ["UEFI", "Legacy BIOS"]

    def test_mock_secure_boot_structure(self):
        detector = BIOSDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "secure_boot" in result
        assert "supported" in result["secure_boot"]
        assert "enabled" in result["secure_boot"]

    def test_mock_characteristics_is_list(self):
        detector = BIOSDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert "characteristics" in result
        assert isinstance(result["characteristics"], list)

    def test_mock_system_info_present(self):
        detector = BIOSDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert "system_serial" in result
        assert "system_uuid" in result


class TestBIOSDetectorReal:
    def test_real_returns_dict(self):
        detector = BIOSDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "type" in result
