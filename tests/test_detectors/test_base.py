import pytest
from abc import ABC
from src.detectors.base import BaseDetector, DetectorMode


class TestDetectorMode:
    def test_mock_mode_value(self):
        assert DetectorMode.MOCK.value == "mock"

    def test_real_mode_value(self):
        assert DetectorMode.REAL.value == "real"


class ConcreteDetector(BaseDetector):
    """Concrete implementation for testing."""

    def detect_real(self) -> dict:
        return {"mode": "real", "data": "real_hardware_info"}

    def detect_mock(self) -> dict:
        return {"mode": "mock", "data": "simulated_info"}


class TestBaseDetector:
    def test_default_mode_is_real(self):
        detector = ConcreteDetector()
        assert detector.mode == DetectorMode.REAL

    def test_mock_mode_can_be_set(self):
        detector = ConcreteDetector(mode=DetectorMode.MOCK)
        assert detector.mode == DetectorMode.MOCK

    def test_detect_routes_to_real(self):
        detector = ConcreteDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert result["mode"] == "real"

    def test_detect_routes_to_mock(self):
        detector = ConcreteDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert result["mode"] == "mock"

    def test_is_abstract(self):
        assert issubclass(BaseDetector, ABC)
