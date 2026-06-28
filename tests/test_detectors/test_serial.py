import pytest
from src.detectors.serial import SerialDetector
from src.detectors.base import DetectorMode


class TestSerialDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = SerialDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "ports" in result
        assert "port_count" in result
        assert "standard_count" in result
        assert "usb_count" in result

    def test_mock_ports_is_list(self):
        detector = SerialDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["ports"], list)

    def test_mock_port_has_required_fields(self):
        detector = SerialDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for port in result["ports"]:
            assert "name" in port
            assert "device" in port
            assert "type" in port
            assert "status" in port

    def test_mock_port_types_valid(self):
        detector = SerialDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for port in result["ports"]:
            assert port["type"] in ["standard", "usb"]

    def test_mock_standard_port_has_hardware_info(self):
        detector = SerialDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        standard_ports = [p for p in result["ports"] if p["type"] == "standard"]
        for port in standard_ports:
            assert "driver" in port
            assert port["name"].startswith(("ttyS", "ttyAMA"))

    def test_mock_usb_port_has_usb_info(self):
        detector = SerialDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        usb_ports = [p for p in result["ports"] if p["type"] == "usb"]
        for port in usb_ports:
            assert "vendor_id" in port
            assert "product_id" in port
            assert "manufacturer" in port
            assert port["name"].startswith(("ttyUSB", "ttyACM"))


class TestSerialDetectorReal:
    def test_real_returns_dict(self):
        detector = SerialDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "ports" in result
