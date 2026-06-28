import pytest
from src.detectors.fpga import FPGADetector
from src.detectors.base import DetectorMode


class TestFPGADetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = FPGADetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "fpgas" in result
        assert "fpga_count" in result
        assert isinstance(result["fpgas"], list)

    def test_mock_fpga_count_matches_list(self):
        detector = FPGADetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["fpga_count"] == len(result["fpgas"])

    def test_mock_fpga_has_required_fields(self):
        detector = FPGADetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for fpga in result["fpgas"]:
            assert "index" in fpga
            assert "model" in fpga
            assert "vendor" in fpga
            assert "pci_slot" in fpga

    def test_mock_xilinx_alveo_present(self):
        detector = FPGADetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        xilinx_fpgas = [f for f in result["fpgas"] if f["vendor"] == "Xilinx"]
        assert len(xilinx_fpgas) >= 1
        assert any("Alveo" in f["model"] for f in xilinx_fpgas)

    def test_mock_intel_stratix_present(self):
        detector = FPGADetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        intel_fpgas = [f for f in result["fpgas"] if f["vendor"] == "Intel"]
        assert len(intel_fpgas) >= 1
        assert any("Stratix" in f["model"] for f in intel_fpgas)


class TestFPGADetectorReal:
    def test_real_returns_dict(self):
        detector = FPGADetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "fpgas" in result
