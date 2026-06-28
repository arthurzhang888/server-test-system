import pytest
from src.detectors.chassis import ChassisDetector
from src.detectors.base import DetectorMode


class TestChassisDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = ChassisDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "type" in result
        assert "manufacturer" in result
        assert "model" in result
        assert "serial" in result
        assert "asset_tag" in result
        assert "service_tag" in result
        assert "rack_location" in result
        assert "power_state" in result
        assert "led_status" in result
        assert "lock_status" in result
        assert "version" in result
        assert "sku" in result

    def test_mock_chassis_type_is_valid(self):
        detector = ChassisDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["type"], str)
        assert result["type"] != ""

    def test_mock_identifiers_are_strings(self):
        detector = ChassisDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert isinstance(result["serial"], str)
        assert isinstance(result["asset_tag"], str)
        assert isinstance(result["service_tag"], str)
        assert isinstance(result["manufacturer"], str)
        assert isinstance(result["model"], str)

    def test_mock_status_fields_are_valid(self):
        detector = ChassisDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert isinstance(result["power_state"], str)
        assert isinstance(result["led_status"], str)
        assert isinstance(result["lock_status"], str)

    def test_mock_rack_location_is_string(self):
        detector = ChassisDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["rack_location"], str)

    def test_mock_type_raw_is_integer(self):
        detector = ChassisDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert "type_raw" in result
        assert isinstance(result["type_raw"], int)


class TestChassisDetectorReal:
    def test_real_returns_dict(self):
        detector = ChassisDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)

    def test_real_has_expected_keys(self):
        detector = ChassisDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert "type" in result
        assert "manufacturer" in result
        assert "serial" in result
