import pytest
from src.detectors.gpu import GPUDetector
from src.detectors.base import DetectorMode


class TestGPUDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = GPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "gpus" in result
        assert "gpu_count" in result
        assert "vendor" in result

    def test_mock_gpu_list_is_list(self):
        detector = GPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["gpus"], list)

    def test_mock_gpu_count_matches_list(self):
        detector = GPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert result["gpu_count"] == len(result["gpus"])

    def test_mock_gpu_has_required_fields(self):
        detector = GPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        if result["gpus"]:
            gpu = result["gpus"][0]
            assert "index" in gpu
            assert "name" in gpu
            assert "memory_gb" in gpu
            assert "driver" in gpu

    def test_mock_simulates_nvidia_a100(self):
        detector = GPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["vendor"] == "NVIDIA"
        assert len(result["gpus"]) == 1
        assert result["gpus"][0]["name"] == "NVIDIA A100"
        assert result["gpus"][0]["memory_gb"] == 80

    def test_mock_memory_is_positive(self):
        detector = GPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for gpu in result["gpus"]:
            assert isinstance(gpu["memory_gb"], int)
            assert gpu["memory_gb"] > 0

    def test_mock_driver_is_string(self):
        detector = GPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for gpu in result["gpus"]:
            assert isinstance(gpu["driver"], str)
            assert len(gpu["driver"]) > 0


class TestGPUDetectorReal:
    def test_real_returns_dict(self):
        detector = GPUDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)

    def test_real_has_required_keys(self):
        detector = GPUDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert "gpus" in result
        assert "gpu_count" in result
        assert "vendor" in result

    def test_real_gpu_count_is_non_negative(self):
        detector = GPUDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result["gpu_count"], int)
        assert result["gpu_count"] >= 0

    def test_real_gpus_is_list(self):
        detector = GPUDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result["gpus"], list)

    def test_real_gpu_list_length_matches_count(self):
        detector = GPUDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert len(result["gpus"]) == result["gpu_count"]

    def test_real_vendor_is_string(self):
        detector = GPUDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result["vendor"], str)


class TestGPUDetectorVendorDetection:
    def test_nvidia_vendor_detection(self):
        detector = GPUDetector()
        gpus = [{"name": "NVIDIA GeForce RTX 4090"}]
        assert detector._determine_vendor(gpus) == "NVIDIA"

    def test_amd_vendor_detection(self):
        detector = GPUDetector()
        gpus = [{"name": "AMD Radeon RX 7900 XTX"}]
        assert detector._determine_vendor(gpus) == "AMD"

    def test_intel_vendor_detection(self):
        detector = GPUDetector()
        gpus = [{"name": "Intel Arc A770"}]
        assert detector._determine_vendor(gpus) == "Intel"

    def test_unknown_vendor_when_empty(self):
        detector = GPUDetector()
        assert detector._determine_vendor([]) == "Unknown"


class TestGPUDetectorMemoryParsing:
    def test_parse_memory_mib(self):
        detector = GPUDetector()
        assert detector._parse_memory("8192 MiB") == 8

    def test_parse_memory_gib(self):
        detector = GPUDetector()
        assert detector._parse_memory("80 GiB") == 80

    def test_parse_memory_invalid(self):
        detector = GPUDetector()
        assert detector._parse_memory("invalid") == 0

    def test_parse_memory_number_only(self):
        detector = GPUDetector()
        assert detector._parse_memory("80") == 80
