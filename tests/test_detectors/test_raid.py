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


class TestRAIDDetectorArcconfParsing:
    """Tests for arcconf output parsing."""

    def test_parse_arcconf_battery_info(self):
        detector = RAIDDetector()
        sample_output = """
Controller Battery Information
------------------------------
Status: Optimal
Remaining Charge: 95%
"""
        result = detector._parse_arcconf_output(sample_output)
        assert result["battery"]["present"] is True
        assert result["battery"]["status"] == "Optimal"
        assert result["battery"]["charge_percent"] == 95

    def test_parse_arcconf_logical_device(self):
        detector = RAIDDetector()
        sample_output = """
Logical Device information
--------------------------
Logical Device number 0
   RAID level: RAID5
   Status of logical device: Optimal
   Size: 1000 GB
"""
        result = detector._parse_arcconf_output(sample_output)
        assert len(result["arrays"]) == 1
        assert result["arrays"][0]["raid_level"] == "RAID5"
        assert result["arrays"][0]["status"] == "Optimal"
        assert result["arrays"][0]["size_gb"] == 1000

    def test_parse_arcconf_physical_drive(self):
        detector = RAIDDetector()
        sample_output = """
Physical Device information
---------------------------
Device #0
   State: Online
   Model: ST2000NM0008
   Size: 1920 GB
"""
        result = detector._parse_arcconf_output(sample_output)
        assert len(result["physical_drives"]) == 1
        assert result["physical_drives"][0]["status"] == "Online"
        assert result["physical_drives"][0]["model"] == "ST2000NM0008"
        assert result["physical_drives"][0]["size_gb"] == 1920


class TestRAIDDetectorSsacliParsing:
    """Tests for ssacli output parsing."""

    def test_parse_ssacli_logical_drive(self):
        detector = RAIDDetector()
        sample_output = """
Logical Drive: 1
   RAID Level: RAID 5
   Status: OK
   Size: 2.0 TB
"""
        result = detector._parse_ssacli_ld_output(sample_output)
        assert len(result) == 1
        assert result[0]["raid_level"] == "RAID5"
        assert result[0]["status"] == "OK"
        assert result[0]["size_gb"] == 2048  # 2.0 TB = 2048 GB

    def test_parse_ssacli_physical_drive(self):
        detector = RAIDDetector()
        sample_output = """
   physicaldrive 1I:1:1
      Status: OK
      Model: HP EG0600JETKA
      Size: 600 GB
"""
        result = detector._parse_ssacli_pd_output(sample_output)
        assert len(result) == 1
        assert result[0]["status"] == "OK"
        assert result[0]["model"] == "HP EG0600JETKA"
        assert result[0]["size_gb"] == 600
