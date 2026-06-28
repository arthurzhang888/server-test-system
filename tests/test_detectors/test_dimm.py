import pytest
from src.detectors.dimm import DIMMDetector
from src.detectors.base import DetectorMode


class TestDIMMDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = DIMMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "dimms" in result
        assert "total_slots" in result
        assert "populated_slots" in result
        assert "total_memory_gb" in result
        assert isinstance(result["dimms"], list)

    def test_mock_dimms_have_required_fields(self):
        detector = DIMMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for dimm in result["dimms"]:
            assert "slot" in dimm
            assert "size_gb" in dimm
            assert "type" in dimm
            assert "status" in dimm

    def test_mock_populated_dimm_has_all_fields(self):
        detector = DIMMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        populated = [d for d in result["dimms"] if d.get("size_gb", 0) > 0]
        assert len(populated) > 0

        dimm = populated[0]
        assert "speed_mhz" in dimm
        assert "configured_speed_mhz" in dimm
        assert "manufacturer" in dimm
        assert "serial_number" in dimm
        assert "part_number" in dimm
        assert "rank" in dimm
        assert "voltage_v" in dimm
        assert "ecc" in dimm
        assert "temperature_c" in dimm
        assert "correctable_errors" in dimm
        assert "uncorrectable_errors" in dimm

    def test_mock_memory_totals_valid(self):
        detector = DIMMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        populated = [d for d in result["dimms"] if d.get("size_gb", 0) > 0]
        expected_total = sum(d["size_gb"] for d in populated)

        assert result["populated_slots"] == len(populated)
        assert result["total_memory_gb"] == pytest.approx(expected_total, 0.01)
        assert result["total_slots"] >= result["populated_slots"]

    def test_mock_empty_dimm_has_null_fields(self):
        detector = DIMMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        empty = [d for d in result["dimms"] if d.get("size_gb", 0) == 0]
        if empty:
            dimm = empty[0]
            assert dimm["status"] == "Empty"
            assert dimm["type"] is None
            assert dimm["manufacturer"] is None

    def test_parse_size_method(self):
        detector = DIMMDetector(mode=DetectorMode.MOCK)

        assert detector._parse_size("8192 MB") == 8.0
        assert detector._parse_size("64 GB") == 64.0
        assert detector._parse_size("1 TB") == 1024.0
        assert detector._parse_size("No Module Installed") == 0.0
        assert detector._parse_size("0 MB") == 0.0


class TestDIMMDetectorReal:
    def test_real_returns_dict(self):
        detector = DIMMDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)

    def test_real_has_dimms_list(self):
        detector = DIMMDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert "dimms" in result
        assert isinstance(result["dimms"], list)


class TestDIMMDetectorParsing:
    def test_parse_memory_devices_empty_input(self):
        detector = DIMMDetector(mode=DetectorMode.MOCK)
        result = detector._parse_memory_devices("")
        assert result == []

    def test_parse_memory_devices_valid_output(self):
        detector = DIMMDetector(mode=DetectorMode.MOCK)
        sample_output = """
Handle 0x002B, DMI type 17, 40 bytes
Memory Device
	Array Handle: 0x002A
	Error Information Handle: Not Provided
	Total Width: 72 bits
	Data Width: 64 bits
	Size: 64 GB
	Form Factor: DIMM
	Set: None
	Locator: DIMM_A1
	Bank Locator: BANK 0
	Type: DDR5
	Type Detail: Synchronous
	Speed: 4800 MT/s
	Manufacturer: Samsung
	Serial Number: S12345678
	Asset Tag: Not Specified
	Part Number: M393A8G40AB2-CWE
	Rank: 2
	Configured Memory Speed: 4400 MT/s
"""
        result = detector._parse_memory_devices(sample_output)
        assert len(result) == 1
        assert result[0]["slot"] == "DIMM_A1"
        assert result[0]["size_gb"] == 64.0
        assert result[0]["type"] == "DDR5"
