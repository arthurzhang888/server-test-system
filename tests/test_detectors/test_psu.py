import pytest
from src.detectors.psu import PSUDetector
from src.detectors.base import DetectorMode


class TestPSUDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = PSUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "psu_count" in result
        assert "redundant" in result
        assert "psus" in result
        assert isinstance(result["psus"], list)

    def test_mock_psu_count_matches_list(self):
        detector = PSUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["psu_count"] == len(result["psus"])

    def test_mock_psu_has_required_fields(self):
        detector = PSUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for psu in result["psus"]:
            assert "id" in psu
            assert "present" in psu
            assert "status" in psu
            assert "input_voltage" in psu
            assert "output_watts" in psu

    def test_mock_redundant_configuration(self):
        detector = PSUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        if result["psu_count"] >= 2:
            assert result["redundant"] is True

    def test_mock_load_calculation(self):
        detector = PSUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        if result.get("total_capacity_watts", 0) > 0:
            assert 0 <= result.get("load_percent", 0) <= 100


class TestPSUDetectorReal:
    def test_real_returns_dict(self):
        detector = PSUDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "psus" in result
