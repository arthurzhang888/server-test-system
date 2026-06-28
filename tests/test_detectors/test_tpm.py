import pytest
from src.detectors.tpm import TPMDetector
from src.detectors.base import DetectorMode


class TestTPMDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = TPMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "present" in result
        assert "version" in result
        assert "status" in result

    def test_mock_present_is_boolean(self):
        detector = TPMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["present"], bool)

    def test_mock_version_format(self):
        detector = TPMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        if result["present"]:
            assert result["version"] in ["1.2", "2.0"]

    def test_mock_has_vendor(self):
        detector = TPMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        if result["present"]:
            assert "vendor" in result
            assert isinstance(result["vendor"], str)

    def test_mock_pcr_banks_is_list(self):
        detector = TPMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        if result["present"]:
            assert "pcr_banks" in result
            assert isinstance(result["pcr_banks"], list)


class TestTPMDetectorReal:
    def test_real_returns_dict(self):
        detector = TPMDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "present" in result
