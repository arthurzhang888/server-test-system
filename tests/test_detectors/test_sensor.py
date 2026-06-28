import pytest
from src.detectors.sensor import SensorDetector
from src.detectors.base import DetectorMode


class TestSensorDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = SensorDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "sensors" in result
        assert "temperatures" in result["sensors"]
        assert "fans" in result["sensors"]
        assert isinstance(result["sensors"]["temperatures"], list)
        assert isinstance(result["sensors"]["fans"], list)

    def test_mock_temperatures_have_required_fields(self):
        detector = SensorDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for temp in result["sensors"]["temperatures"]:
            assert "name" in temp
            assert "value" in temp
            assert "unit" in temp
            assert "status" in temp
            assert temp["unit"] == "C"

    def test_mock_fans_have_required_fields(self):
        detector = SensorDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for fan in result["sensors"]["fans"]:
            assert "name" in fan
            assert "rpm" in fan
            assert "percent" in fan
            assert "status" in fan

    def test_mock_sensor_count_matches(self):
        detector = SensorDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        temps = result["sensors"]["temperatures"]
        fans = result["sensors"]["fans"]

        assert result["sensor_count"]["temperatures"] == len(temps)
        assert result["sensor_count"]["fans"] == len(fans)

    def test_mock_temperature_values_reasonable(self):
        detector = SensorDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for temp in result["sensors"]["temperatures"]:
            assert 0 <= temp["value"] <= 100


class TestSensorDetectorReal:
    def test_real_returns_dict(self):
        detector = SensorDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "sensors" in result
