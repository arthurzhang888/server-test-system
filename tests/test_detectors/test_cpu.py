import pytest
from src.detectors.cpu import CPUDetector
from src.detectors.base import DetectorMode


class TestCPUDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = CPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "model" in result
        assert "cores" in result
        assert "threads" in result
        assert "frequency_ghz" in result
        assert "architecture" in result

    def test_mock_cores_is_positive(self):
        detector = CPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["cores"], int)
        assert result["cores"] > 0

    def test_mock_threads_is_positive(self):
        detector = CPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["threads"], int)
        assert result["threads"] > 0

    def test_mock_frequency_is_reasonable(self):
        detector = CPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["frequency_ghz"], (int, float))
        assert 1.0 <= result["frequency_ghz"] <= 5.0


class TestCPUDetectorReal:
    def test_real_returns_dict(self):
        detector = CPUDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
