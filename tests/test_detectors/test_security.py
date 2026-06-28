import pytest
from src.detectors.security import SecurityDetector
from src.detectors.base import DetectorMode


class TestSecurityDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = SecurityDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "sgx" in result
        assert "sev" in result
        assert "txt" in result
        assert "memory_encryption" in result

    def test_mock_sgx_has_required_fields(self):
        detector = SecurityDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        sgx = result["sgx"]
        assert "present" in sgx
        assert "enabled" in sgx
        assert "flc" in sgx
        assert "epc_size_mb" in sgx
        assert isinstance(sgx["present"], bool)
        assert isinstance(sgx["enabled"], bool)

    def test_mock_sev_has_required_fields(self):
        detector = SecurityDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        sev = result["sev"]
        assert "present" in sev
        assert "enabled" in sev
        assert "es" in sev
        assert "snp" in sev
        assert isinstance(sev["present"], bool)
        assert isinstance(sev["enabled"], bool)

    def test_mock_txt_has_required_fields(self):
        detector = SecurityDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        txt = result["txt"]
        assert "present" in txt
        assert "enabled" in txt
        assert "bios_measured" in txt
        assert isinstance(txt["present"], bool)
        assert isinstance(txt["enabled"], bool)

    def test_mock_memory_encryption_has_required_fields(self):
        detector = SecurityDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        mem = result["memory_encryption"]
        assert "supported" in mem
        assert "type" in mem
        assert isinstance(mem["supported"], bool)


class TestSecurityDetectorReal:
    def test_real_returns_dict(self):
        detector = SecurityDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "sgx" in result
        assert "sev" in result
        assert "txt" in result
