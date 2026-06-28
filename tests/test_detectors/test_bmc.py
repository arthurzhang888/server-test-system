import pytest
from src.detectors.bmc import BMCDetector
from src.detectors.base import DetectorMode


class TestBMCDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = BMCDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "bmc_version" in result
        assert "ipmi_enabled" in result
        assert "bmc_ip" in result
        assert "sensors" in result

    def test_mock_bmc_version_is_string(self):
        detector = BMCDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["bmc_version"], str)
        assert len(result["bmc_version"]) > 0

    def test_mock_ipmi_enabled_is_boolean(self):
        detector = BMCDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["ipmi_enabled"], bool)

    def test_mock_bmc_ip_is_valid_format(self):
        detector = BMCDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["bmc_ip"], str)
        # Basic IP format check
        parts = result["bmc_ip"].split(".")
        assert len(parts) == 4
        for part in parts:
            assert part.isdigit()
            assert 0 <= int(part) <= 255

    def test_mock_sensors_is_list(self):
        detector = BMCDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["sensors"], list)
        assert len(result["sensors"]) > 0

    def test_mock_sensor_has_required_fields(self):
        detector = BMCDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        for sensor in result["sensors"]:
            assert "name" in sensor
            assert "value" in sensor
            assert "unit" in sensor
            assert isinstance(sensor["name"], str)
            assert isinstance(sensor["value"], (int, float))
            assert isinstance(sensor["unit"], str)


class TestBMCDetectorReal:
    def test_real_returns_dict(self):
        detector = BMCDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)

    def test_real_has_expected_keys(self):
        detector = BMCDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        # Real mode may return empty dict if ipmitool is not available
        # but should still have the expected structure if data is available
        if result:
            assert "bmc_version" in result
            assert "ipmi_enabled" in result
