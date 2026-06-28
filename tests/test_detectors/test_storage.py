import pytest
from src.detectors.storage import StorageDetector
from src.detectors.base import DetectorMode


class TestStorageDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = StorageDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "disks" in result
        assert "total_size_gb" in result
        assert "disk_count" in result
        assert isinstance(result["disks"], list)

    def test_mock_disks_have_required_fields(self):
        detector = StorageDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for disk in result["disks"]:
            assert "name" in disk
            assert "type" in disk
            assert "size_gb" in disk
            assert "model" in disk

    def test_mock_disk_count_matches_disks_list(self):
        detector = StorageDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["disk_count"] == len(result["disks"])

    def test_mock_total_size_is_positive(self):
        detector = StorageDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert isinstance(result["total_size_gb"], (int, float))
        assert result["total_size_gb"] > 0

    def test_mock_disk_types_are_valid(self):
        detector = StorageDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        valid_types = ["NVMe", "SATA", "SAS"]
        for disk in result["disks"]:
            assert disk["type"] in valid_types

    def test_mock_disk_sizes_are_positive(self):
        detector = StorageDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for disk in result["disks"]:
            assert isinstance(disk["size_gb"], (int, float))
            assert disk["size_gb"] > 0

    def test_mock_total_size_matches_sum(self):
        detector = StorageDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        calculated_total = sum(disk["size_gb"] for disk in result["disks"])
        assert result["total_size_gb"] == calculated_total


class TestStorageDetectorReal:
    def test_real_returns_dict(self):
        detector = StorageDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)

    def test_real_has_disks_list(self):
        detector = StorageDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert "disks" in result
        assert isinstance(result["disks"], list)
