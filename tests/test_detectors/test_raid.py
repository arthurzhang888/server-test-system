import pytest
from src.detectors.raid import RAIDDetector
from src.detectors.base import DetectorMode


class TestRAIDDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = RAIDDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "controllers" in result
        assert "controller_count" in result
        assert isinstance(result["controllers"], list)

    def test_mock_has_controller_details(self):
        detector = RAIDDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        if result["controller_count"] > 0:
            controller = result["controllers"][0]
            assert "model" in controller
            assert "vendor" in controller
            assert "arrays" in controller
            assert "physical_drives" in controller

    def test_mock_controller_count_matches(self):
        detector = RAIDDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["controller_count"] == len(result["controllers"])

    def test_mock_arrays_have_required_fields(self):
        detector = RAIDDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for controller in result["controllers"]:
            for array in controller.get("arrays", []):
                assert "id" in array
                assert "raid_level" in array
                assert "size_gb" in array
                assert "status" in array

    def test_mock_physical_drives_have_required_fields(self):
        detector = RAIDDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for controller in result["controllers"]:
            for drive in controller.get("physical_drives", []):
                assert "slot" in drive
                assert "model" in drive
                assert "size_gb" in drive
                assert "status" in drive


class TestRAIDDetectorReal:
    def test_real_returns_dict(self):
        detector = RAIDDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "controllers" in result
