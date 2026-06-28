import pytest
from src.detectors.network import NetworkDetector
from src.detectors.base import DetectorMode


class TestNetworkDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = NetworkDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "interfaces" in result
        assert "interface_count" in result
        assert isinstance(result["interfaces"], list)
        assert isinstance(result["interface_count"], int)

    def test_mock_interfaces_have_required_fields(self):
        detector = NetworkDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for interface in result["interfaces"]:
            assert "name" in interface
            assert "mac" in interface
            assert "speed_mbps" in interface
            assert "type" in interface

    def test_mock_interface_count_matches_interfaces(self):
        detector = NetworkDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["interface_count"] == len(result["interfaces"])

    def test_mock_mac_address_format(self):
        detector = NetworkDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for interface in result["interfaces"]:
            mac = interface["mac"]
            assert isinstance(mac, str)
            assert len(mac) == 17  # aa:bb:cc:dd:ee:ff
            parts = mac.split(":")
            assert len(parts) == 6

    def test_mock_speed_is_positive(self):
        detector = NetworkDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for interface in result["interfaces"]:
            assert isinstance(interface["speed_mbps"], int)
            assert interface["speed_mbps"] > 0

    def test_mock_interface_type_is_ethernet(self):
        detector = NetworkDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for interface in result["interfaces"]:
            assert interface["type"] == "Ethernet"


class TestNetworkDetectorReal:
    def test_real_returns_dict(self):
        detector = NetworkDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)

    def test_real_has_interfaces_key(self):
        detector = NetworkDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert "interfaces" in result
        assert isinstance(result["interfaces"], list)

    def test_real_has_interface_count(self):
        detector = NetworkDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert "interface_count" in result
        assert isinstance(result["interface_count"], int)
