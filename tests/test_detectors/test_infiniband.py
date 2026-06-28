import pytest
from src.detectors.infiniband import IBDetector
from src.detectors.base import DetectorMode


class TestIBDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = IBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "present" in result
        assert "device_count" in result
        assert "devices" in result
        assert isinstance(result["present"], bool)
        assert isinstance(result["device_count"], int)
        assert isinstance(result["devices"], list)

    def test_mock_has_devices_when_present(self):
        detector = IBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["present"] is True
        assert result["device_count"] > 0
        assert len(result["devices"]) > 0

    def test_mock_devices_have_required_fields(self):
        detector = IBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for device in result["devices"]:
            assert "name" in device
            assert "guid" in device
            assert "vendor" in device
            assert "model" in device
            assert "firmware_version" in device
            assert "ports" in device
            assert isinstance(device["ports"], list)

    def test_mock_ports_have_required_fields(self):
        detector = IBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for device in result["devices"]:
            for port in device["ports"]:
                assert "port_num" in port
                assert "state" in port
                assert "phys_state" in port
                assert "rate" in port
                assert "lid" in port

    def test_mock_device_count_matches_devices(self):
        detector = IBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["device_count"] == len(result["devices"])


class TestIBDetectorReal:
    def test_real_returns_dict(self):
        detector = IBDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)

    def test_real_has_required_keys(self):
        detector = IBDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert "present" in result
        assert "device_count" in result
        assert "devices" in result
