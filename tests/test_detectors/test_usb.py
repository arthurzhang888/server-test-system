import pytest
from src.detectors.usb import USBDetector
from src.detectors.base import DetectorMode


class TestUSBDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = USBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "controllers" in result
        assert "devices" in result
        assert "controller_count" in result
        assert "device_count" in result

    def test_mock_controllers_is_list(self):
        detector = USBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["controllers"], list)

    def test_mock_devices_is_list(self):
        detector = USBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["devices"], list)

    def test_mock_controller_has_required_fields(self):
        detector = USBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for ctrl in result["controllers"]:
            assert "bus" in ctrl
            assert "id" in ctrl
            assert "vendor" in ctrl
            assert "product" in ctrl
            assert "speed" in ctrl

    def test_mock_device_has_required_fields(self):
        detector = USBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for dev in result["devices"]:
            assert "bus" in dev
            assert "device" in dev
            assert "id" in dev
            assert "vendor" in dev
            assert "class" in dev

    def test_mock_counts_match_lists(self):
        detector = USBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["controller_count"] == len(result["controllers"])
        assert result["device_count"] == len(result["devices"])


class TestUSBDetectorReal:
    def test_real_returns_dict(self):
        detector = USBDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "controllers" in result
