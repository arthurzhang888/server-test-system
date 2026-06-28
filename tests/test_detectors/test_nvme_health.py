import pytest
from src.detectors.nvme_health import NVMeHealthDetector
from src.detectors.base import DetectorMode


class TestNVMeHealthDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = NVMeHealthDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "devices" in result
        assert "device_count" in result
        assert "overall_health" in result
        assert isinstance(result["devices"], list)

    def test_mock_devices_have_required_fields(self):
        detector = NVMeHealthDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for device in result["devices"]:
            assert "device" in device
            assert "model" in device
            assert "serial" in device
            assert "health_percentage" in device
            assert "temperature_celsius" in device
            assert "available_spare_percentage" in device
            assert "data_read_tb" in device
            assert "data_written_tb" in device
            assert "power_on_hours" in device
            assert "power_cycles" in device
            assert "media_errors" in device
            assert "unsafe_shutdowns" in device
            assert "predicted_life_remaining_percentage" in device
            assert "critical_warning" in device

    def test_mock_device_count_matches_devices_list(self):
        detector = NVMeHealthDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["device_count"] == len(result["devices"])

    def test_mock_health_values_are_valid(self):
        detector = NVMeHealthDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for device in result["devices"]:
            assert isinstance(device["health_percentage"], (int, float))
            assert 0 <= device["health_percentage"] <= 100
            assert isinstance(device["temperature_celsius"], int)
            assert device["temperature_celsius"] > 0
            assert isinstance(device["available_spare_percentage"], (int, float))
            assert 0 <= device["available_spare_percentage"] <= 100
            assert isinstance(device["predicted_life_remaining_percentage"], (int, float))
            assert 0 <= device["predicted_life_remaining_percentage"] <= 100

    def test_mock_data_values_are_non_negative(self):
        detector = NVMeHealthDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for device in result["devices"]:
            assert device["data_read_tb"] >= 0
            assert device["data_written_tb"] >= 0
            assert device["power_on_hours"] >= 0
            assert device["power_cycles"] >= 0
            assert device["media_errors"] >= 0
            assert device["unsafe_shutdowns"] >= 0

    def test_mock_overall_health_is_valid_status(self):
        detector = NVMeHealthDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        valid_statuses = ["excellent", "good", "fair", "poor", "degraded", "critical", "unknown"]
        assert result["overall_health"] in valid_statuses


class TestNVMeHealthDetectorReal:
    def test_real_returns_dict(self):
        detector = NVMeHealthDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)

    def test_real_has_devices_list(self):
        detector = NVMeHealthDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert "devices" in result
        assert isinstance(result["devices"], list)
