import pytest
from src.detectors.memory import MemoryDetector
from src.detectors.base import DetectorMode


class TestMemoryDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = MemoryDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "total_gb" in result
        assert "available_gb" in result
        assert "percent_used" in result
        assert "type" in result

    def test_mock_total_is_positive(self):
        detector = MemoryDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["total_gb"], (int, float))
        assert result["total_gb"] > 0

    def test_mock_available_less_than_total(self):
        detector = MemoryDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert result["available_gb"] <= result["total_gb"]

    def test_mock_percent_in_range(self):
        detector = MemoryDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert 0 <= result["percent_used"] <= 100
